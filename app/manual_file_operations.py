"""Group planned manual file operations by their folder pair."""
from pathlib import PurePosixPath


def parent_directory(value):
    path = str(value or "").replace("\\", "/").strip("/")
    return PurePosixPath(path).parent.as_posix() if path else ""


def group_file_operations(rows):
    """Group (source path, target path, item) triples in display order."""
    groups = {}
    for source, target, item in rows:
        pair = (parent_directory(source), parent_directory(target))
        groups.setdefault(pair, []).append(item)
    return sorted(groups.items())
