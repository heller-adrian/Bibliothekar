"""Remove only empty, known old workspace structure after verified reconciliation."""
import json
import re
from pathlib import Path


WORKSPACE_BRANCHES = {"Alle", "Sortiert", "Export"}
DAY_DIRECTORY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IGNORED_METADATA_FILES = {".DS_Store"}


def _ignored_metadata_file(path: Path) -> bool:
    """Only metadata that the event inventory deliberately ignores."""
    return path.name in IGNORED_METADATA_FILES or path.name.startswith("._")


def _remove_ignored_metadata(directory: Path) -> None:
    """Remove harmless ignored metadata from a proven obsolete managed folder.

    The caller has already established that ``directory`` belongs to
    Bibliothekar and is no longer required by the target layout. Unknown files,
    directories and symlinks remain untouched so they continue to block rmdir.
    """
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        if not _ignored_metadata_file(entry) or entry.is_symlink():
            continue
        try:
            if entry.is_file():
                entry.unlink()
        except OSError:
            pass


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _safe_component(value) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw in {".", ".."} or "/" in raw or "\\" in raw:
        return None
    return raw


def _managed_candidates_from_document(event_root: Path, data: dict) -> set[Path]:
    """Return only directories whose names/shapes are owned by the app.

    event.json is the ownership proof for the event root. We never delete files
    here; rmdir later removes only empty managed directories.
    """
    candidates: set[Path] = {event_root}
    event = data.get("event") or {}
    preserve = bool(event.get("preserve_day_folders"))
    bases = [event_root]
    for child in data.get("child_events") or []:
        name = _safe_component(child.get("folder_name") or child.get("name"))
        if name:
            bases.append(event_root / name)

    for base in bases:
        candidates.add(base)
        if preserve:
            try:
                day_dirs = [
                    item for item in base.iterdir()
                    if item.is_dir() and not item.is_symlink() and DAY_DIRECTORY.match(item.name)
                ]
            except OSError:
                day_dirs = []
            for day_dir in day_dirs:
                candidates.add(day_dir)
                candidates.update(day_dir / branch for branch in WORKSPACE_BRANCHES)
        else:
            candidates.update(base / branch for branch in WORKSPACE_BRANCHES)
    return candidates


def cleanup_obsolete_structure(
    root: Path,
    sources,
    destinations,
    event_ids,
    *,
    managed_event_roots=(),
    desired_directories=(),
):
    root = root.resolve()
    destinations = {Path(p).resolve() for p in destinations}
    desired_directories = {
        Path(p).resolve() for p in desired_directories
        if _inside(Path(p).resolve(), root)
    }
    explicit_roots = {
        Path(p).resolve() for p in managed_event_roots
        if _inside(Path(p).resolve(), root) and Path(p).resolve() != root
    }

    def required(directory: Path) -> bool:
        return (
            any(directory == target or directory in target.parents for target in destinations)
            or any(directory == target or directory in target.parents for target in desired_directories)
        )

    # A concrete destination in one standard branch makes the sibling branches
    # part of the active managed target as well. Never prune empty Sortiert /
    # Export merely because all camera originals currently live in Alle.
    active_branch_roots = set()
    for target in destinations:
        for parent in (target.parent, *target.parents):
            if parent.name in WORKSPACE_BRANCHES and _inside(parent, root):
                active_branch_roots.add(parent.parent)
                break
    for directory in desired_directories:
        if directory.name in WORKSPACE_BRANCHES:
            active_branch_roots.add(directory.parent)

    candidates: set[Path] = set()
    documents: set[Path] = set()

    # Existing behavior: source paths prove which old free/event ancestors were
    # touched by this reconciliation.
    for source in sources:
        current = Path(source).resolve(strict=False).parent
        while current != root and _inside(current, root):
            if current.is_symlink():
                break
            candidates.add(current)
            if current.name == "Alle":
                candidates.update(current.parent / name for name in WORKSPACE_BRANCHES)
            document = current / "event.json"
            if document.is_file() and not document.is_symlink():
                documents.add(document)
            current = current.parent

    # 0.26.10: an empty removed child has no source file and therefore cannot
    # appear above. The current event root is supplied explicitly; its old
    # event.json proves ownership and tells us which empty child structures were
    # managed by Bibliothekar.
    for event_root in explicit_roots:
        document = event_root / "event.json"
        if document.is_file() and not document.is_symlink():
            documents.add(document)

    valid_documents: dict[Path, dict] = {}
    for document in documents:
        try:
            data = json.loads(document.read_text())
        except (OSError, ValueError, TypeError):
            continue
        if (
            data.get("source") != "kamera-automatisierung"
            or str((data.get("event") or {}).get("id")) not in event_ids
        ):
            continue
        valid_documents[document] = data
        candidates.update(_managed_candidates_from_document(document.parent, data))

    # Remove event.json only when the complete old event root is obsolete and
    # contains no unknown file/directory. An edited event keeps its document
    # until the fresh document is written after cleanup.
    for document, data in valid_documents.items():
        if required(document.parent):
            continue
        try:
            contents = list(document.parent.rglob("*"))
            if any(
                p.is_symlink()
                or (p.is_file() and p != document)
                or (p.is_dir() and p not in candidates)
                for p in contents
            ):
                continue
            document.unlink()
        except OSError:
            continue

    removed = []
    for directory in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        if directory == root or directory.is_symlink() or required(directory):
            continue
        if directory.name in WORKSPACE_BRANCHES and directory.parent in active_branch_roots:
            continue
        # Finder/SMB may leave .DS_Store or AppleDouble files in a folder
        # whose real event contents were completely moved by Bibliothekar.
        # event_inventory ignores exactly these files, so letting them block
        # rmdir would make our own completed restructure look like a later
        # manual folder change. Remove only that narrow ignored metadata set;
        # any other entry still protects the directory from deletion.
        _remove_ignored_metadata(directory)
        try:
            directory.rmdir()
            removed.append(str(directory))
        except OSError:
            pass
    return removed
