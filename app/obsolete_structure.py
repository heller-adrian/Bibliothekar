"""Remove only empty, known old workspace structure after verified reconciliation."""
import json
from pathlib import Path


def cleanup_obsolete_structure(root: Path, sources, destinations, event_ids):
    root = root.resolve()
    destinations = {Path(p).resolve() for p in destinations}
    candidates = set()
    documents = set()
    for source in sources:
        current = Path(source).parent
        while current != root and root in current.parents:
            if current.is_symlink():
                break
            candidates.add(current)
            if current.name == 'Alle':
                candidates.update(current.parent / name for name in ('Sortiert','Export'))
            document = current / 'event.json'
            if document.is_file() and not document.is_symlink():
                documents.add(document)
            current = current.parent
    for document in documents:
        if any(document.parent in target.parents for target in destinations):
            continue
        try:
            data=json.loads(document.read_text())
            if data.get('source') != 'kamera-automatisierung' or str(data.get('event',{}).get('id')) not in event_ids:
                continue
            # Unknown files and directories keep the entire old structure intact.
            contents=list(document.parent.rglob('*'))
            if any(p.is_symlink() or (p.is_file() and p!=document) or (p.is_dir() and p not in candidates) for p in contents):
                continue
            document.unlink()
        except (OSError,ValueError,TypeError):
            continue
    removed=[]
    for directory in sorted(candidates,key=lambda p:len(p.parts),reverse=True):
        if directory==root or directory.is_symlink() or any(directory in target.parents for target in destinations):
            continue
        try:
            directory.rmdir()
            removed.append(str(directory))
        except OSError:
            pass
    return removed
