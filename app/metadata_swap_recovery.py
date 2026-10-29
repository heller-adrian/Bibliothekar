"""Durable BA-12 metadata file-swap journal.

Records are fsync'ed BEFORE moving the first original. A restart either
restores each original from its adjacent old-byte copy (pre-commit) or
finishes removing verified safety copies (post-commit). Ambiguity is blocked.
No archive files, unrelated paths, or user-owned metadata are deleted.
"""
from __future__ import annotations

from app.root_operations import validate_active_roots

from contextlib import contextmanager
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import sqlite3
import uuid

from app.database import database_connection


class MetadataSwapRecoveryError(RuntimeError):
    pass


@contextmanager
def metadata_write_guard(metadata_root: Path):
    """One cooperative writer/recovery per physical metadata area, across processes.

    Reuse F14's protected control directory and nonblocking file lock. SIGKILL
    releases the kernel lock; the existing durable journals remain authoritative.
    """
    from app.root_operations import _control, _lock, RootOperationError
    entered = False
    try:
        _, control = _control(Path(metadata_root).resolve(strict=False), allow_missing=True)
        with _lock(control / 'metadata-write.lock', exclusive=True):
            entered = True
            yield
    except RootOperationError as error:
        # A domain refusal raised by the protected body is not lock contention.
        # Preserve its exact path/reason and every original safety assertion.
        if entered:
            raise
        raise MetadataSwapRecoveryError(
            "Eine Metadatenkorrektur oder Wiederherstellung ist bereits aktiv, "
            "oder ihre Sperre kann nicht sicher nachgewiesen werden."
        ) from error


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    validate_active_roots()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def _sync_dir(path: Path) -> None:
    validate_active_roots()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _journal_dir(metadata_root: Path) -> Path:
    return Path(metadata_root).resolve(strict=False) / ".swap-journals"


def _atomic_json(path: Path, data: dict[str, Any], *, new: bool = False) -> None:
    validate_active_roots()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    temp = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        validate_active_roots()
        with temp.open("xb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if new and (path.exists() or path.is_symlink()):
            raise MetadataSwapRecoveryError("Ein Metadatenjournal existiert bereits.")
        validate_active_roots()
        os.replace(temp, path)
        _sync_dir(path.parent)
    finally:
        validate_active_roots()
        temp.unlink(missing_ok=True)


def assert_no_pending_swaps(metadata_root: Path) -> None:
    """Do not start another write while an interrupted multi-file edit exists."""
    directory = _journal_dir(metadata_root)
    if directory.exists():
        if directory.is_symlink() or not directory.is_dir():
            raise MetadataSwapRecoveryError("Metadatenjournal-Stamm ist unsicher.")
        if any(directory.iterdir()):
            raise MetadataSwapRecoveryError(
                "Eine unterbrochene Metadatenkorrektur muss zuerst wiederhergestellt werden."
            )


def fsync_staged_file(path: Path) -> None:
    validate_active_roots()
    with Path(path).open("rb") as stream:
        os.fsync(stream.fileno())
    _sync_dir(path.parent)

def create_swap_journal(
    metadata_root: Path, *,
    kind: str, file_entries: list[dict[str, Any]],
    data_root: Path, database_path: Path | None = None,
    task_id: str | None = None, family_id: int | None = None,
    proposed: str = "", task_verification: dict[str, Any] | None = None,
    preparation: Path | None = None,
) -> Path:
    if kind not in {"library", "reintegrate", "multiple", "general"} or not file_entries:
        raise MetadataSwapRecoveryError("Ungültiger Metadaten-Austauschplan.")
    record_id = uuid.uuid4().hex if preparation is None else preparation.stem
    journal = _journal_dir(metadata_root) / (record_id + ".json")
    if preparation is not None:
        previous = _load(preparation, metadata_root)
        if previous["state"] != "preparing" or previous["task_id"] != task_id:
            raise MetadataSwapRecoveryError("Falsches Vorbereitungsjournal.")
        for key in ("source", "incoming", "backup", "before_sha"):
            if previous["files"][0][key] != file_entries[0][key]:
                raise MetadataSwapRecoveryError("Vorbereitungsplan wurde verändert.")
    data = {
        "format": 1, "id": record_id, "kind": kind,
        "state": "prepared", "root": str(Path(data_root).resolve(strict=False)),
        "database": str(Path(database_path).resolve(strict=False)) if database_path else "",
        "task_id": task_id, "family_id": family_id,
        "proposed": proposed, "verification": task_verification,
        "files": file_entries,
    }
    _validate(journal, data, metadata_root)
    _atomic_json(journal, data, new=preparation is None)
    return journal


def create_preparation_journal(metadata_root: Path, *, data_root: Path,
                               database_path: Path, task_id: str, source: Path,
                               incoming: Path, backup: Path, before_sha: str) -> Path:
    # Record exclusive ownership before the first byte is copied. Partial
    # native ExifTool output cannot be hashed in advance; its inode is recorded
    # before copy/write and checked on cleanup. Unknown entries are retained.
    ident = uuid.uuid4().hex
    journal = _journal_dir(metadata_root) / (ident + ".json")
    data = dict(format=1, id=ident, kind="general", state="preparing",
                root=str(data_root.resolve()), database=str(database_path.resolve()),
                task_id=task_id, files=[dict(source=str(source), incoming=str(incoming),
                                            backup=str(backup), before_sha=before_sha)])
    _validate(journal, data, metadata_root)
    _atomic_json(journal, data, new=True)
    _sync_dir(metadata_root)
    validate_active_roots()
    fd = os.open(incoming, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fsync(fd)
        info = os.fstat(fd)
        data["files"][0]["owned_inode"] = [info.st_dev, info.st_ino]
        _sync_dir(incoming.parent)
        _atomic_json(journal, data)
    finally:
        os.close(fd)
    return journal


def _recover_preparation(data: dict[str, Any]) -> None:
    item = data["files"][0]
    source, incoming, backup = [Path(item[key]) for key in ("source", "incoming", "backup")]
    if source.is_symlink() or not source.is_file() or _sha(source) != item["before_sha"]:
        raise MetadataSwapRecoveryError("Vorbereitung ohne unverändertes Original.")
    if backup.exists() or backup.is_symlink():
        raise MetadataSwapRecoveryError("Unerwartete Sicherheitskopie während Vorbereitung.")
    if incoming.exists() or incoming.is_symlink():
        info = incoming.lstat()
        if incoming.is_symlink() or not incoming.is_file() or [info.st_dev, info.st_ino] != item.get("owned_inode"):
            raise MetadataSwapRecoveryError("Arbeitskopie ohne nachgewiesenen Besitz; Prüfung erforderlich.")
        validate_active_roots()
        incoming.unlink()
        _sync_dir(incoming.parent)


def _validate(journal: Path, data: dict[str, Any], metadata_root: Path) -> None:
    if not isinstance(data, dict) or data.get("format") != 1:
        raise MetadataSwapRecoveryError("Unbekanntes Metadatenjournal.")
    ident = str(data.get("id") or "")
    if not re.fullmatch(r"[a-f0-9]{32}", ident):
        raise MetadataSwapRecoveryError("Ungültige Metadatenjournal-ID.")
    if journal != _journal_dir(metadata_root) / (ident + ".json"):
        raise MetadataSwapRecoveryError("Metadatenjournal liegt am falschen Ort.")
    if data.get("kind") not in {"library", "reintegrate", "multiple", "general"}:
        raise MetadataSwapRecoveryError("Unbekannte Metadatenkorrektur-Art.")
    if data.get("state") not in {"preparing", "prepared", "committed"}:
        raise MetadataSwapRecoveryError("Unbekannter Metadatenjournal-Zustand.")
    root = Path(str(data.get("root") or "")).resolve(strict=False)
    if not root.is_absolute() or str(root) == "/" or root.is_symlink():
        raise MetadataSwapRecoveryError("Ungültiger Metadaten-Datenstamm.")
    files = data.get("files")
    if not isinstance(files, list) or not files or len(files) > 10000:
        raise MetadataSwapRecoveryError("Metadatenjournal ohne zulässige Dateien.")
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise MetadataSwapRecoveryError("Ungültiger Metadaten-Dateieintrag.")
        paths = [str(item.get(key) or "") for key in ("source", "backup", "incoming")]
        if data["kind"] == "reintegrate":
            paths.append(str(item.get("destination") or ""))
        for raw in paths:
            path = Path(raw)
            if not path.is_absolute() or ".." in path.parts:
                raise MetadataSwapRecoveryError("Unsicherer Metadaten-Dateipfad.")
            if not path.resolve(strict=False).is_relative_to(root):
                raise MetadataSwapRecoveryError("Metadatenpfad verlässt den Dateistamm.")
        source, backup, incoming = [Path(p) for p in paths[:3]]
        if (not source.parent == backup.parent == incoming.parent or
            not backup.name.startswith("." + source.name + ".") or
            not incoming.name.startswith("." + source.name + ".")):
            raise MetadataSwapRecoveryError("Metadaten-Sicherheitskopie liegt am falschen Ort.")
        if len(set(paths)) != len(paths):
            raise MetadataSwapRecoveryError("Doppelte Metadaten-Swap-Pfade.")
        if paths[0] in seen:
            raise MetadataSwapRecoveryError("Metadatenquelle ist doppelt.")
        seen.update(paths)
        for key in (("before_sha",) if data["state"] == "preparing" else ("before_sha", "after_sha")):
            if not re.fullmatch("[0-9a-f]{64}", str(item.get(key) or "")):
                raise MetadataSwapRecoveryError("Metadatenjournal ohne gültige Prüfsumme.")
        if data["kind"] in {"library", "reintegrate"} and not isinstance(item.get("file_id"), int):
            raise MetadataSwapRecoveryError("Metadatenjournal ohne Datei-ID.")
    if data["kind"] in {"library", "reintegrate"}:
        if not data.get("database") or not data.get("family_id"):
            raise MetadataSwapRecoveryError("Metadatenjournal ohne Datenbank-Zuordnung.")
    if data["kind"] == "general" and (not data.get("database") or not data.get("task_id") or len(files) != 1):
        raise MetadataSwapRecoveryError("Allgemeine Metadatenkorrektur ohne Aufgaben-Zuordnung.")


def _load(journal: Path, metadata_root: Path) -> dict[str, Any]:
    if journal.is_symlink() or not journal.is_file():
        raise MetadataSwapRecoveryError("Metadatenjournal ist keine reguläre Datei.")
    try:
        data = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MetadataSwapRecoveryError("Metadatenjournal ist nicht lesbar.") from exc
    _validate(journal, data, metadata_root)
    return data


def _state(path: Path, item: dict[str, Any]) -> str:
    if not path.exists() and not path.is_symlink():
        return "missing"
    if path.is_symlink() or not path.is_file():
        raise MetadataSwapRecoveryError("Metadatenpfad ist kein regulärer Dateieintrag: " + str(path))
    digest = _sha(path)
    if digest == item["before_sha"] == item["after_sha"]:
        return "same"
    if digest == item["before_sha"]:
        return "before"
    if digest == item["after_sha"]:
        return "after"
    raise MetadataSwapRecoveryError("Metadaten-Datei besitzt fremden Inhalt: " + str(path))


def _database_state(data: dict[str, Any]) -> str:
    """SQLite provides the commit fence for library and reintegration swaps."""
    if data["kind"] == "multiple":
        return "committed" if data["state"] == "committed" else "prepared"
    db = Path(str(data["database"]))
    if not db.is_file():
        raise MetadataSwapRecoveryError("Metadaten-Index fehlt; keine automatische Wiederherstellung.")
    results = []
    with database_connection(db) as conn:
        if data["kind"] == "general":
            row = conn.execute(
                "SELECT status,source_path,source_sha256,output_sha256 FROM metadata_corrections WHERE id=? AND area='general'",
                (data["task_id"],),
            ).fetchone()
            item = data["files"][0]
            if row is None or str(row["source_path"]) != item["source"] or str(row["source_sha256"]) != item["before_sha"]:
                raise MetadataSwapRecoveryError("Allgemeine Metadatenaufgabe passt nicht zum Journal.")
            if row["status"] == "completed" and row["output_sha256"] == item["after_sha"]:
                return "committed"
            if row["status"] in {"writing", "blocked", "prepared"}:
                return "prepared"
            raise MetadataSwapRecoveryError("Allgemeine Metadatenaufgabe besitzt einen widersprüchlichen Zustand.")
        for item in data["files"]:
            row = conn.execute(
                """SELECT current_relative_path,sha256_current,selected_capture_time
                   FROM files WHERE id=? AND family_id=?""",
                (item["file_id"], data["family_id"]),
            ).fetchone()
            if row is None:
                raise MetadataSwapRecoveryError("Dateidatensatz fehlt; Wiederherstellung gesperrt.")
            if data["kind"] == "reintegrate":
                old = str(item["source_relative"])
                new = str(item["destination_relative"])
                if str(row["current_relative_path"]) == new and str(row["sha256_current"]) == item["after_sha"]:
                    results.append("committed")
                elif str(row["current_relative_path"]) == old and str(row["sha256_current"]) == item["before_sha"]:
                    results.append("prepared")
                else:
                    results.append("ambiguous")
            else:
                if (str(row["sha256_current"]) == item["after_sha"]
                    and str(row["selected_capture_time"] or "") == str(data["proposed"])):
                    results.append("committed")
                elif str(row["sha256_current"]) == item["before_sha"]:
                    results.append("prepared")
                else:
                    results.append("ambiguous")
    if all(s == "committed" for s in results):
        return "committed"
    if all(s == "prepared" for s in results):
        return "prepared"
    raise MetadataSwapRecoveryError("SQLite-Dateieinträge sind uneinheitlich; keine automatische Aktion.")


def mark_swap_committed(journal: Path, metadata_root: Path) -> None:
    data = _load(journal, metadata_root)
    data["state"] = "committed"
    _atomic_json(journal, data)


def _preflight_rollback(data: dict[str, Any]) -> None:
    for item in data["files"]:
        source = Path(item["source"])
        backup = Path(item["backup"])
        incoming = Path(item["incoming"])
        destination = Path(item["destination"]) if item.get("destination") else None
        ss, bs, ins = [_state(p, item) for p in (source, backup, incoming)]
        ds = _state(destination, item) if destination else "missing"
        if bs in {"before", "same"}:
            if ss not in {"after", "same", "missing"} or ds not in {"after", "same", "missing"}:
                raise MetadataSwapRecoveryError("Metadaten-Rückbau mit widersprüchlicher Quelle.")
        elif bs == "missing":
            if ss not in {"before", "same"} or ds not in {"after", "same", "missing"}:
                raise MetadataSwapRecoveryError("Metadaten-Rückbau ohne gesicherte Originalbytes.")
        else:
            raise MetadataSwapRecoveryError("Metadaten-Sicherung besitzt keinen Originalinhalt.")
        if ins not in {"after", "same", "missing"}:
            raise MetadataSwapRecoveryError("Metadaten-Zwischendatei wurde verändert.")


def _rollback(data: dict[str, Any]) -> None:
    _preflight_rollback(data)
    for item in reversed(data["files"]):
        source, backup, incoming = [Path(item[k]) for k in ("source", "backup", "incoming")]
        destination = Path(item["destination"]) if item.get("destination") else None
        if backup.exists():
            validate_active_roots()
            os.replace(backup, source)
            _sync_dir(source.parent)
        if destination and destination.exists():
            # The destination is a verified AFTER copy; the original is now safe.
            validate_active_roots()
            destination.unlink()
            _sync_dir(destination.parent)
        if incoming.exists():
            validate_active_roots()
            incoming.unlink()
            _sync_dir(incoming.parent)


def _preflight_finish(data: dict[str, Any]) -> None:
    for item in data["files"]:
        source, backup, incoming = [Path(item[k]) for k in ("source", "backup", "incoming")]
        destination = Path(item["destination"]) if item.get("destination") else None
        if destination:
            if _state(source, item) != "missing" or _state(destination, item) not in {"after", "same"}:
                raise MetadataSwapRecoveryError("Reintegration wurde nicht vollständig bestätigt.")
        elif _state(source, item) not in {"after", "same"}:
            raise MetadataSwapRecoveryError("Metadaten-Austausch wurde nicht vollständig abgeschlossen.")
        if _state(backup, item) not in {"before", "same", "missing"}:
            raise MetadataSwapRecoveryError("Metadaten-Sicherung wurde verändert.")
        if _state(incoming, item) not in {"after", "same", "missing"}:
            raise MetadataSwapRecoveryError("Metadaten-Zwischendatei wurde verändert.")


def _finish(data: dict[str, Any]) -> None:
    _preflight_finish(data)
    for item in data["files"]:
        for key in ("backup", "incoming"):
            path = Path(item[key])
            if path.exists():
                validate_active_roots()
                path.unlink()
                _sync_dir(path.parent)


def recover_swap_journal(
    metadata_root: Path, journal: Path, *,
    allowed_databases: set[Path] | None = None,
) -> str:
    data = _load(journal, metadata_root)
    db = str(data.get("database") or "")
    if db and allowed_databases is not None:
        approved = {str(Path(p).resolve(strict=False)) for p in allowed_databases}
        if db not in approved:
            raise MetadataSwapRecoveryError("Metadatenjournal verweist auf eine nicht registrierte Datenbank.")
    if data["state"] == "preparing":
        # Validate task/source association independently of the unknown AFTER hash.
        item = data["files"][0]
        with database_connection(Path(db)) as conn:
            row = conn.execute("SELECT source_path,source_sha256,status FROM metadata_corrections WHERE id=? AND area='general'", (data["task_id"],)).fetchone()
            if row is None or row["source_path"] != item["source"] or row["source_sha256"] != item["before_sha"] or row["status"] not in {"prepared", "blocked", "writing"}:
                raise MetadataSwapRecoveryError("Vorbereitungsjournal passt nicht zur Aufgabe.")
        _recover_preparation(data)
        validate_active_roots()
        journal.unlink()
        _sync_dir(journal.parent)
        return "rolled_back"
    decision = _database_state(data)
    if data["state"] == "committed" and decision != "committed":
        raise MetadataSwapRecoveryError("Metadatenjournal und SQLite-Commit widersprechen sich.")
    if decision == "committed":
        _finish(data)
        if data["kind"] == "library" and data.get("task_id"):
            from app.metadata_correction import _complete_task, get_metadata_correction
            current = get_metadata_correction(Path(db), str(data["task_id"]))
            if str(current["status"]) != "completed":
                details = data.get("verification") or {}
                _complete_task(
                    Path(db), str(data["task_id"]),
                    output_path=Path(str(details["output_path"])),
                    output_size=int(details["output_size"]),
                    output_sha=str(details["output_sha"]),
                    verification=dict(details["verification"]),
                )
        disposition = "completed"
    else:
        _rollback(data)
        if data["kind"] in {"library", "general"} and data.get("task_id"):
            from app.metadata_correction import _mark_task_blocked
            _mark_task_blocked(
                Path(db), str(data["task_id"]),
                MetadataSwapRecoveryError(
                    "Metadatenkorrektur nach Prozessabbruch zurückgesetzt; bitte erneut ausführen."
                ),
            )
        disposition = "rolled_back"
    validate_active_roots()
    journal.unlink()
    _sync_dir(journal.parent)
    return disposition


def recover_metadata_swaps(
    metadata_root: Path, *,
    allowed_databases: set[Path] | None = None,
) -> dict[str, Any]:
    directory = _journal_dir(metadata_root)
    result: dict[str, Any] = {"completed": 0, "rolled_back": 0, "blocked": 0, "errors": []}
    if not directory.exists():
        return result
    with metadata_write_guard(metadata_root):
        if directory.is_symlink() or not directory.is_dir():
            raise MetadataSwapRecoveryError("Metadatenjournal-Stamm ist unsicher.")
        for journal in sorted(directory.glob("*.json")):
            try:
                result[recover_swap_journal(
                    metadata_root, journal, allowed_databases=allowed_databases,
                )] += 1
            except Exception as exc:
                result["blocked"] += 1
                result["errors"].append(journal.name + ": " + str(exc))
        return result
