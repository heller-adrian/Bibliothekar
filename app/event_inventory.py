from __future__ import annotations

from app.root_operations import protect, validate_active_roots



from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat
import re

from app.database import database_connection
from app.metadata import MetadataError, analyze_tree, classify_media
from app.filename_collisions import collision_alias_stems, export_collision_base_stem
from app.event_layout import ensure_event_layout_snapshot, layout_role_paths
from app.physical_state import organization_path_for_event_relative


SORT_BRANCHES = {"Alle", "Sortiert", "All", "Sorted", "Export"}
IGNORED_EVENT_FILES = {"event.json", ".DS_Store"}


class EventInventoryError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    validate_active_roots()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    validate_active_roots()
    raw = str(value or "").strip().replace("\\", "/").strip("/")
    path = PurePosixPath(raw)
    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise EventInventoryError("Unsicherer Ereignispfad: " + raw)
    return path


def event_root_relative(event: dict[str, Any]) -> PurePosixPath:
    start = str(event.get("start_datetime") or "")
    year = start[:4]
    folder = str(event.get("folder_name") or "").strip()
    if len(year) != 4 or not year.isdigit() or not folder:
        raise EventInventoryError(
            "Ereignis besitzt keinen eindeutigen Jahres-/Ordnerpfad."
        )
    return _safe_relative(PurePosixPath(year, folder).as_posix())


def _discover_event_prefix_by_document(
    root: Path,
    expected_prefix: PurePosixPath,
    event_id: str,
) -> PurePosixPath:
    """Find a manually renamed event root by its stable event.json identity."""
    expected_root = root.joinpath(*expected_prefix.parts)
    if expected_root.exists():
        return expected_prefix
    if not expected_prefix.parts:
        return expected_prefix

    year_root = root / expected_prefix.parts[0]
    if not year_root.is_dir() or year_root.is_symlink():
        return expected_prefix

    matches: list[PurePosixPath] = []
    try:
        candidates = sorted(year_root.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return expected_prefix

    for candidate in candidates:
        if not candidate.is_dir() or candidate.is_symlink():
            continue
        document = candidate / "event.json"
        if not document.is_file() or document.is_symlink():
            continue
        try:
            payload = json.loads(document.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        document_event = payload.get("event") or {}
        if str(document_event.get("id") or "") != str(event_id):
            continue
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        matches.append(PurePosixPath(relative.as_posix()))

    return matches[0] if len(matches) == 1 else expected_prefix


def _event_and_known_files(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with database_connection(database_path) as connection:
        event = connection.execute(
            """SELECT * FROM events
               WHERE id=? AND parent_event_id IS NULL""",
            (event_id,),
        ).fetchone()
        if event is None:
            raise EventInventoryError("Ereignis wurde nicht gefunden.")

        rows = connection.execute(
            """
            WITH RECURSIVE event_tree AS (
                SELECT id FROM events
                WHERE id=?
                   OR (linked_event_id=? AND linkage_kind='archived_manual' AND status='archived')
                UNION ALL
                SELECT child.id
                FROM events child
                JOIN event_tree parent ON child.parent_event_id=parent.id
            ),
            assigned_families AS (
                SELECT DISTINCT family_id
                FROM event_assignments
                WHERE event_id IN (SELECT id FROM event_tree)
                  AND family_id IS NOT NULL

                UNION

                SELECT DISTINCT family_id
                FROM event_reapply_removed_families
                WHERE event_id=?
            ),
            assigned_files AS (
                SELECT DISTINCT file_id
                FROM event_assignments
                WHERE event_id IN (SELECT id FROM event_tree)
                  AND file_id IS NOT NULL
            )
            SELECT DISTINCT
                f.id AS file_id,
                f.family_id,
                f.original_filename,
                f.current_relative_path,
                f.original_relative_path,
                f.size_bytes,
                f.sha256_current,
                f.sha256_original,
                f.selected_capture_time,
                ff.original_stem,
                ff.family_key
            FROM files f
            LEFT JOIN file_families ff
              ON ff.id=f.family_id AND ff.job_id=f.job_id
            WHERE (
                    f.family_id IN (SELECT family_id FROM assigned_families)
                    OR f.id IN (SELECT file_id FROM assigned_files)
                  )
            ORDER BY f.id
            """,
            (event_id, event_id, event_id),
        ).fetchall()
    return dict(event), [dict(row) for row in rows]


def _iter_regular_event_files(event_root: Path) -> list[Path]:
    if not event_root.exists() or not event_root.is_dir():
        raise EventInventoryError(
            "Ereignisordner wurde nicht gefunden: " + str(event_root)
        )

    result: list[Path] = []
    for current, directories, files in os.walk(event_root, topdown=True, followlinks=False):
        current_path = Path(current)

        safe_directories: list[str] = []
        for name in directories:
            child = current_path / name
            info = os.lstat(child)
            if stat.S_ISLNK(info.st_mode):
                raise EventInventoryError(
                    "Symlinks sind innerhalb eines Ereignisses nicht zulässig: "
                    + str(child.relative_to(event_root))
                )
            if not stat.S_ISDIR(info.st_mode):
                raise EventInventoryError(
                    "Unerwarteter Verzeichniseintrag im Ereignis: "
                    + str(child.relative_to(event_root))
                )
            safe_directories.append(name)
        directories[:] = safe_directories

        for name in files:
            if name in IGNORED_EVENT_FILES or name.startswith("._"):
                continue
            path = current_path / name
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                raise EventInventoryError(
                    "Symlinks sind innerhalb eines Ereignisses nicht zulässig: "
                    + str(path.relative_to(event_root))
                )
            if not stat.S_ISREG(info.st_mode):
                raise EventInventoryError(
                    "Unerwarteter Dateieintrag im Ereignis: "
                    + str(path.relative_to(event_root))
                )
            result.append(path)

    result.sort(key=lambda p: p.relative_to(event_root).as_posix())
    return result


def _iter_regular_event_directories(event_root: Path) -> list[Path]:
    """Return the actual directory tree, including empty directories."""
    if not event_root.exists() or not event_root.is_dir():
        raise EventInventoryError(
            "Ereignisordner wurde nicht gefunden: " + str(event_root)
        )
    result: list[Path] = []
    for current, directories, _files in os.walk(event_root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe: list[str] = []
        for name in directories:
            child = current_path / name
            info = os.lstat(child)
            if stat.S_ISLNK(info.st_mode):
                raise EventInventoryError(
                    "Symlinks sind innerhalb eines Ereignisses nicht zulässig: "
                    + str(child.relative_to(event_root))
                )
            if not stat.S_ISDIR(info.st_mode):
                raise EventInventoryError(
                    "Unerwarteter Verzeichniseintrag im Ereignis: "
                    + str(child.relative_to(event_root))
                )
            safe.append(name)
            result.append(child)
        directories[:] = safe
    result.sort(key=lambda p: p.relative_to(event_root).as_posix())
    return result


def _branch_for(event_relative_path: str) -> str:
    for part in PurePosixPath(event_relative_path).parts[:-1]:
        if part in SORT_BRANCHES:
            return part
    return ""


def _asset_kind(
    event_relative_path: str,
    media_type: str,
    known_file_id: int | None,
    *,
    declared_export: bool = False,
    previous_asset_kind: str | None = None,
) -> str:
    if known_file_id is not None:
        return "camera_original"
    if media_type == "xmp":
        return "xmp"
    if media_type in {"jpeg", "image"}:
        stem = Path(str(event_relative_path or "")).stem
        # 0.28.5: A normal image is not automatically an export. Positive
        # evidence is required: configured export role, explicit _Export
        # naming or an already observed export identity. A later unique
        # camera-family match may still promote derived_media to export.
        if (
            declared_export
            or export_collision_base_stem(stem) is not None
            or str(previous_asset_kind or "") == "export"
        ):
            return "export"
        return "derived_media"
    if media_type in {"raw", "video"}:
        return "derived_media"
    return "other"


_FILENAME_SCHEMA_RE = re.compile(
    r"(?<!\d)(?P<date>20\d{6})[_-](?P<time>\d{6})(?!\d)"
)
def _filename_schema_capture_time(filename: str) -> str | None:
    """Read the canonical JJJJMMTT_HHMMSS timestamp from an export name."""
    match = _FILENAME_SCHEMA_RE.search(Path(str(filename or "")).stem)
    if match is None:
        return None
    value = match.group("date") + match.group("time")
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return parsed.isoformat(timespec="seconds")


def _filename_family_source(
    filename: str,
    known_files: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Conservatively match an export name to exactly one imported family.

    Besides the imported camera stem, current canonical filenames and common
    Finder/Windows duplicate suffixes are considered. This matters after a
    manual archive merge where either the camera JPEG or the export may have
    been renamed to e.g. "Kopie", "copy 2" or "(1)".
    """
    observed_stem = Path(str(filename or "")).stem
    export_aliases = collision_alias_stems(
        observed_stem,
        allow_plain_number=True,
        include_export_base=True,
    )
    if not export_aliases:
        return None

    by_family: dict[int, dict[str, Any]] = {}
    for row in known_files:
        if row.get("family_id") is None:
            continue

        known_stems: set[str] = set()
        for value in (
            row.get("original_stem"),
            Path(str(row.get("original_filename") or "")).stem,
            Path(str(row.get("current_relative_path") or "")).stem,
            Path(str(row.get("original_relative_path") or "")).stem,
        ):
            value = str(value or "").strip()
            if not value:
                continue
            known_stems.update(collision_alias_stems(value))

        matched = False
        for known_stem in known_stems:
            if len(known_stem) < 3:
                continue
            token_pattern = re.compile(
                rf"(^|[ _.-]){re.escape(known_stem)}($|[ _.-])"
            )
            if any(
                alias == known_stem or token_pattern.search(alias)
                for alias in export_aliases
            ):
                matched = True
                break
        if matched:
            by_family.setdefault(int(row["family_id"]), row)

    if len(by_family) != 1:
        return None
    return next(iter(by_family.values()))


def _capture_seconds_apart(left: str | None, right: str | None) -> float | None:
    try:
        a = datetime.fromisoformat(str(left or ""))
        b = datetime.fromisoformat(str(right or ""))
        if a.tzinfo is not None:
            validate_active_roots()
            a = a.astimezone(timezone.utc).replace(tzinfo=None)
        if b.tzinfo is not None:
            validate_active_roots()
            b = b.astimezone(timezone.utc).replace(tzinfo=None)
        return abs((a - b).total_seconds())
    except (TypeError, ValueError):
        return None


def _best_known_match(
    *,
    sha256: str,
    size_bytes: int,
    filename: str,
    known_files: list[dict[str, Any]],
    used_file_ids: set[int],
) -> dict[str, Any] | None:
    candidates = [
        row for row in known_files
        if int(row["file_id"]) not in used_file_ids
        and int(row.get("size_bytes") or 0) == int(size_bytes)
        and sha256 in {
            str(row.get("sha256_current") or "").strip(),
            str(row.get("sha256_original") or "").strip(),
        }
    ]
    if not candidates:
        return None
    exact_name = [
        row for row in candidates
        if filename == str(row.get("original_filename") or "")
        or filename == Path(str(row.get("current_relative_path") or "")).name
        or filename == Path(str(row.get("original_relative_path") or "")).name
    ]
    if len(exact_name) == 1:
        return exact_name[0]

    # A filesystem collision may rename the camera original itself. SHA/size
    # remain authoritative; the copy suffix is only a conservative tie-breaker
    # if otherwise multiple identical known files are possible.
    observed_aliases = collision_alias_stems(
        Path(str(filename or "")).stem,
        allow_plain_number=True,
    )
    collision_name = []
    for row in candidates:
        candidate_aliases: set[str] = set()
        for value in (
            row.get("original_filename"),
            Path(str(row.get("current_relative_path") or "")).name,
            Path(str(row.get("original_relative_path") or "")).name,
        ):
            stem = Path(str(value or "")).stem
            if stem:
                candidate_aliases.update(
                    collision_alias_stems(stem, allow_plain_number=True)
                )
        if observed_aliases & candidate_aliases:
            collision_name.append(row)
    if len(collision_name) == 1:
        return collision_name[0]

    if len(candidates) == 1:
        return candidates[0]
    return None


@protect(workspace_arg='storage_root', database_arg='database_path', kind='inventory', error_type=EventInventoryError)
def scan_event_inventory(
    database_path: Path,
    storage_root: Path,
    job_id: str,
    event_id: str,
    *,
    root_kind: str,
    persist: bool = True,
    update_known_file_locations: bool = False,
    event_prefix_override: str | PurePosixPath | None = None,
    fast_refresh: bool = False,
    allow_missing_root: bool = False,
) -> dict[str, Any]:
    """Scan the *current* event tree.

    This snapshot is intentionally observational. It is replaced wholesale on
    every scan and therefore never turns a later manual archive deletion into
    an integrity error by itself.
    """
    if root_kind not in {"shared_workspace", "camera_archive"}:
        raise EventInventoryError("Ungültige Ereigniswurzel: " + root_kind)

    event, known_files = _event_and_known_files(database_path, job_id, event_id)

    layout_state: dict[str, Any] | None = None
    previous_kind_by_content: dict[tuple[int, str], str] = {}
    with database_connection(database_path) as connection:
        try:
            layout_state = ensure_event_layout_snapshot(
                connection,
                event_id,
                now=_now(),
            )
        except Exception:
            layout_state = None
        try:
            previous_rows = connection.execute(
                """SELECT size_bytes,sha256,asset_kind
                   FROM event_inventory_files
                   WHERE event_id=? AND root_kind=?""",
                (event_id, root_kind),
            ).fetchall()
            grouped_previous: dict[tuple[int, str], set[str]] = {}
            for row in previous_rows:
                key = (int(row["size_bytes"] or 0), str(row["sha256"] or ""))
                if key[1]:
                    grouped_previous.setdefault(key, set()).add(str(row["asset_kind"] or ""))
            for key, kinds in grouped_previous.items():
                if "export" in kinds:
                    previous_kind_by_content[key] = "export"
        except Exception:
            previous_kind_by_content = {}

    export_role_paths = set(
        layout_role_paths(layout_state["layout"], "export")
        if layout_state is not None and bool(layout_state.get("structure_enabled"))
        else []
    )

    def declared_export_for(relative_path: str) -> bool:
        if not export_role_paths or layout_state is None:
            return False
        organization = organization_path_for_event_relative(
            relative_path,
            layout_state,
        )
        return any(
            organization == role_path or organization.startswith(role_path + "/")
            for role_path in export_role_paths
        )

    root = storage_root.expanduser().resolve(strict=False)
    prefix = (
        _safe_relative(str(event_prefix_override))
        if event_prefix_override is not None
        else event_root_relative(event)
    )
    prefix = _discover_event_prefix_by_document(
        root,
        prefix,
        event_id,
    )
    event_root = root.joinpath(*prefix.parts)

    try:
        event_root.relative_to(root)
    except ValueError as exc:
        raise EventInventoryError("Ereignisordner verlässt die Speicherwurzel.") from exc

    # Reject symlinks in the event-root path before any recursive metadata pass.
    current = root
    for part in prefix.parts:
        current = current / part
        if current.is_symlink():
            raise EventInventoryError(
                "Symlinks sind als Ereignisordner nicht zulässig: "
                + current.relative_to(root).as_posix()
            )
        if not current.exists():
            continue
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode):
            raise EventInventoryError(
                "Symlinks sind als Ereignisordner nicht zulässig: "
                + current.relative_to(root).as_posix()
            )

    # The normal inventory contract remains strict. Only the passive live
    # consistency scan may treat a *genuinely absent* event directory as an
    # empty physical inventory. Never confuse an unavailable storage root,
    # a broken symlink or a non-directory with an intentional deletion.
    event_root_missing = not event_root.exists()
    if event_root_missing and allow_missing_root:
        if not root.is_dir() or root.is_symlink() or event_root.is_symlink():
            raise EventInventoryError(
                "Ereignisspeicher ist nicht sicher erreichbar: " + str(root)
            )
        physical_files: list[Path] = []
        physical_directories: list[Path] = []
    else:
        physical_files = _iter_regular_event_files(event_root)
        physical_directories = _iter_regular_event_directories(event_root)

    previous_by_relative: dict[str, dict[str, Any]] = {}
    known_by_current_relative: dict[str, dict[str, Any]] = {}
    if fast_refresh:
        with database_connection(database_path) as connection:
            previous_rows = connection.execute(
                """SELECT relative_path,size_bytes,sha256,known_file_id,family_id
                   FROM event_inventory_files
                   WHERE event_id=? AND root_kind=?""",
                (event_id, root_kind),
            ).fetchall()
        previous_by_relative = {
            str(row["relative_path"]): dict(row)
            for row in previous_rows
        }
        known_by_current_relative = {
            str(item.get("current_relative_path") or ""): item
            for item in known_files
            if str(item.get("current_relative_path") or "")
        }

    metadata_by_relative: dict[str, dict[str, Any]] = {}
    try:
        analyzed = analyze_tree(event_root) if not event_root_missing else {"files": []}
        metadata_by_relative = {
            str(row.get("relative_path") or ""): row
            for row in analyzed.get("files", [])
            if row.get("relative_path")
        }
    except (MetadataError, OSError):
        # Hash-/Existenzprüfung bleibt möglich. Für neue Exporte ohne
        # auslesbare Aufnahmemetadaten entsteht später bewusst ein unklarer
        # Zuordnungsfall statt einer geratenen Zeit.
        metadata_by_relative = {}

    used_known_ids: set[int] = set()
    scanned: list[dict[str, Any]] = []

    for path in physical_files:
        event_rel = path.relative_to(event_root).as_posix()
        root_rel = path.relative_to(root).as_posix()
        info = os.lstat(path)
        size_bytes = int(info.st_size)
        metadata = metadata_by_relative.get(event_rel, {})
        media_type = str(metadata.get("media_type") or classify_media(path))

        digest: str | None = None
        known = None
        if fast_refresh:
            direct_known = known_by_current_relative.get(root_rel)
            if (
                direct_known is not None
                and int(direct_known.get("size_bytes") or -1) == size_bytes
            ):
                stored = str(
                    direct_known.get("sha256_current")
                    or direct_known.get("sha256_original")
                    or ""
                ).strip()
                if stored:
                    digest = stored
                    known = direct_known

            if digest is None:
                previous = previous_by_relative.get(root_rel)
                if (
                    previous is not None
                    and int(previous.get("size_bytes") or -1) == size_bytes
                    and str(previous.get("sha256") or "").strip()
                ):
                    digest = str(previous["sha256"])

        if digest is None:
            digest = _sha256_file(path)

        if known is None:
            known = _best_known_match(
                sha256=digest,
                size_bytes=size_bytes,
                filename=path.name,
                known_files=known_files,
                used_file_ids=used_known_ids,
            )
        known_file_id = int(known["file_id"]) if known is not None else None
        family_id = int(known["family_id"]) if known is not None and known.get("family_id") is not None else None
        if known_file_id is not None:
            used_known_ids.add(known_file_id)

        # Der physisch neu gelesene Archivbestand ist die IST-Wahrheit.
        # Für bekannte Kameraoriginale wurde bisher immer die historische
        # SQLite-Aufnahmezeit bevorzugt. Nach einer älteren Fehlzuordnung konnte
        # dadurch ein real vorhandenes Foto trotz korrekter EXIF-Zeit im falschen
        # Freigabezeitraum landen. Belastbare Medienmetadaten des aktuell
        # gelesenen Originals schlagen deshalb den gespeicherten Importwert;
        # SQLite bleibt nur der sichere Fallback, wenn die Datei selbst keine
        # belastbare Zeit mehr liefert.
        live_capture_time = str(metadata.get("selected_capture_time") or "").strip() or None
        live_capture_source = str(metadata.get("selected_capture_source") or "").strip() or None
        live_confidence = str(metadata.get("capture_time_confidence") or "missing")
        live_capture_trusted = bool(
            live_capture_time
            and live_confidence in {"high", "medium"}
            and "FileModifyDate" not in str(live_capture_source or "")
            and "FileCreateDate" not in str(live_capture_source or "")
        )
        if known is not None and live_capture_trusted:
            capture_time = live_capture_time
            capture_source = live_capture_source
            confidence = live_confidence
        elif known is not None:
            capture_time = str(known.get("selected_capture_time") or "").strip() or None
            capture_source = "database_import" if capture_time else None
            confidence = "high" if capture_time else "missing"
        else:
            capture_time = live_capture_time
            capture_source = live_capture_source
            confidence = live_confidence
        asset_kind = _asset_kind(
            event_rel,
            media_type,
            known_file_id,
            declared_export=declared_export_for(event_rel),
            previous_asset_kind=previous_kind_by_content.get((size_bytes, digest)),
        )

        # Export-Zeitpyramide 0.27.7:
        # 1. echtes DateTimeOriginal, 2. weitere belastbare Medienzeiten,
        # 3. später eindeutiger Namensabgleich mit der Kamerafamilie,
        # 4. kanonischer JJJJMMTT_HHMMSS-Dateiname als letzter Fallback.
        # Reine Dateisystemzeiten bleiben ausdrücklich ungeeignet.
        if known_file_id is None and asset_kind == "export":
            original_candidates = [
                str(item.get("normalized_datetime") or "")
                for item in metadata.get("metadata_candidates", [])
                if item.get("usable")
                and "DateTimeOriginal" in str(item.get("tag_name") or "")
                and item.get("normalized_datetime")
            ]
            distinct_originals = set(original_candidates)
            filename_capture = _filename_schema_capture_time(path.name)

            if len(distinct_originals) == 1:
                # Ein echtes Aufnahmedatum schlägt widersprechende CreateDate-
                # oder ModifyDate-Werte des Exportvorgangs. Die originale
                # Metadatenquelle bleibt sichtbar/auditierbar.
                capture_time = next(iter(distinct_originals))
                capture_source = next(
                    (
                        str(item.get("tag_name") or "")
                        for item in metadata.get("metadata_candidates", [])
                        if item.get("usable")
                        and "DateTimeOriginal" in str(item.get("tag_name") or "")
                        and str(item.get("normalized_datetime") or "") == capture_time
                    ),
                    str(capture_source or "EXIF:ExifIFD:DateTimeOriginal"),
                )
                confidence = "high"
            elif len(distinct_originals) > 1:
                # Mehrere echte, widersprüchliche Aufnahmedaten bleiben offen,
                # bis der Namensabgleich sie ggf. auf eine Kamerafamilie bindet.
                capture_time = filename_capture
                capture_source = "filename_schema" if filename_capture else None
                confidence = "medium" if filename_capture else "conflict"
            elif (
                capture_time
                and confidence in {"high", "medium"}
                and "FileModifyDate" not in str(capture_source or "")
                and filename_capture
            ):
                # CreateDate/XMP-Zeit ist bei Exporten nur dann belastbar, wenn
                # der kanonische Dateiname sie plausibilisiert. Andernfalls
                # könnte es lediglich der Exportzeitpunkt sein.
                gap = _capture_seconds_apart(capture_time, filename_capture)
                if gap is None or gap > 120:
                    capture_time = filename_capture
                    capture_source = "filename_schema"
                    confidence = "medium"
            elif filename_capture:
                capture_time = filename_capture
                capture_source = "filename_schema"
                confidence = "medium"
            else:
                capture_time = None
                capture_source = None
                confidence = "missing"

        scanned.append({
            "event_id": event_id,
            "job_id": job_id,
            "root_kind": root_kind,
            "relative_path": root_rel,
            "event_relative_path": event_rel,
            "filename": path.name,
            "extension": path.suffix.lower(),
            "media_type": media_type,
            "asset_kind": asset_kind,
            "known_file_id": known_file_id,
            "family_id": family_id,
            "source_file_id": None,
            "size_bytes": size_bytes,
            "sha256": digest,
            "selected_capture_time": capture_time,
            "selected_capture_source": capture_source,
            "capture_time_confidence": confidence,
            "branch": _branch_for(event_rel),
        })

    # Resolve conservative sidecar/export links after camera originals are known.
    originals = [row for row in scanned if row["known_file_id"] is not None]
    by_same_dir_stem: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_stem: dict[str, list[dict[str, Any]]] = {}
    known_by_id = {
        int(item["file_id"]): item
        for item in known_files
    }
    for row in originals:
        rel = PurePosixPath(row["event_relative_path"])
        known_row = known_by_id.get(int(row["known_file_id"]), {})
        stored_original_stem = str(
            known_row.get("original_stem")
            or Path(str(known_row.get("original_filename") or "")).stem
        ).strip()
        numeric_aliases = collision_alias_stems(
            rel.stem,
            allow_plain_number=True,
        )
        allow_plain_number = bool(
            stored_original_stem
            and rel.stem.casefold() != stored_original_stem.casefold()
            and stored_original_stem.casefold() in numeric_aliases
        )
        for stem_alias in collision_alias_stems(
            rel.stem,
            allow_plain_number=allow_plain_number,
        ):
            key = (str(rel.parent), stem_alias)
            by_same_dir_stem.setdefault(key, []).append(row)
            by_stem.setdefault(stem_alias, []).append(row)

    for row in scanned:
        if row["asset_kind"] not in {"xmp", "export", "derived_media"}:
            continue
        rel = PurePosixPath(row["event_relative_path"])
        aliases = collision_alias_stems(
            rel.stem,
            allow_plain_number=row["asset_kind"] == "export",
            include_export_base=row["asset_kind"] == "export",
        )
        candidates: list[dict[str, Any]] = []
        seen_candidate_ids: set[int] = set()
        for alias in aliases:
            for item in by_same_dir_stem.get((str(rel.parent), alias), []):
                key = int(item["known_file_id"])
                if key not in seen_candidate_ids:
                    candidates.append(item)
                    seen_candidate_ids.add(key)
        if not candidates:
            for alias in aliases:
                for item in by_stem.get(alias, []):
                    key = int(item["known_file_id"])
                    if key not in seen_candidate_ids:
                        candidates.append(item)
                        seen_candidate_ids.add(key)

        # 0.28.4: _Export as well as common Finder/Windows duplicate suffixes
        # are transparent for family linkage. Content identity still decides
        # which file is the imported camera original.
        # Exporte behalten häufig den Kameranamen nur als Namensbestandteil
        # (z. B. mit vorangestelltem Zeitstempel). Wenn der Name genau eine
        # importierte Familie identifiziert, wird diese Beziehung genutzt.
        filename_family = None
        if (
            row["asset_kind"] in {"export", "derived_media"}
            and row.get("media_type") in {"jpeg", "image"}
            and not candidates
        ):
            filename_family = _filename_family_source(row["filename"], known_files)
            if filename_family is not None and filename_family.get("family_id") is not None:
                matched_family_id = int(filename_family["family_id"])
                candidates = [
                    item for item in originals
                    if item.get("family_id") is not None
                    and int(item["family_id"]) == matched_family_id
                ]

        source = candidates[0] if len(candidates) == 1 else None
        candidate_family_ids = {
            int(item["family_id"])
            for item in candidates
            if item.get("family_id") is not None
        }

        # Ein Lightroom-XMP kann denselben Stem wie RAF und Kamera-JPEG haben.
        # Dann ist kein einzelnes Ursprungs-file eindeutig, wohl aber die
        # Kamerafamilie. Genau diese Beziehung reicht für gemeinsame
        # Neu-Zuordnung und Aufnahmezeit-Vererbung.
        family_source = None
        if len(candidate_family_ids) == 1:
            family_id = next(iter(candidate_family_ids))
            family_members = [
                item for item in candidates
                if item.get("family_id") is not None
                and int(item["family_id"]) == family_id
            ]
            if family_members:
                family_source = family_members[0]
                row["family_id"] = family_id

        if source is not None:
            row["source_file_id"] = source["known_file_id"]
            if row["family_id"] is None:
                row["family_id"] = source["family_id"]
            family_source = source

        if (
            row["known_file_id"] is None
            and row["asset_kind"] == "derived_media"
            and row["media_type"] in {"jpeg", "image"}
            and (family_source is not None or filename_family is not None)
        ):
            # A unique camera-family relation is positive export evidence even
            # outside a specifically classified export folder.
            row["asset_kind"] = "export"

        # Ein eindeutiger Namensbezug zum Kameraoriginal korrigiert auch
        # Exportmetadaten, wenn diese sichtbar eine andere Zeit behaupten.
        # Dadurch bleibt ein Lightroom-/Finder-Export bei seiner Aufnahme.
        export_family_correction = False
        if (
            row["asset_kind"] == "export"
            and family_source is not None
            and family_source.get("selected_capture_time")
        ):
            gap = _capture_seconds_apart(
                row.get("selected_capture_time"),
                family_source.get("selected_capture_time"),
            )
            export_family_correction = (
                not row.get("selected_capture_time")
                or row.get("capture_time_confidence") in {"missing", "low", "conflict"}
                or (gap is not None and gap > 120)
            )

        should_inherit = (
            row["asset_kind"] == "xmp"
            or export_family_correction
            or not row["selected_capture_time"]
            or row["capture_time_confidence"] in {"missing", "low", "conflict"}
        )
        if family_source is not None and should_inherit:
            row["selected_capture_time"] = family_source["selected_capture_time"]
            row["selected_capture_source"] = (
                "filename_family_correction"
                if row["asset_kind"] == "export" and export_family_correction
                else (
                    "source_file_inheritance"
                    if source is not None
                    else "family_inheritance"
                )
            )
            row["capture_time_confidence"] = (
                "high" if family_source["selected_capture_time"] else "missing"
            )

    scanned_at = _now()
    if persist:
        with database_connection(database_path) as connection:
            connection.execute(
                "DELETE FROM event_inventory_files WHERE event_id=? AND root_kind=?",
                (event_id, root_kind),
            )
            connection.executemany(
                """INSERT INTO event_inventory_files(
                       event_id,job_id,root_kind,relative_path,event_relative_path,
                       filename,extension,asset_kind,known_file_id,family_id,
                       source_file_id,size_bytes,sha256,selected_capture_time,
                       selected_capture_source,capture_time_confidence,scanned_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        row["event_id"], row["job_id"], row["root_kind"],
                        row["relative_path"], row["event_relative_path"],
                        row["filename"], row["extension"], row["asset_kind"],
                        row["known_file_id"], row["family_id"], row["source_file_id"],
                        row["size_bytes"], row["sha256"], row["selected_capture_time"],
                        row["selected_capture_source"], row["capture_time_confidence"],
                        scanned_at,
                    )
                    for row in scanned
                ],
            )
            connection.execute(
                "DELETE FROM event_inventory_directories WHERE event_id=? AND root_kind=?",
                (event_id, root_kind),
            )
            connection.executemany(
                """INSERT INTO event_inventory_directories(
                       event_id,job_id,root_kind,event_relative_path,scanned_at)
                   VALUES (?,?,?,?,?)""",
                [
                    (
                        event_id,
                        str(event.get("job_id") or job_id),
                        root_kind,
                        directory.relative_to(event_root).as_posix(),
                        scanned_at,
                    )
                    for directory in physical_directories
                ],
            )
            if update_known_file_locations:
                for row in scanned:
                    if row["known_file_id"] is None:
                        continue
                    connection.execute(
                        """UPDATE files
                           SET current_relative_path=?,current_root_kind=?,updated_at=?
                           WHERE id=?""",
                        (
                            row["relative_path"],
                            root_kind,
                            scanned_at,
                            int(row["known_file_id"]),
                        ),
                    )

    known_ids = {int(row["known_file_id"]) for row in scanned if row["known_file_id"] is not None}
    expected_ids = {int(row["file_id"]) for row in known_files}

    return {
        "event": event,
        "event_root": str(event_root),
        "event_root_missing": event_root_missing,
        "directories": [
            directory.relative_to(event_root).as_posix()
            for directory in physical_directories
        ],
        "event_prefix": prefix.as_posix(),
        "root_kind": root_kind,
        "scanned_at": scanned_at,
        "files": scanned,
        "summary": {
            "file_count": len(scanned),
            "directory_count": len(physical_directories),
            "camera_original_count": sum(row["asset_kind"] == "camera_original" for row in scanned),
            "xmp_count": sum(row["asset_kind"] == "xmp" for row in scanned),
            "export_count": sum(row["asset_kind"] == "export" for row in scanned),
            "derived_media_count": sum(row["asset_kind"] == "derived_media" for row in scanned),
            "other_count": sum(row["asset_kind"] == "other" for row in scanned),
            "known_file_count": len(known_ids),
            "expected_known_file_count": len(expected_ids),
            "missing_known_file_ids": sorted(expected_ids - known_ids),
        },
    }


def match_inventory_by_content(
    source_files: list[dict[str, Any]],
    target_files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One-to-one content match independent of Alle/Sortiert/Export position."""
    pools: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in target_files:
        pools.setdefault((int(row["size_bytes"]), str(row["sha256"])), []).append(row)
    for rows in pools.values():
        rows.sort(key=lambda r: (str(r.get("filename") or ""), str(r.get("relative_path") or "")))

    matches: list[dict[str, Any]] = []
    for source in source_files:
        key = (int(source["size_bytes"]), str(source["sha256"]))
        candidates = pools.get(key) or []
        if not candidates:
            raise EventInventoryError(
                "Datei fehlt im Zielereignis: " + str(source.get("relative_path") or source.get("filename") or "")
            )
        same_name = [row for row in candidates if row.get("filename") == source.get("filename")]
        target = same_name[0] if same_name else candidates[0]
        candidates.remove(target)
        matches.append({"source": source, "target": target})
    return matches
