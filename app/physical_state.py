from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
import json

from app.event_layout import layout_paths
from app.external_changes import record_notice, resolve_notice_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def organization_path_for_event_relative(
    event_relative_path: str,
    layout_state: dict[str, Any],
) -> str:
    """Return the configured organization path immediately before a filename."""
    raw = str(event_relative_path or "").replace("\\", "/").strip("/")
    if not raw or not bool(layout_state.get("structure_enabled")):
        return ""
    parent_parts = PurePosixPath(raw).parts[:-1]
    candidates = sorted(
        (PurePosixPath(path) for path in layout_paths(layout_state.get("layout") or {})),
        key=lambda path: (-len(path.parts), path.as_posix().casefold()),
    )
    for candidate in candidates:
        if not candidate.parts:
            continue
        if len(parent_parts) >= len(candidate.parts) and tuple(parent_parts[-len(candidate.parts):]) == candidate.parts:
            return candidate.as_posix()
    return ""


def placement_snapshot_map(
    connection: Any,
    event_id: str,
    *,
    pending_only: bool = False,
) -> dict[int, str]:
    where = " AND restore_pending=1" if pending_only else ""
    rows = connection.execute(
        f"""SELECT file_id,organization_path
            FROM event_file_placement_snapshots
            WHERE event_id=?{where}""",
        (event_id,),
    ).fetchall()
    return {int(row["file_id"]): str(row["organization_path"] or "") for row in rows}


def capture_placement_snapshot(
    connection: Any,
    event_id: str,
    layout_state: dict[str, Any],
    *,
    root_kind: str = "shared_workspace",
    restore_pending: bool = False,
    now: str | None = None,
) -> int:
    """Capture current physical organization while the old structure still exists."""
    if not bool(layout_state.get("structure_enabled")):
        return 0
    timestamp = now or _now()
    rows = [
        {
            "known_file_id": int(row["known_file_id"]),
            "event_relative_path": str(row["event_relative_path"] or ""),
        }
        for row in connection.execute(
            """SELECT known_file_id,event_relative_path
               FROM event_inventory_files
               WHERE event_id=? AND root_kind=? AND known_file_id IS NOT NULL
               ORDER BY known_file_id""",
            (event_id, root_kind),
        ).fetchall()
    ]
    if not rows:
        event = connection.execute(
            "SELECT start_datetime,folder_name FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
        if event is not None:
            prefix = PurePosixPath(
                str(event["start_datetime"] or "")[:4],
                str(event["folder_name"] or ""),
            )
            fallback = connection.execute(
                """SELECT DISTINCT f.id,f.current_relative_path
                   FROM files f
                   JOIN event_assignments ea ON ea.family_id=f.family_id OR ea.file_id=f.id
                   JOIN events assigned ON assigned.id=ea.event_id
                   WHERE COALESCE(assigned.parent_event_id,assigned.id)=?
                     AND f.current_relative_path IS NOT NULL
                   ORDER BY f.id""",
                (event_id,),
            ).fetchall()
            for row in fallback:
                path = PurePosixPath(str(row["current_relative_path"] or ""))
                try:
                    rel = path.relative_to(prefix)
                except ValueError:
                    continue
                rows.append({
                    "known_file_id": int(row["id"]),
                    "event_relative_path": rel.as_posix(),
                })

    captured = 0
    for row in rows:
        file_id = int(row["known_file_id"])
        organization = organization_path_for_event_relative(
            str(row["event_relative_path"] or ""),
            layout_state,
        )
        connection.execute(
            """INSERT INTO event_file_placement_snapshots(
                   event_id,file_id,organization_path,restore_pending,captured_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(event_id,file_id) DO UPDATE SET
                   organization_path=excluded.organization_path,
                   restore_pending=excluded.restore_pending,
                   captured_at=excluded.captured_at""",
            (event_id, file_id, organization, int(bool(restore_pending)), timestamp),
        )
        captured += 1
    return captured


def mark_placement_restore_pending(
    connection: Any,
    event_id: str,
    pending: bool,
) -> int:
    cursor = connection.execute(
        """UPDATE event_file_placement_snapshots
           SET restore_pending=?
           WHERE event_id=?""",
        (int(bool(pending)), event_id),
    )
    return int(cursor.rowcount or 0)


def clear_placement_restore(
    connection: Any,
    event_id: str,
) -> None:
    connection.execute(
        "DELETE FROM event_file_placement_snapshots WHERE event_id=?",
        (event_id,),
    )


def sync_placement_moves(
    connection: Any,
    event: dict[str, Any],
    layout_state: dict[str, Any],
    root_kind: str,
    file_moves: list[dict[str, Any]],
    *,
    now: str | None = None,
) -> int:
    """Adopt user file moves that do not change the known directory structure."""
    timestamp = now or _now()
    count = 0
    for move in file_moves:
        file_id = int(move["file_id"])
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,current_root_kind=?,updated_at=?
               WHERE id=?""",
            (str(move["new_path"]), root_kind, timestamp, file_id),
        )
        count += 1


    if count:
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'event_file_placements_observed','event',?,?,?)""",
            (
                str(event["job_id"]),
                str(event["id"]),
                json.dumps(
                    {
                        "root_kind": root_kind,
                        "file_count": count,
                        "moves": [
                            {
                                "file_id": int(move["file_id"]),
                                "old_path": str(move["old_path"]),
                                "new_path": str(move["new_path"]),
                            }
                            for move in file_moves
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                timestamp,
            ),
        )
    return count


def reconcile_missing_files(
    connection: Any,
    event: dict[str, Any],
    root_kind: str,
    missing_file_ids: list[int],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Require two consecutive complete scans before accepting a deletion."""
    timestamp = now or _now()
    event_id = str(event["id"])
    missing = {int(value) for value in missing_file_ids}

    prior_rows = connection.execute(
        """SELECT file_id,consecutive_misses
           FROM event_missing_file_observations
           WHERE event_id=? AND root_kind=?""",
        (event_id, root_kind),
    ).fetchall()
    prior = {int(row["file_id"]): int(row["consecutive_misses"] or 0) for row in prior_rows}

    # Reappeared files immediately clear the provisional missing state.
    for file_id in set(prior) - missing:
        connection.execute(
            """DELETE FROM event_missing_file_observations
               WHERE event_id=? AND root_kind=? AND file_id=?""",
            (event_id, root_kind, file_id),
        )
        resolve_notice_key(
            connection,
            f"placement:{file_id}",
            now=timestamp,
        )
        resolve_notice_key(
            connection,
            f"cross-event:{event_id}:{file_id}",
            now=timestamp,
        )

    confirmed: list[int] = []
    pending: list[int] = []
    for file_id in sorted(missing):
        file_identity = connection.execute(
            """SELECT f.id,f.job_id,f.family_id,f.original_filename,
                      f.current_relative_path,f.current_root_kind,
                      f.size_bytes,
                      COALESCE(f.sha256_current,f.sha256_original,'') AS sha256
               FROM files f
               WHERE f.id=?""",
            (file_id,),
        ).fetchone()

        if (
            file_identity is not None
            and str(file_identity["current_root_kind"] or "") == "trash"
        ):
            connection.execute(
                """DELETE FROM event_missing_file_observations
                   WHERE event_id=? AND root_kind=? AND file_id=?""",
                (event_id, root_kind, file_id),
            )
            resolve_notice_key(connection, f"placement:{file_id}", now=timestamp)
            resolve_notice_key(
                connection,
                f"cross-event:{event_id}:{file_id}",
                now=timestamp,
            )
            continue

        cross_matches = []
        if file_identity is not None and str(file_identity["sha256"] or ""):
            cross_matches = connection.execute(
                """SELECT inv.event_id,inv.root_kind,inv.relative_path,
                          inv.filename,e.name AS event_name
                   FROM event_inventory_files inv
                   JOIN events e ON e.id=inv.event_id
                   WHERE (inv.event_id<>? OR inv.root_kind<>?)
                     AND inv.size_bytes=?
                     AND inv.sha256=?
                     AND inv.filename=?
                   ORDER BY inv.root_kind,inv.event_id,inv.relative_path""",
                (
                    event_id,
                    root_kind,
                    int(file_identity["size_bytes"] or 0),
                    str(file_identity["sha256"]),
                    str(file_identity["original_filename"] or ""),
                ),
            ).fetchall()

        if cross_matches:
            unique = {
                (
                    str(row["root_kind"]),
                    str(row["event_id"]),
                    str(row["relative_path"]),
                ): dict(row)
                for row in cross_matches
            }
            matches = list(unique.values())

            # Ein vollständig aus dem angewendeten Arbeitsbestand ins Archiv
            # verschobenes Ereignis ist kein Zuordnungsfehler. Es wird als
            # mögliche manuelle Archivübernahme angeboten und erst nach
            # SHA-Prüfung fachlich abgeschlossen.
            archive_same_event = [
                row
                for row in matches
                if (
                    root_kind == "shared_workspace"
                    and str(row["root_kind"]) == "camera_archive"
                    and str(row["event_id"]) == event_id
                )
            ]
            if len(archive_same_event) == 1:
                observed = archive_same_event[0]
                connection.execute(
                    """DELETE FROM event_missing_file_observations
                       WHERE event_id=? AND root_kind=? AND file_id=?""",
                    (event_id, root_kind, file_id),
                )
                record_notice(
                    connection,
                    notice_key=f"archive-transfer:{event_id}",
                    kind="archive_transfer_candidate",
                    root_kind="camera_archive",
                    title="Mögliche Archivübernahme erkannt",
                    detail=(
                        f"Für „{event.get('name') or event_id}“ wurden Dateien "
                        "aus dem Arbeitsbereich im Archiv wiedergefunden. "
                        "Bitte den Archivbestand prüfen."
                    ),
                    job_id=str(file_identity["job_id"]),
                    event_id=event_id,
                    file_id=None,
                    relative_path=str(observed.get("relative_path") or ""),
                    repairable=False,
                    action_required=False,
                    group_key="archive_candidate",
                    details={
                        "event_id": event_id,
                        "job_id": str(file_identity["job_id"]),
                        "event_name": str(event.get("name") or ""),
                    },
                    now=timestamp,
                )
                pending.append(file_id)
                continue

            if len(matches) == 1:
                observed = matches[0]
                observed_kind = str(observed["root_kind"])
                observed_path = str(observed["relative_path"])
                expected_path = str(
                    file_identity["current_relative_path"] or ""
                )
                expected_kind = str(
                    file_identity["current_root_kind"]
                    or root_kind
                )

                # 0.41.4: Nach der ersten Fremdverschiebung folgt SQLite
                # bewusst dem beobachteten physischen IST. Der fachliche
                # Sollpfad darf dadurch bei einem weiteren Reload/Reconcile
                # aber nicht verloren gehen. Ein bereits offener eindeutiger
                # placement_conflict ist deshalb die persistente Sollpfad-
                # Erinnerung, bis die Zuordnung wirklich wieder stimmt.
                prior_conflict = connection.execute(
                    """SELECT details_json
                       FROM external_change_notices
                       WHERE notice_key=?
                         AND status='open'
                         AND action_required=1
                       LIMIT 1""",
                    (f"placement:{file_id}",),
                ).fetchone()
                if prior_conflict is not None:
                    try:
                        prior_details = json.loads(
                            str(prior_conflict["details_json"] or "{}")
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        prior_details = {}
                    prior_expected_path = str(
                        prior_details.get("expected_relative_path") or ""
                    ).strip()
                    prior_expected_kind = str(
                        prior_details.get("expected_root_kind") or ""
                    ).strip()
                    if prior_expected_path:
                        expected_path = prior_expected_path
                    if prior_expected_kind:
                        expected_kind = prior_expected_kind

                detail = (
                    f"{file_identity['original_filename']} wurde aus "
                    f"„{event.get('name') or event_id}“ nach "
                    f"„{observed.get('event_name') or observed.get('event_id')}“ "
                    "verschoben, ohne dass die fachliche Zuordnung geändert wurde."
                )
                if (
                    observed_kind == "camera_archive"
                    or expected_kind == "camera_archive"
                ):
                    detail += (
                        " Das Archiv ist schreibgeschützt; die Datei muss "
                        "manuell an einen fachlich passenden Ort zurück."
                    )
                record_notice(
                    connection,
                    notice_key=f"placement:{file_id}",
                    kind="placement_conflict",
                    root_kind=observed_kind,
                    title="Datei falsch zugeordnet",
                    detail=detail,
                    job_id=str(file_identity["job_id"]),
                    event_id=event_id,
                    file_id=file_id,
                    relative_path=observed_path,
                    repairable=(
                        observed_kind != "camera_archive"
                        and expected_kind != "camera_archive"
                    ),
                    action_required=True,
                    group_key="placement_conflict",
                    details={
                        "source_event_id": event_id,
                        "target_event_id": str(observed.get("event_id") or ""),
                        "target_event_name": str(observed.get("event_name") or ""),
                        "expected_root_kind": expected_kind,
                        "observed_root_kind": observed_kind,
                        "expected_relative_path": expected_path,
                        "observed_relative_path": observed_path,
                        "size_bytes": int(file_identity["size_bytes"] or 0),
                        "sha256": str(file_identity["sha256"] or ""),
                    },
                    now=timestamp,
                )
                # SQLite folgt dem realen IST, die fachliche Abweichung bleibt
                # separat als offene Aufgabe erhalten.
                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,
                           current_root_kind=?,
                           updated_at=?
                       WHERE id=?""",
                    (
                        observed_path,
                        observed_kind,
                        timestamp,
                        file_id,
                    ),
                )
                connection.execute(
                    """DELETE FROM event_missing_file_observations
                       WHERE event_id=? AND root_kind=? AND file_id=?""",
                    (event_id, root_kind, file_id),
                )
                pending.append(file_id)
                continue

            # Mehrere identische physische Kandidaten: nicht löschen und nicht
            # automatisch entscheiden.
            first = matches[0]
            record_notice(
                connection,
                notice_key=f"placement:{file_id}",
                kind="placement_conflict",
                root_kind=str(first["root_kind"]),
                title="Dateiposition ist mehrdeutig",
                detail=(
                    f"{file_identity['original_filename']} fehlt am erwarteten "
                    "Ort; mehrere byte-identische Positionen wurden gefunden."
                ),
                job_id=str(file_identity["job_id"]),
                event_id=event_id,
                file_id=file_id,
                relative_path=str(first["relative_path"]),
                repairable=False,
                action_required=True,
                group_key="placement_conflict",
                details={
                    "expected_root_kind": str(
                        file_identity["current_root_kind"] or root_kind
                    ),
                    "observed_root_kind": str(first["root_kind"]),
                    "expected_relative_path": str(
                        file_identity["current_relative_path"] or ""
                    ),
                    "observed_relative_path": str(first["relative_path"]),
                    "candidate_paths": [
                        {
                            "root_kind": str(row["root_kind"]),
                            "event_id": str(row["event_id"]),
                            "relative_path": str(row["relative_path"]),
                        }
                        for row in matches
                    ],
                    "size_bytes": int(file_identity["size_bytes"] or 0),
                    "sha256": str(file_identity["sha256"] or ""),
                },
                now=timestamp,
            )
            pending.append(file_id)
            continue

        # Ein Konflikt kann in einem anderen verwalteten Bereich (z. B.
        # Tagesbestand) bereits erkannt worden sein. Solange er offen ist,
        # darf die fehlende Ereignisdatei nicht als echte Löschung verbucht
        # werden.
        active_conflict = connection.execute(
            """SELECT 1 FROM external_change_notices
               WHERE notice_key=? AND status='open' AND action_required=1
               LIMIT 1""",
            (f"placement:{file_id}",),
        ).fetchone()
        if active_conflict is not None:
            pending.append(file_id)
            continue

        resolve_notice_key(
            connection,
            f"cross-event:{event_id}:{file_id}",
            now=timestamp,
        )
        count = prior.get(file_id, 0) + 1
        if file_id in prior:
            connection.execute(
                """UPDATE event_missing_file_observations
                   SET consecutive_misses=?,last_missing_at=?
                   WHERE event_id=? AND root_kind=? AND file_id=?""",
                (count, timestamp, event_id, root_kind, file_id),
            )
        else:
            connection.execute(
                """INSERT INTO event_missing_file_observations(
                       event_id,root_kind,file_id,consecutive_misses,
                       first_missing_at,last_missing_at)
                   VALUES (?,?,?,1,?,?)""",
                (event_id, root_kind, file_id, timestamp, timestamp),
            )

        if count < 2:
            pending.append(file_id)
            continue

        file_row = connection.execute(
            """SELECT f.*,ff.family_key
               FROM files f LEFT JOIN file_families ff ON ff.id=f.family_id
               WHERE f.id=?""",
            (file_id,),
        ).fetchone()
        if file_row is None:
            confirmed.append(file_id)
            continue
        # Never remove a shared file/family record merely because this
        # event's directory has disappeared. A foreign event's assignment
        # is an independent ownership claim, even if its inventory has not
        # been refreshed yet (for example after a manual move).
        foreign_owner = connection.execute(
            """SELECT 1 FROM event_assignments ea
               JOIN events assigned ON assigned.id=ea.event_id
               WHERE (ea.file_id=? OR (ea.family_id=? AND ea.family_id IS NOT NULL))
                 AND COALESCE(assigned.parent_event_id,assigned.id)<>?
               LIMIT 1""",
            (file_id, file_row["family_id"], event_id),
        ).fetchone()
        if foreign_owner is not None:
            record_notice(
                connection,
                notice_key=f"placement:{file_id}",
                kind="placement_conflict",
                root_kind=root_kind,
                title="Gemeinsam zugeordnete Datei fehlt",
                detail=(
                    f"{file_row['original_filename']} wird auch von einem anderen "
                    "Ereignis verwendet. Eine automatische Löschbestätigung "
                    "ist ohne eindeutige Prüfung der Zuordnung nicht zulässig."
                ),
                job_id=str(file_row["job_id"]),
                event_id=event_id,
                file_id=file_id,
                relative_path=str(file_row["current_relative_path"] or ""),
                repairable=False,
                action_required=True,
                group_key="placement_conflict",
                details={
                    "expected_root_kind": root_kind,
                    "expected_relative_path": str(file_row["current_relative_path"] or ""),
                    "size_bytes": int(file_row["size_bytes"] or 0),
                    "sha256": str(file_row["sha256_current"] or file_row["sha256_original"] or ""),
                    "force_repair": True,
                },
                now=timestamp,
            )
            pending.append(file_id)
            continue

        details = {
            "file_id": file_id,
            "family_id": int(file_row["family_id"]) if file_row["family_id"] is not None else None,
            "family_key": str(file_row["family_key"] or ""),
            "original_relative_path": str(file_row["original_relative_path"] or ""),
            "sha256_original": str(file_row["sha256_original"] or ""),
            "source_size_bytes": int(file_row["source_size_bytes"] if file_row["source_size_bytes"] is not None else file_row["size_bytes"]),
            "filename": str(file_row["original_filename"] or ""),
            "last_relative_path": str(file_row["current_relative_path"] or ""),
            "sha256": str(file_row["sha256_current"] or file_row["sha256_original"] or ""),
            "root_kind": root_kind,
            "confirmed_after_scans": count,
        }
        family_id = int(file_row["family_id"]) if file_row["family_id"] is not None else None
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'manual_file_deletion_confirmed','file',?,?,?)""",
            (
                str(file_row["job_id"]),
                str(file_id),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.execute("DELETE FROM files WHERE id=?", (file_id,))
        if family_id is not None:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM files WHERE family_id=?",
                (family_id,),
            ).fetchone()[0]
            if int(remaining or 0) == 0:
                connection.execute("DELETE FROM file_families WHERE id=?", (family_id,))
        confirmed.append(file_id)

    return {"pending": pending, "confirmed_deleted": confirmed}
