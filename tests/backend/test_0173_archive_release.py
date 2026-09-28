from pathlib import Path

import pytest

from app.ssd_release import SsdReleaseError, _remove_empty_event_tree, _validate_event_tree


def _fixture(tmp_path: Path):
    work_root = tmp_path / "Arbeitsbereich"
    event_root = work_root / "2026" / "07-23 - test 23 Archiv"
    media = event_root / "Alle" / "DSCF0001.JPG"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"image")
    event = {
        "start_datetime": "2026-07-23T00:00:00",
        "folder_name": "07-23 - test 23 Archiv",
    }
    files = [{
        "file_id": 1,
        "current_root_kind": "shared_workspace",
        "current_relative_path": "2026/07-23 - test 23 Archiv/Alle/DSCF0001.JPG",
        "original_relative_path": "DCIM/DSCF0001.JPG",
        "sha256_current": "dummy",
        "sha256_original": "dummy",
        "size_bytes": 5,
    }]
    return work_root, event_root, event, files


def test_release_allows_event_json_and_macos_metadata(tmp_path):
    work_root, event_root, event, files = _fixture(tmp_path)
    (event_root / "event.json").write_text("{}")
    (event_root / ".DS_Store").write_bytes(b"finder")
    (event_root / "._DSCF0001.JPG").write_bytes(b"appledouble")

    root, prepared = _validate_event_tree(work_root, event, files, False)
    assert root == event_root.resolve(strict=False)
    assert len(prepared) == 1


def test_release_still_blocks_unknown_file(tmp_path):
    work_root, event_root, event, files = _fixture(tmp_path)
    (event_root / "event.json").write_text("{}")
    (event_root / "TEST.txt").write_text("unexpected")

    with pytest.raises(SsdReleaseError, match="nicht erfasste Dateien") as exc:
        _validate_event_tree(work_root, event, files, False)
    assert "TEST.txt" in str(exc.value)


def test_release_still_blocks_symlink(tmp_path):
    work_root, event_root, event, files = _fixture(tmp_path)
    (event_root / "event.json").write_text("{}")
    (event_root / "link").symlink_to(event_root / "event.json")

    with pytest.raises(SsdReleaseError, match="nicht erfasste Dateien"):
        _validate_event_tree(work_root, event, files, False)



def test_release_cleanup_removes_event_json_and_event_tree(tmp_path):
    work_root, event_root, _event, _files = _fixture(tmp_path)
    media = event_root / "Alle" / "DSCF0001.JPG"
    media.unlink()
    (event_root / "event.json").write_text("{}")
    (event_root / ".DS_Store").write_bytes(b"finder")
    (event_root / "Alle" / "._DSCF0001.JPG").write_bytes(b"appledouble")

    removed = _remove_empty_event_tree(work_root=work_root, event_root=event_root)

    assert not event_root.exists()
    assert "2026/07-23 - test 23 Archiv/event.json" in removed
    assert "2026/07-23 - test 23 Archiv" in removed


def test_release_cleanup_never_deletes_unexpected_remaining_file(tmp_path):
    work_root, event_root, _event, _files = _fixture(tmp_path)
    media = event_root / "Alle" / "DSCF0001.JPG"
    media.unlink()
    unexpected = event_root / "KEEP.txt"
    unexpected.write_text("keep")

    with pytest.raises(SsdReleaseError, match="unerwartete Dateien"):
        _remove_empty_event_tree(work_root=work_root, event_root=event_root)

    assert unexpected.exists()
    assert event_root.exists()
