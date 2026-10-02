"""Sicherer Abschluss manueller Änderungen an archivierten Ereignissen.

Die Kamerabibliothek ist für diesen Workflow strikt read-only. Die App prüft
nur, ob der Benutzer die angekündigten Verschiebungen manuell korrekt
ausgeführt hat, und aktualisiert anschließend ausschließlich die Datenbank.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.database import database_connection
from app.event_timeline import normalize_no_event_segments, replace_event_segments
from app.event_inventory import EventInventoryError, scan_event_inventory
from app.filename_collisions import collision_alias_stems
from app.archive_locations import (
    ArchiveLocationError,
    archive_path_without_symlinks,
    record_family_anchor,
    record_verified_file_location,
)


class EventChangeApplyError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _safe_archive_path(archive_root: Path, relative_value: Any) -> Path:
    raw = str(relative_value or "").strip().replace("\\", "/")
    try:
        return archive_path_without_symlinks(archive_root, raw)
    except ArchiveLocationError as exc:
        raise EventChangeApplyError(str(exc)) from exc


def _collision_verified_archive_target(
    archive_root: Path,
    relative_value: str,
    *,
    expected_size: int,
    expected_sha: str,
    asset_kind: str,
) -> tuple[Path, str] | None:
    """Resolve common Finder/Windows collision names by content identity.

    The planned exact path remains preferred. If the filesystem chose a
    duplicate suffix instead, only candidates in the same target directory
    with a recognized collision-equivalent stem, matching extension, size and
    SHA-256 are accepted. For exports, Bibliothekar's planned _Export suffix
    and the unsuffixed filename are equivalent collision choices.
    """
    target = _safe_archive_path(archive_root, relative_value)
    parent = target.parent
    if not parent.exists() or not parent.is_dir() or parent.is_symlink():
        return None

    expected_aliases = collision_alias_stems(
        target.stem,
        allow_plain_number=True,
        include_export_base=asset_kind == "export",
    )
    matches: list[Path] = []
    try:
        children = list(parent.iterdir())
    except OSError:
        return None

    for candidate in children:
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if candidate.suffix.casefold() != target.suffix.casefold():
                continue
            aliases = collision_alias_stems(
                candidate.stem,
                allow_plain_number=True,
                include_export_base=asset_kind == "export",
            )
            if not (aliases & expected_aliases):
                continue
            if expected_size and int(candidate.stat().st_size) != int(expected_size):
                continue
            if _sha256_file(candidate) != expected_sha:
                continue
            matches.append(candidate)
        except OSError:
            continue

    if len(matches) != 1:
        return None
    resolved = matches[0].resolve(strict=False)
    root = archive_root.expanduser().resolve(strict=False)
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        return None
    return resolved, relative


def confirm_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path | None = None,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Markiere einen vorgeschlagenen Auftrag als bereit zur manuellen Ausführung.

    Diese Bestätigung verändert keine Datei und ist keine Behauptung, dass die
    Dateioperationen bereits erledigt wurden.
    """
    from app.event_change_request import get_event_change_request

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] != "aenderbar_vorschlagen":
        raise EventChangeApplyError(
            f"Änderungsauftrag hat Status '{cr['status']}'. Nicht bestätigbar."
        )

    preparation = {
        "prepared_structure_path": "",
        "staged_file_count": 0,
        "staging_by_file_id": {},
        "missing_directories": [],
        "helper_directories": [],
        "release_stock": {
            "required": False,
            "prepared_file_count": 0,
            "created_directories": [],
        },
    }
    if archive_root is not None and workspace_path is not None:
        from app.archive_staging import prepare_archive_change_staging_for_request
        from app.archive_release_stock import prepare_archive_release_stock
        from app.archive_reversal import prepare_reversal_baseline
        try:
            prepare_reversal_baseline(
                database_path, archive_root, workspace_path, cr_id
            )
            staging = prepare_archive_change_staging_for_request(
                database_path, workspace_path, archive_root, cr_id
            )
            release_stock = prepare_archive_release_stock(
                database_path, workspace_path, cr_id
            )
            preparation = {**staging, "release_stock": release_stock}
        except Exception as exc:
            raise EventChangeApplyError(str(exc)) from exc

    now = _now()
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE event_change_requests SET status='aenderbar_bestaetigt', "
            "confirmed_at=?, prepared_structure_path=?, updated_at=? WHERE id=?",
            (
                now,
                str(preparation.get("prepared_structure_path") or ""),
                now,
                cr_id,
            ),
        )
        for file_id, staging_path in (preparation.get("staging_by_file_id") or {}).items():
            connection.execute(
                """UPDATE event_change_file_reviews
                   SET workspace_staging_path=?,updated_at=?
                   WHERE change_request_id=? AND file_id=?
                     AND source_root_kind='shared_workspace'""",
                (str(staging_path), now, cr_id, int(file_id)),
            )
        connection.commit()

    return {
        "status": "bestaetigt",
        "change_request_id": cr_id,
        "confirmed_at": now,
        "preparation": preparation,
        "message": "Hilfsbereiche vorbereitet. Die Kamerabibliothek wurde nicht verändert.",
    }


def cancel_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path | None = None,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Cancel directly while untouched; otherwise open a guided reversal."""

    now = _now()
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT status FROM event_change_requests WHERE id = ?", (cr_id,)
        ).fetchone()
        if row is None:
            raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
        status = str(row["status"])
        if status not in ("aenderbar_vorschlagen", "aenderbar_bestaetigt"):
            raise EventChangeApplyError(f"Status '{status}' erlaubt keinen Abbruch.")

    if status == "aenderbar_bestaetigt":
        if archive_root is None:
            raise EventChangeApplyError(
                "Ein bestätigter Archivauftrag kann nur nach Prüfung des "
                "ursprünglichen Archivzustands verworfen werden."
            )

        if workspace_path is None:
            # Kompatibler Low-Level-Weg: Ohne SSD-Kontext ist nur der direkte
            # Abbruch erlaubt, solange das Archiv nachweislich noch im IST
            # steht. Sobald manuelle Änderungen erkennbar sind, bleibt der
            # Vorgang blockiert, weil kein sicherer Rückbestand verfügbar ist.
            from app.event_change_request import get_event_change_files
            root = archive_root.expanduser().resolve(strict=False)
            reviews = get_event_change_files(database_path, cr_id)
            if not reviews:
                raise EventChangeApplyError(
                    "Der Änderungsauftrag enthält keine Dateien."
                )
            for review in reviews:
                if str(review.get("source_root_kind") or "camera_archive") == "shared_workspace":
                    raise EventChangeApplyError(
                        "Nach manuellen Änderungen benötigt der sichere Rückweg "
                        "den SSD-Arbeitsbereich."
                    )
                old_rel = str(review.get("old_path") or "")
                new_rel = str(review.get("new_path") or "")
                expected_size = int(review.get("expected_size_bytes") or 0)
                expected_sha = str(review.get("expected_sha256") or "").strip()
                if not expected_sha:
                    raise EventChangeApplyError(
                        "Abbruch gesperrt: Für mindestens eine Datei fehlt die "
                        "gespeicherte SHA-256-Summe."
                    )
                old_path = _safe_archive_path(root, old_rel)
                if (
                    not old_path.is_file()
                    or old_path.is_symlink()
                    or (expected_size and int(old_path.stat().st_size) != expected_size)
                    or _sha256_file(old_path) != expected_sha
                ):
                    raise EventChangeApplyError(
                        "Abbruch gesperrt: Nach manuellen Änderungen ist der "
                        "ursprüngliche Archivzustand nicht mehr vollständig vorhanden."
                    )
                action = str(review.get("action") or "")
                if action in {"move", "merge"} and new_rel and new_rel != old_rel:
                    new_path = _safe_archive_path(root, new_rel)
                    if new_path.exists() or new_path.is_symlink():
                        raise EventChangeApplyError(
                            "Abbruch gesperrt: Am neuen Archivpfad wurden bereits "
                            "manuelle Änderungen erkannt."
                        )
        else:
            from app.archive_reversal import (
                begin_archive_reversal,
                original_archive_state_intact,
            )
            if not original_archive_state_intact(
                database_path, archive_root, workspace_path, cr_id
            ):
                reversal = begin_archive_reversal(
                    database_path, archive_root, workspace_path, cr_id
                )
                return {
                    "status": "rueckaenderung_erforderlich",
                    "change_request_id": cr_id,
                    "reversal_required": True,
                    "reversal": reversal,
                    "message": (
                        "Im Archiv wurden bereits manuelle Änderungen erkannt. "
                        "Der ursprüngliche Zustand wird über einen Rückänderungsauftrag wiederhergestellt."
                    ),
                }

    cleanup_warnings: list[str] = []
    if workspace_path is not None:
        from app.archive_staging import cleanup_archive_change_staging
        from app.archive_release_stock import cleanup_archive_release_stock
        cleanup_archive_change_staging(
            database_path, workspace_path, cr_id, remove_originals=False
        )
        release_cleanup = cleanup_archive_release_stock(
            database_path, workspace_path, cr_id
        )
        cleanup_warnings.extend(release_cleanup.get("warnings") or [])
        try:
            from app.archive_reversal import cleanup_archive_reversal
            cleanup_archive_reversal(workspace_path, cr_id)
        except Exception:
            pass

    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE event_change_requests SET status='aenderbar_abgebrochen', "
            "cancelled_at=?,updated_at=? WHERE id=?",
            (now, now, cr_id),
        )
        connection.commit()
    return {
        "status": "abgebrochen",
        "change_request_id": cr_id,
        "reversal_required": False,
        "cleanup_warnings": cleanup_warnings,
    }

def verify_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Prüfe einen manuellen Archiv-Änderungsauftrag rein lesend."""
    from app.event_change_request import get_event_change_request, get_event_change_files

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] not in {"aenderbar_vorschlagen", "aenderbar_bestaetigt"}:
        raise EventChangeApplyError(
            f"Status '{cr['status']}' erlaubt keine Prüfung."
        )

    root = archive_root.expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise EventChangeApplyError("Die Kamerabibliothek ist nicht lesbar eingebunden.")

    if workspace_path is not None:
        from app.archive_release_stock import (
            describe_archive_release_stock,
            verify_archive_release_removal,
        )
        release_description = describe_archive_release_stock(database_path, cr_id)
        if release_description.get("required"):
            verify_archive_release_removal(
                database_path, archive_root, workspace_path, cr_id
            )

    reviews = get_event_change_files(database_path, cr_id)
    if not reviews:
        raise EventChangeApplyError("Der Änderungsauftrag enthält keine Dateien.")
    managed_reviews = [
        review for review in reviews
        if not bool(review.get("advisory"))
    ]

    now = _now()
    results: list[dict[str, Any]] = []
    advisories: list[dict[str, Any]] = []
    ok_count = 0
    open_reassignments = 0
    open_release = 0
    directory_results: list[dict[str, Any]] = []

    from app.archive_staging import (
        required_target_directories_for_request,
        required_obsolete_directories_for_request,
        required_event_document_for_request,
    )
    required_directories = required_target_directories_for_request(
        database_path, cr_id
    )
    for relative_dir in required_directories:
        target_dir = _safe_archive_path(root, relative_dir)
        exists = target_dir.is_dir()
        directory_results.append({
            "path": relative_dir,
            "status": "verified" if exists else "missing",
            "message": None if exists else "Erforderlicher SOLL-Ordner fehlt.",
        })

    obsolete_directory_results: list[dict[str, Any]] = []
    for relative_dir in required_obsolete_directories_for_request(database_path, cr_id):
        old_dir = _safe_archive_path(root, relative_dir)
        gone = not old_dir.exists()
        obsolete_directory_results.append({
            "path": relative_dir,
            "status": "verified" if gone else "still_exists",
            "message": None if gone else "Alter, nicht mehr benötigter Ordner ist noch vorhanden.",
        })

    event_document_spec_before = (
        required_event_document_for_request(database_path, cr_id)
        if workspace_path is not None
        else None
    )
    event_document_result = None
    camera_collision_path_changed = False
    collision_refresh_error = None

    def verify_event_document_spec(
        spec: dict[str, Any] | None,
        *,
        collision_refresh: bool = False,
    ) -> dict[str, Any] | None:
        if spec is None:
            return None
        relative_document = str(spec["target_relative_path"])
        target_document = _safe_archive_path(root, relative_document)
        document_status = "missing"
        document_message = "Die neue event.json fehlt am SOLL-Pfad."
        if target_document.is_file() and not target_document.is_symlink():
            actual_size = int(target_document.stat().st_size)
            if actual_size != int(spec["size_bytes"]):
                document_status = "size_mismatch"
                document_message = "Die event.json besitzt eine abweichende Dateigröße."
            elif _sha256_file(target_document) != str(spec["sha256"]):
                document_status = "sha256_mismatch"
                document_message = (
                    "Durch einen sicher erkannten Dateinamenskonflikt wurde eine "
                    "aktualisierte event.json unter Später zuordnen vorbereitet. "
                    "Bitte diese erneut ins Archiv übernehmen."
                    if collision_refresh
                    else "Die event.json entspricht nicht dem vorbereiteten SOLL-Zustand."
                )
            else:
                document_status = "verified"
                document_message = None
        return {
            "path": relative_document,
            "status": document_status,
            "message": document_message,
        }

    with database_connection(database_path) as connection:
        for review in reviews:
            action = str(review.get("action") or "")
            expected_size = int(review.get("expected_size_bytes") or 0)
            expected_sha = str(review.get("expected_sha256") or "").strip()
            old_rel = str(review.get("old_path") or "")
            new_rel = str(review.get("new_path") or "")
            source_root_kind = str(review.get("source_root_kind") or "camera_archive")

            status = "pending"
            actual_size = None
            actual_sha = None
            message = None

            release_path = str(review.get("workspace_release_path") or "").strip()
            if bool(review.get("advisory")):
                advisory_path = _safe_archive_path(root, old_rel)
                status = "advisory"
                reason = str(review.get("advisory_reason") or "")
                if reason == "redundant_duplicate":
                    message = (
                        "Byte-identische zusätzliche "
                        + str(review.get("asset_kind") or "Datei").upper()
                        + "-Kopie. Sie ist nicht erforderlich und darf liegen bleiben, "
                          "umbenannt oder gelöscht werden."
                    )
                else:
                    message = (
                        "Zusätzliche nicht verwaltete Datei im Archiv. "
                        "Sie bleibt vollständig unberührt und gehört nicht zum SOLL."
                    )
                advisories.append({
                    "path": old_rel,
                    "exists": advisory_path.is_file(),
                    "asset_kind": review.get("asset_kind"),
                    "advisory_reason": reason,
                    "message": message,
                })
            elif action == "delete" or (action == "unresolved" and release_path):
                stored_status = str(review.get("verification_status") or "pending")
                if stored_status == "verified":
                    status = "verified"
                    actual_size = review.get("actual_size_bytes")
                    actual_sha = review.get("actual_sha256")
                    ok_count += 1
                else:
                    status = stored_status
                    message = (
                        "Freigewordene Archivdatei muss zuerst vollständig auf die SSD "
                        "gesichert und anschließend aus dem Archiv entfernt werden."
                    )
                    open_release += 1
            elif action == "unresolved":
                extra_path = _safe_archive_path(root, old_rel)
                if not extra_path.exists():
                    status = "verified"
                    message = (
                        "Zusätzliche Datei wurde aus dem Ereignisordner entfernt "
                        "und besitzt deshalb kein offenes SOLL-Ziel mehr."
                    )
                else:
                    status = "needs_assignment"
                    message = (
                        "Zusätzliche Datei ohne SOLL-Ziel: "
                        + old_rel
                        + ". Datei aus dem Ereignisordner entfernen oder an einen "
                          "anderen passenden Ort verschieben und anschließend erneut prüfen."
                    )
                    open_reassignments += 1
            elif not expected_sha:
                status = "missing_sha256"
                message = "Gespeicherte SHA-256-Summe fehlt; die Archivänderung kann nicht verifiziert werden."
            else:
                target_rel = new_rel if action == "move" else (new_rel or old_rel)
                resolved_target_rel = target_rel
                review_kind = str(review.get("review_kind") or "camera")
                asset_kind = str(
                    review.get("asset_kind")
                    or ("camera_original" if review_kind != "asset" else "other")
                )
                resolved = _collision_verified_archive_target(
                    root,
                    target_rel,
                    expected_size=expected_size,
                    expected_sha=expected_sha,
                    asset_kind=asset_kind,
                )
                if resolved is None:
                    target = _safe_archive_path(root, target_rel)
                    if not target.is_file():
                        status = "missing"
                        message = "Datei fehlt am erwarteten Zielpfad."
                    else:
                        actual_size = int(target.stat().st_size)
                        actual_sha = _sha256_file(target)
                        if expected_size and actual_size != expected_size:
                            status = "size_mismatch"
                            message = "Dateigröße weicht ab."
                        elif actual_sha != expected_sha:
                            status = "sha256_mismatch"
                            message = "SHA-256-Summe weicht ab."
                        else:
                            status = "verified"
                else:
                    target, resolved_target_rel = resolved
                    actual_size = int(target.stat().st_size)
                    actual_sha = expected_sha
                    status = "verified"
                    if resolved_target_rel != target_rel:
                        message = (
                            "Datei wurde unter einem vom Dateisystem erzeugten "
                            "Kollisionsnamen erkannt und per SHA-256 bestätigt."
                        )

                if (
                    status == "verified"
                    and action == "move"
                    and source_root_kind == "camera_archive"
                    and old_rel != resolved_target_rel
                ):
                    old_target = _safe_archive_path(root, old_rel)
                    if old_target.exists():
                        status = "old_path_still_exists"
                        message = "Die Datei liegt zusätzlich noch am alten Archivpfad."

                if status == "verified" and resolved_target_rel != new_rel:
                    if review_kind != "asset":
                        camera_collision_path_changed = True
                    new_rel = resolved_target_rel

            if status == "verified" and not (
                action == "delete" or (action == "unresolved" and str(review.get("workspace_release_path") or "").strip())
            ):
                ok_count += 1

            table = (
                "event_change_asset_reviews"
                if str(review.get("review_kind") or "camera") == "asset"
                else "event_change_file_reviews"
            )
            connection.execute(
                f"""
                UPDATE {table}
                SET new_path = ?, verification_status = ?,
                    actual_size_bytes = ?, actual_sha256 = ?,
                    verified_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_rel, status, actual_size, actual_sha, now, now, review["id"]),
            )
            results.append({
                "id": review["id"],
                "file_id": review.get("file_id"),
                "family_id": review.get("family_id"),
                "asset_kind": review.get("asset_kind"),
                "review_kind": review.get("review_kind", "camera"),
                "action": action,
                "old_path": old_rel,
                "new_path": new_rel,
                "status": status,
                "message": message,
            })
        connection.commit()

    if (
        camera_collision_path_changed
        and workspace_path is not None
        and event_document_spec_before is not None
    ):
        try:
            from app.archive_staging import refresh_staged_event_document_after_verified_paths
            refresh_staged_event_document_after_verified_paths(
                database_path,
                workspace_path,
                cr_id,
                event_document_spec_before,
            )
        except Exception as exc:
            collision_refresh_error = str(exc)

    event_document_spec_current = (
        required_event_document_for_request(database_path, cr_id)
        if workspace_path is not None
        else None
    )
    event_document_result = verify_event_document_spec(
        event_document_spec_current,
        collision_refresh=camera_collision_path_changed,
    )
    if collision_refresh_error and event_document_result is not None:
        event_document_result = {
            **event_document_result,
            "status": "staging_refresh_failed",
            "message": (
                "Die neue event.json konnte nach der erkannten Dateinamensänderung "
                "nicht sicher im Hilfsbereich aktualisiert werden: "
                + collision_refresh_error
            ),
        }

    verified_directory_count = sum(
        1 for item in directory_results if item["status"] == "verified"
    )
    missing_directory_count = len(directory_results) - verified_directory_count
    remaining_obsolete_directory_count = sum(
        1 for item in obsolete_directory_results if item["status"] != "verified"
    )
    complete = (
        ok_count == len(managed_reviews)
        and open_reassignments == 0
        and open_release == 0
        and missing_directory_count == 0
        and remaining_obsolete_directory_count == 0
        and (
            event_document_result is None
            or event_document_result["status"] == "verified"
        )
    )
    return {
        "change_request_id": cr_id,
        "status": "verified" if complete else "incomplete",
        "complete": complete,
        "file_count": len(managed_reviews),
        "verified_file_count": ok_count,
        "advisory_count": len(advisories),
        "advisories": advisories,
        "open_reassignment_count": open_reassignments,
        "open_release_count": open_release,
        "directory_count": len(directory_results),
        "verified_directory_count": verified_directory_count,
        "missing_directory_count": missing_directory_count,
        "remaining_obsolete_directory_count": remaining_obsolete_directory_count,
        "files": results,
        "directories": directory_results,
        "obsolete_directories": obsolete_directory_results,
        "event_document": event_document_result,
    }


def finish_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Prüfe manuelle Dateiänderungen und schließe danach nur die DB ab.

    Es gibt absichtlich keinerlei mkdir/move/unlink/rmtree auf archive_root.
    """
    from app.event_change_request import get_event_change_request

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] != "aenderbar_bestaetigt":
        raise EventChangeApplyError(
            f"Status '{cr['status']}' erlaubt keinen Abschluss. Änderungen erst bestätigen."
        )

    verification = verify_event_change(
        database_path, cr_id, archive_root, workspace_path
    )
    if not verification["complete"]:
        raise EventChangeApplyError(
            "Die manuelle Archivänderung ist noch nicht vollständig geprüft. "
            f"{verification['verified_file_count']} von {verification['file_count']} Dateien sind korrekt; "
            f"{verification.get('open_release_count', 0)} freigewordene Dateien sind noch nicht sicher zurückgeholt; "
            f"{verification['open_reassignment_count']} weitere Dateien benötigen Klärung."
        )

    event_document_cleanup_spec = None
    if workspace_path is not None:
        try:
            from app.archive_change_document import projected_archive_event_document_spec
            event_document_cleanup_spec = projected_archive_event_document_spec(database_path, cr_id)
        except Exception:
            event_document_cleanup_spec = None

    selected_ids = sorted({int(v) for v in json.loads(cr["selected_family_ids"] or "[]")})
    delete_event = bool(cr.get("delete_event") or 0)
    if not selected_ids and not delete_event:
        with database_connection(database_path) as connection:
            asset_count = int(connection.execute(
                """SELECT COUNT(*)
                   FROM event_change_asset_reviews
                   WHERE change_request_id=?
                     AND NOT (
                         action='unresolved'
                         AND COALESCE(workspace_release_path,'')<>''
                     )""",
                (cr_id,),
            ).fetchone()[0])
        if asset_count == 0:
            raise EventChangeApplyError(
                "Das archivierte Ereignis enthält weder aktuelle Kamera- noch weitere Ereignisdateien."
            )

    start_date = str(cr["start_date"])
    end_date = str(cr["end_date"])
    event_kind = str(cr.get("event_kind") or "event")
    no_event_segments = []
    if event_kind == "no_event":
        try:
            no_event_segments = normalize_no_event_segments(json.loads(cr.get("no_event_segments") or "[]"))
        except Exception as exc:
            raise EventChangeApplyError("Die gespeicherten „Ohne Ereignis“-Zeitsegmente sind ungültig.") from exc
        if not no_event_segments:
            raise EventChangeApplyError("Für „Ohne Ereignis“ fehlt mindestens ein Zeitsegment.")
        parent_start = no_event_segments[0]["start_datetime"]
        parent_end = no_event_segments[-1]["end_datetime"]
    else:
        parent_start = f"{start_date}T00:00:00"
        parent_end = f"{end_date}T23:59:59"
    uses_time_range = bool(cr["uses_time_range"]) if event_kind != "no_event" else False
    try:
        child_segments = json.loads(cr.get("child_segments_json") or "[]") if event_kind == "event" else []
    except Exception as exc:
        raise EventChangeApplyError("Die gespeicherten Unterereignisse sind ungültig.") from exc
    start_time = str(cr["start_time"] or "00:00")
    end_time = str(cr["end_time"] or "23:59")
    child_start = f"{start_date}T{start_time}:00"
    child_end = f"{end_date}T{end_time}:59"
    if event_kind == 'event' and uses_time_range:
        parent_start, parent_end = child_start, child_end
    now = _now()

    from app.archive_release_stock import describe_archive_release_stock
    release_description = describe_archive_release_stock(database_path, cr_id)
    release_rows = list(release_description.get("rows") or [])
    release_segments = list(release_description.get("segments") or [])
    released_family_ids = sorted({
        int(row["family_id"])
        for row in release_rows
        if row.get("family_id") is not None
    })
    released_range_by_family: dict[int, tuple[str, str]] = {}
    for segment in release_segments:
        bounds = (
            str(segment.get("start_datetime") or ""),
            str(segment.get("end_datetime") or ""),
        )
        for family_id in segment.get("family_ids") or []:
            released_range_by_family[int(family_id)] = bounds

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND job_id = ?",
            (cr["event_id"], cr["job_id"]),
        ).fetchone()
        if event is None or not event["archived_at"]:
            connection.rollback()
            raise EventChangeApplyError("Das zugrunde liegende archivierte Ereignis fehlt.")

        family_jobs: dict[int, str] = {}
        if released_family_ids:
            placeholders = ",".join("?" for _ in released_family_ids)
            family_jobs = {
                int(row["id"]): str(row["job_id"])
                for row in connection.execute(
                    f"SELECT id,job_id FROM file_families WHERE id IN ({placeholders})",
                    tuple(released_family_ids),
                ).fetchall()
            }

        for row in release_rows:
            if str(row.get("verification_status") or "") != "verified":
                connection.rollback()
                raise EventChangeApplyError(
                    "Mindestens eine freigewordene Archivdatei wurde noch nicht vollständig zurückgeholt."
                )
            family_id = int(row["family_id"]) if row.get("family_id") is not None else None
            release_path = str(row.get("workspace_release_path") or "")
            if not release_path:
                connection.rollback()
                raise EventChangeApplyError("Für eine freigewordene Datei fehlt der SSD-Pfad.")
            if str(row.get("review_kind") or "camera") == "camera":
                if row.get("file_id") is None:
                    connection.rollback()
                    raise EventChangeApplyError("Für eine freigewordene Kameradatei fehlt die Datei-ID.")
                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,current_root_kind='shared_workspace',
                           sha256_current=?,updated_at=?
                       WHERE id=?""",
                    (
                        release_path,
                        str(row.get("expected_sha256") or ""),
                        now,
                        int(row["file_id"]),
                    ),
                )
            else:
                job_id = family_jobs.get(family_id) if family_id is not None else str(cr["job_id"])
                connection.execute(
                    """INSERT INTO released_archive_assets(
                           job_id,family_id,source_file_id,asset_kind,current_relative_path,
                           size_bytes,sha256,origin_change_request_id,created_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(job_id,current_relative_path) DO UPDATE SET
                           family_id=excluded.family_id,
                           source_file_id=excluded.source_file_id,
                           asset_kind=excluded.asset_kind,
                           size_bytes=excluded.size_bytes,
                           sha256=excluded.sha256,
                           origin_change_request_id=excluded.origin_change_request_id,
                           updated_at=excluded.updated_at""",
                    (
                        job_id,
                        family_id,
                        row.get("source_file_id"),
                        str(row.get("asset_kind") or "other"),
                        release_path,
                        int(row.get("expected_size_bytes") or 0),
                        str(row.get("expected_sha256") or ""),
                        cr_id,
                        now,
                        now,
                    ),
                )

        for family_id in released_family_ids:
            job_id = family_jobs.get(family_id)
            bounds = released_range_by_family.get(family_id)
            if job_id is None or bounds is None:
                connection.rollback()
                raise EventChangeApplyError(
                    "Eine freigewordene Familie besitzt keine vollständige Herkunfts-/Zeitinformation."
                )
            connection.execute(
                """INSERT OR REPLACE INTO released_free_families(
                       job_id,family_id,released_start_datetime,released_end_datetime,created_at,archive_origin
                   ) VALUES (?,?,?,?,?,1)""",
                (job_id, family_id, bounds[0], bounds[1], now),
            )

        if delete_event:
            if workspace_path is not None:
                from app.archive_staging import cleanup_archive_change_staging
                cleanup_archive_change_staging(
                    database_path,
                    workspace_path,
                    cr_id,
                    remove_originals=False,
                    event_document_spec=event_document_cleanup_spec,
                )
            connection.execute(
                """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'archived_event_deleted_after_release','event_change_request',?,?,?)""",
                (
                    cr["job_id"],
                    cr_id,
                    json.dumps({
                        "archive_read_only": True,
                        "verified_file_count": verification["verified_file_count"],
                        "released_family_ids": released_family_ids,
                        "event_id": cr["event_id"],
                    }, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            connection.execute(
                "DELETE FROM events WHERE id=? AND job_id=?",
                (cr["event_id"], cr["job_id"]),
            )
            connection.commit()
            return {
                "status": "archiviert",
                "change_request_id": cr_id,
                "archive_read_only": True,
                "files_changed_by_app": 0,
                "verified_file_count": verification["verified_file_count"],
                "event_deleted": True,
                "released_family_ids": released_family_ids,
            }

        connection.execute(
            """
            UPDATE events
            SET name = ?, start_datetime = ?, end_datetime = ?, folder_name = ?,
                event_kind = ?, preserve_day_folders = ?, notes = ?,
                revision = revision + 1, updated_at = ?, edited_at = ?
            WHERE id = ?
            """,
            (
                cr["event_name"], parent_start, parent_end, cr["parent_folder"],
                event_kind, int(bool(cr["preserve_day_folders"])),
                cr["notes"], now, now, cr["event_id"],
            ),
        )

        connection.execute("UPDATE events SET time_model_version=2 WHERE id=?", (cr['event_id'],))

        # 0.28.3: Die im Archivauftrag eingefrorene Ordnerdefinition wird erst
        # nach erfolgreicher read-only Prüfung kanonisch. Ältere/automatische
        # Aufträge ohne Layoutfelder verändern den bestehenden Zustand nicht.
        if cr.get("folder_layout_json") is not None:
            try:
                requested_layout = json.loads(str(cr.get("folder_layout_json") or "{}"))
            except Exception as exc:
                connection.rollback()
                raise EventChangeApplyError(
                    "Die gespeicherte Archiv-Ordnerstruktur ist beschädigt."
                ) from exc
            from app.event_layout import update_event_layout
            try:
                update_event_layout(
                    connection,
                    str(cr["event_id"]),
                    structure_enabled=bool(cr.get("folder_structure_enabled")),
                    input_path=str(cr.get("folder_input_path") or ""),
                    layout=requested_layout,
                    updated_at=now,
                )
            except Exception as exc:
                connection.rollback()
                raise EventChangeApplyError(
                    "Die geprüfte Archiv-Ordnerstruktur konnte nicht übernommen werden: "
                    + str(exc)
                ) from exc

        children = connection.execute(
            "SELECT * FROM events WHERE parent_event_id = ? ORDER BY start_datetime, id",
            (cr["event_id"],),
        ).fetchall()
        child = children[0] if children else None
        if event_kind == "no_event":
            assignment_event_id = str(cr["event_id"])
            if children:
                connection.execute("DELETE FROM events WHERE parent_event_id = ?", (cr["event_id"],))
            replace_event_segments(
                connection,
                event_id=str(cr["event_id"]),
                job_id=str(cr["job_id"]),
                segments=no_event_segments,
                now=now,
                source="cascade",
            )
        elif child_segments:
            connection.execute("DELETE FROM event_assignments WHERE event_id IN (SELECT id FROM events WHERE parent_event_id=?)",(cr["event_id"],))
            connection.execute("DELETE FROM events WHERE parent_event_id=?",(cr["event_id"],))
            created_children=[]
            for segment in child_segments:
                import uuid
                child_id=str(segment.get("id") or ("EVENT_"+uuid.uuid4().hex.upper()))
                seg_start=segment.get('start_datetime') or f"{start_date}T{segment['start_time']}:00"; seg_end=segment.get('end_datetime') or f"{end_date}T{segment['end_time']}:59"
                folder=str(segment.get("folder_name") or segment.get("folder") or f"{segment['start_time'].replace(':','-')} - {segment['end_time'].replace(':','-')} - {segment['name']}")
                connection.execute(
                    """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,edited_at,timeline_model)
                       VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?,'',?,'continuous')""",
                    (child_id,cr["job_id"],cr["event_id"],segment["name"],seg_start,seg_end,folder,now,now,
                     int(bool(cr["preserve_day_folders"])),event["applied_at"],event["archived_at"],now),
                )
                created_children.append((child_id,seg_start,seg_end))
            assignment_event_id=None
        elif uses_time_range and cr.get('child_folder'):
            child_name = str(cr.get("child_event_name") or "Unterereignis")
            if child is None:
                import uuid
                child_id = "EVENT_" + uuid.uuid4().hex.upper()
                connection.execute(
                    """
                    INSERT INTO events(id, job_id, parent_event_id, event_level, name,
                       start_datetime, end_datetime, uses_time_range, folder_name, status,
                       created_at, updated_at, event_kind, preserve_day_folders, revision,
                       applied_at, archived_at, notes, edited_at)
                    VALUES (?, ?, ?, 'child', ?, ?, ?, 1, ?, 'archived', ?, ?, 'event', ?, 1, ?, ?, '', ?)
                    """,
                    (child_id, cr["job_id"], cr["event_id"], child_name, child_start, child_end,
                     cr["child_folder"] or "", now, now, int(bool(cr["preserve_day_folders"])),
                     event["applied_at"], event["archived_at"], now),
                )
            else:
                child_id = str(child["id"])
                connection.execute(
                    """
                    UPDATE events SET name = ?, start_datetime = ?, end_datetime = ?,
                        folder_name = ?, preserve_day_folders = ?, revision = revision + 1,
                        updated_at = ?, edited_at = ? WHERE id = ?
                    """,
                    (child_name, child_start, child_end, cr["child_folder"] or "",
                     int(bool(cr["preserve_day_folders"])), now, now, child_id),
                )
                for extra in children[1:]:
                    connection.execute("DELETE FROM events WHERE id = ?", (extra["id"],))
            assignment_event_id = child_id
        else:
            assignment_event_id = str(cr["event_id"])
            if children:
                connection.execute("DELETE FROM events WHERE parent_event_id = ?", (cr["event_id"],))

        selected_family_rows = []
        if selected_ids:
            selected_family_rows = connection.execute(
                "SELECT id,job_id,selected_capture_time FROM file_families "
                "WHERE id IN (" + ",".join("?" for _ in selected_ids) + ")",
                tuple(selected_ids),
            ).fetchall()
        found_selected_ids = {int(row["id"]) for row in selected_family_rows}
        if found_selected_ids != set(selected_ids):
            connection.rollback()
            raise EventChangeApplyError(
                "Mindestens eine ausgewählte Dateifamilie wurde nicht mehr gefunden."
            )

        connection.execute(
            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN "
            "(SELECT id FROM events WHERE parent_event_id = ?)",
            (cr["event_id"], cr["event_id"]),
        )
        if child_segments:
            assignments = []
            for family in selected_family_rows:
                capture = str(family["selected_capture_time"] or "")[:19]
                matches = [
                    child_id
                    for child_id, range_start, range_end in created_children
                    if range_start <= capture <= range_end
                ]
                if len(matches) > 1 or (
                    not matches and int(cr.get("time_model_version", 1)) < 2
                ):
                    connection.rollback()
                    raise EventChangeApplyError(
                        "Eine archivierte Familie passt in kein eindeutiges Unterereignis."
                    )
                assignments.append(
                    (matches[0] if matches else cr["event_id"], int(family["id"]), now)
                )
            connection.executemany(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) "
                "VALUES (?,?,NULL,'date_time_range',?)",
                assignments,
            )
        else:
            connection.executemany(
                "INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at) "
                "VALUES (?, ?, NULL, 'date_time_range', ?)",
                [(assignment_event_id, family_id, now) for family_id in selected_ids],
            )

        if selected_ids:
            connection.execute(
                "DELETE FROM released_free_families WHERE archive_origin=0 AND family_id IN ("
                + ",".join("?" for _ in selected_ids) + ")",
                tuple(selected_ids),
            )
        # archive_origin=1 bleibt als Rückkehrherkunft erhalten.

        # Die Import-Herkunft bleibt an file_families.job_id/files.job_id erhalten.
        # Auch Familien aus späteren Sicherungen gehören fachlich direkt zum
        # kanonischen Archivereignis; dafür wird kein technisches Zweitereignis
        # erzeugt. Legacy-'archived_manual'-Beiträge bleiben weiterhin lesbar.

        # 0.19.0: nach erfolgreicher manueller Prüfung den tatsächlich
        # bestätigten stabilen Archivanker je Familie speichern. Alle/Sortiert/
        # Export sind bewusst nicht Teil des Ankers.
        verified_rows = connection.execute(
            """SELECT family_id,file_id,new_path FROM event_change_file_reviews
               WHERE change_request_id=? AND verification_status='verified' AND new_path<>''
               ORDER BY family_id,id""",
            (cr_id,),
        ).fetchall()
        paths_by_family: dict[int, list[str]] = {}
        for row in verified_rows:
            family_id = int(row["family_id"])
            new_path = str(row["new_path"])
            paths_by_family.setdefault(family_id, []).append(new_path)
            if row["file_id"] is not None:
                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?, current_root_kind='camera_archive', updated_at=?
                       WHERE id=?""",
                    (new_path, now, int(row["file_id"])),
                )
        for family_id, verified_paths in paths_by_family.items():
            owner = connection.execute(
                """SELECT COALESCE(parent.id,assigned.id) AS root_event_id
                   FROM event_assignments ea
                   JOIN events assigned ON assigned.id=ea.event_id
                   LEFT JOIN events parent ON parent.id=assigned.parent_event_id
                   WHERE ea.family_id=? AND assigned.status IN ('planned','applied','archived')
                   ORDER BY CASE assigned.status WHEN 'archived' THEN 0 WHEN 'applied' THEN 1 ELSE 2 END
                   LIMIT 1""",
                (family_id,),
            ).fetchone()
            if owner is not None:
                root_event_id = str(owner["root_event_id"])
                record_family_anchor(connection, root_event_id, family_id, verified_paths, now)
                family_verified_rows = [r for r in verified_rows if int(r["family_id"]) == family_id]
                for verified_row in family_verified_rows:
                    file_row = connection.execute(
                        "SELECT file_id,new_path FROM event_change_file_reviews WHERE change_request_id=? AND family_id=? AND new_path=? AND verification_status='verified' LIMIT 1",
                        (cr_id, family_id, str(verified_row["new_path"])),
                    ).fetchone()
                    if file_row is not None and file_row["file_id"] is not None:
                        record_verified_file_location(
                            connection, root_event_id, family_id, int(file_row["file_id"]),
                            str(file_row["new_path"]), now,
                        )

        connection.execute(
            "UPDATE event_change_requests SET status = 'aenderbar_archiviert', "
            "finished_at = ?, updated_at = ? WHERE id = ?",
            (now, now, cr_id),
        )
        connection.execute(
            """
            INSERT INTO audit_log(job_id, action, entity_type, entity_id, details_json, created_at)
            VALUES (?, 'event_change_verified_and_finished', 'event_change_request', ?, ?, ?)
            """,
            (
                cr["job_id"], cr_id,
                json.dumps({
                    "archive_read_only": True,
                    "verified_file_count": verification["verified_file_count"],
                    "selected_family_ids": selected_ids,
                    "released_family_ids": released_family_ids,
                }, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        connection.commit()

    ssd_cleanup = {
        "removed_staging_file_count": 0,
        "removed_original_file_count": 0,
        "removed_empty_source_directory_count": 0,
        "warnings": [],
    }
    if workspace_path is not None:
        from app.archive_staging import cleanup_archive_change_staging
        ssd_cleanup = cleanup_archive_change_staging(
            database_path,
            workspace_path,
            cr_id,
            remove_originals=True,
            event_document_spec=event_document_cleanup_spec,
        )

    released_stock_maintenance = {"updated_family_count": 0, "moved_file_count": 0, "warnings": []}
    if workspace_path is not None:
        try:
            from app.released_archive_maintenance import normalize_released_archive_stock
            occupied_ranges = (
                [
                    (str(segment["start_datetime"])[:19], str(segment["end_datetime"])[:19])
                    for segment in no_event_segments
                ]
                if event_kind == "no_event"
                else [(parent_start[:19], parent_end[:19])]
            )
            released_stock_maintenance = normalize_released_archive_stock(
                database_path, workspace_path, occupied_ranges
            )
        except Exception as exc:
            released_stock_maintenance = {
                "updated_family_count": 0,
                "moved_file_count": 0,
                "warnings": [str(exc)],
            }

    inventory_refresh_error = None
    inventory_summary = None
    try:
        refreshed = scan_event_inventory(
            database_path,
            archive_root,
            str(cr["job_id"]),
            str(cr["event_id"]),
            root_kind="camera_archive",
            persist=True,
            update_known_file_locations=True,
        )
        inventory_summary = refreshed.get("summary")
    except EventInventoryError as exc:
        # Die manuelle Änderung ist zu diesem Zeitpunkt bereits geprüft und
        # atomar in SQLite abgeschlossen. Ein nachgelagerter Inventurfehler
        # darf diesen konsistenten Abschluss nicht rückwirkend als fehlgeschlagen
        # darstellen; der nächste Bearbeitungslauf scannt ohnehin erneut.
        inventory_refresh_error = str(exc)

    return {
        "status": "archiviert",
        "change_request_id": cr_id,
        "archive_read_only": True,
        "files_changed_by_app": 0,
        "verified_file_count": verification["verified_file_count"],
        "released_family_ids": released_family_ids,
        "inventory_summary": inventory_summary,
        "inventory_refresh_error": inventory_refresh_error,
        "ssd_files_removed_by_app": int(ssd_cleanup.get("removed_original_file_count") or 0),
        "staging_files_removed_by_app": int(ssd_cleanup.get("removed_staging_file_count") or 0),
        "ssd_cleanup_warnings": list(ssd_cleanup.get("warnings") or []),
        "released_stock_maintenance": released_stock_maintenance,
    }
