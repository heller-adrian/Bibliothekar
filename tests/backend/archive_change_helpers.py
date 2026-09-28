"""Test helper for the manual projected event.json Finder step."""
from pathlib import Path
from app.archive_staging import required_event_document_for_request

def copy_prepared_event_document(database_path: Path, workspace_path: Path, archive_root: Path, cr_id: str) -> Path:
    spec = required_event_document_for_request(database_path, cr_id)
    assert spec is not None
    relative = str(spec["target_relative_path"])
    source = workspace_path / "Arbeitsbereich" / "Später zuordnen" / relative
    assert source.is_file(), source
    target = archive_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    assert target.stat().st_size == int(spec["size_bytes"])
    return target
