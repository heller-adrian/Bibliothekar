"""Sichere Neutralisierung herausfallender Familien aus applied-Ereignissen.

0.20.4: Familien, die durch eine strukturelle Bearbeitung aus einem bereits
angewendeten Ereignis herausfallen, bleiben nicht physisch im alten
Ereignisordner. Ihre Arbeitskopien werden innerhalb desselben SSD-Datasets nach
``Arbeitsbereich/Nicht zugeordnet/JJJJ/MM`` verschoben. SD-Sicherung und
Kamerabibliothek werden dabei niemals angefasst.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import os

from app.workspace_layout import shared_work_root


class AppliedNeutralizationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_rel(value: str) -> PurePosixPath:
    p = PurePosixPath(str(value or "").replace("\\", "/"))
    if p.is_absolute() or not p.parts or any(part in {"", ".", ".."} for part in p.parts):
        raise AppliedNeutralizationError("Unsicherer Arbeitsbereichspfad: " + str(value))
    return p


def _move_same_filesystem(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise AppliedNeutralizationError("Neutraler Zielpfad existiert bereits: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    src_stat = os.lstat(source)
    os.link(source, destination, follow_symlinks=False)
    dst_stat = os.lstat(destination)
    if int(src_stat.st_dev) != int(dst_stat.st_dev) or int(src_stat.st_ino) != int(dst_stat.st_ino):
        destination.unlink(missing_ok=True)
        raise AppliedNeutralizationError("Sicherer SSD-Verschiebeschritt konnte nicht bestätigt werden: " + str(destination))
    source.unlink()


def _rollback_move(source: Path, destination: Path) -> None:
    if destination.exists() and not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        os.link(destination, source, follow_symlinks=False)
        destination.unlink()


def neutralize_removed_applied_families(
    database_path: Path,
    workspace_path: Path,
    *,
    job_id: str,
    event_id: str,
    family_ids: list[int],
    mutation_id: str | None,
) -> list[dict[str, Any]]:
    """Move all current workspace files of removed families into neutral storage.

    Every source is validated before the first move. On any failure all physical
    moves are rolled back and the files table remains unchanged.
    """
    if not family_ids:
        return []
    from app.database import database_connection

    root = shared_work_root(workspace_path).resolve(strict=False)
    placeholders = ",".join("?" for _ in family_ids)
    with database_connection(database_path) as c:
        rows = c.execute(
            f"""SELECT f.id,f.family_id,f.current_relative_path,f.current_root_kind,
                       f.size_bytes,f.sha256_current,f.sha256_original,
                       COALESCE(ff.selected_capture_time,f.selected_capture_time) AS capture_time
                FROM files f
                LEFT JOIN file_families ff ON ff.id=f.family_id
                WHERE f.job_id=? AND f.family_id IN ({placeholders})
                ORDER BY f.id""",
            (job_id, *family_ids),
        ).fetchall()
    if not rows:
        raise AppliedNeutralizationError("Für die herausfallenden Familien wurden keine Arbeitsdateien gefunden.")

    prepared: list[dict[str, Any]] = []
    seen_dest: set[str] = set()
    for row in rows:
        if str(row["current_root_kind"] or "") != "shared_workspace":
            raise AppliedNeutralizationError(
                "Eine herausfallende Datei liegt nicht im SSD-Arbeitsbereich; Neutralisierung wurde abgebrochen."
            )
        rel = _safe_rel(str(row["current_relative_path"] or ""))
        src = root.joinpath(*rel.parts).resolve(strict=False)
        if not _inside(src, root) or not src.exists() or not src.is_file() or src.is_symlink():
            raise AppliedNeutralizationError("Arbeitsdatei fehlt oder ist unsicher: " + str(src))
        st = src.stat()
        if int(st.st_size) != int(row["size_bytes"] or 0):
            raise AppliedNeutralizationError("Dateigröße stimmt vor Neutralisierung nicht: " + str(src))
        expected = str(row["sha256_current"] or row["sha256_original"] or "").strip()
        if not expected or _sha256(src) != expected:
            raise AppliedNeutralizationError("SHA-256 stimmt vor Neutralisierung nicht: " + str(src))
        capture = str(row["capture_time"] or "")
        if len(capture) < 7 or capture[4:5] != "-" or capture[7:8] not in {"", "-", "T"}:
            raise AppliedNeutralizationError("Aufnahmedatum für neutralen Jahres-/Monatsordner fehlt.")
        year, month = capture[:4], capture[5:7]
        filename = rel.name
        dest_rel = PurePosixPath("Nicht zugeordnet", year, month, filename)
        if str(dest_rel) in seen_dest:
            raise AppliedNeutralizationError("Mehrere Dateien würden denselben neutralen Zielpfad erhalten: " + str(dest_rel))
        seen_dest.add(str(dest_rel))
        dst = root.joinpath(*dest_rel.parts).resolve(strict=False)
        if not _inside(dst, root):
            raise AppliedNeutralizationError("Neutraler Zielpfad verlässt den Arbeitsbereich.")
        if dst.exists() or dst.is_symlink():
            raise AppliedNeutralizationError("Neutraler Zielpfad ist bereits belegt: " + str(dst))
        prepared.append({
            "file_id": int(row["id"]),
            "family_id": int(row["family_id"]),
            "old_relative_path": rel.as_posix(),
            "neutral_relative_path": dest_rel.as_posix(),
            "sha256": expected,
            "size_bytes": int(row["size_bytes"] or 0),
            "source": src,
            "destination": dst,
        })

    moved: list[dict[str, Any]] = []
    try:
        for item in prepared:
            _move_same_filesystem(item["source"], item["destination"])
            # Ab jetzt muss der Schritt rollback-fähig sein, auch wenn die
            # unmittelbar folgende Zielprüfung fehlschlägt.
            moved.append(item)
            if _sha256(item["destination"]) != item["sha256"]:
                raise AppliedNeutralizationError("SHA-256 stimmt nach Neutralisierung nicht: " + str(item["destination"]))
        with database_connection(database_path) as c:
            c.execute("BEGIN IMMEDIATE")
            for item in prepared:
                c.execute(
                    "UPDATE files SET current_relative_path=?,current_root_kind='shared_workspace' WHERE id=? AND job_id=?",
                    (item["neutral_relative_path"], item["file_id"], job_id),
                )
            if mutation_id:
                row = c.execute("SELECT target_state_json FROM event_mutations WHERE id=? AND job_id=?", (mutation_id, job_id)).fetchone()
                if row is not None:
                    import json
                    state = json.loads(str(row["target_state_json"] or "{}"))
                    state["_neutralized_files"] = [
                        {k: v for k, v in item.items() if k not in {"source", "destination"}}
                        for item in prepared
                    ]
                    c.execute(
                        "UPDATE event_mutations SET target_state_json=? WHERE id=? AND job_id=?",
                        (json.dumps(state, ensure_ascii=False, sort_keys=True), mutation_id, job_id),
                    )
            c.commit()
    except Exception:
        for item in reversed(moved):
            try:
                _rollback_move(item["source"], item["destination"])
            except Exception:
                pass
        raise

    return [
        {k: v for k, v in item.items() if k not in {"source", "destination"}}
        for item in prepared
    ]


def cleanup_empty_neutral_directories(workspace_path: Path) -> list[str]:
    """Remove empty month/year folders below ``Nicht zugeordnet``.

    The stable top-level system folder itself is preserved.
    """
    root = shared_work_root(workspace_path).resolve(strict=False)
    neutral = (root / "Nicht zugeordnet").resolve(strict=False)
    if not _inside(neutral, root) or not neutral.exists() or not neutral.is_dir():
        return []
    removed: list[str] = []
    # deepest first; keep the top-level neutral folder
    dirs = sorted((p for p in neutral.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
    for directory in dirs:
        try:
            if not any(directory.iterdir()):
                directory.rmdir()
                removed.append(str(directory))
        except FileNotFoundError:
            pass
    return removed


def restore_neutralized_files(connection: Any, workspace_path: Path, mutation_row: Any) -> int:
    """Restore neutralized files when an open event mutation is cancelled."""
    import json
    try:
        state = json.loads(str(mutation_row["target_state_json"] or "{}"))
    except Exception:
        state = {}
    entries = list(state.get("_neutralized_files") or [])
    if not entries:
        return 0
    root = shared_work_root(workspace_path).resolve(strict=False)
    prepared = []
    for item in entries:
        neutral_rel = _safe_rel(str(item.get("neutral_relative_path") or ""))
        old_rel = _safe_rel(str(item.get("old_relative_path") or ""))
        src = root.joinpath(*neutral_rel.parts).resolve(strict=False)
        dst = root.joinpath(*old_rel.parts).resolve(strict=False)
        if not _inside(src, root) or not _inside(dst, root):
            raise ValueError("Eine neutralisierte Datei verlässt den Arbeitsbereich.")
        if not src.exists() or not src.is_file() or src.is_symlink():
            raise ValueError("Neutralisierte Datei fehlt; Änderung kann nicht sicher verworfen werden: " + str(src))
        if dst.exists() or dst.is_symlink():
            raise ValueError("Alter Ereignispfad ist bereits belegt; Änderung kann nicht sicher verworfen werden: " + str(dst))
        expected = str(item.get("sha256") or "")
        if int(src.stat().st_size) != int(item.get("size_bytes") or 0) or not expected or _sha256(src) != expected:
            raise ValueError("Neutralisierte Datei stimmt nicht mehr mit dem gespeicherten Zustand überein: " + str(src))
        prepared.append((item, src, dst))
    moved=[]
    try:
        for item,src,dst in prepared:
            _move_same_filesystem(src,dst)
            moved.append((item,src,dst))
        for item,_,_ in prepared:
            connection.execute(
                "UPDATE files SET current_relative_path=?,current_root_kind='shared_workspace' WHERE id=? AND job_id=?",
                (str(item["old_relative_path"]), int(item["file_id"]), str(mutation_row["job_id"])),
            )
    except Exception:
        for item,src,dst in reversed(moved):
            try:
                _rollback_move(src,dst)
            except Exception:
                pass
        raise
    cleanup_empty_neutral_directories(workspace_path)
    return len(prepared)
