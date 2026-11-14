from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import PurePosixPath

import pytest

from app import legacy_adoption_dataset as dataset
from app.legacy_adoption_paths import bound_directory


@pytest.fixture
def zfs_views(tmp_path, monkeypatch):
    source, archive = (tmp_path.resolve() / name for name in ("source", "archive"))
    source.mkdir()
    archive.mkdir()
    device = source.stat().st_dev
    device_name = f"{os.major(device)}:{os.minor(device)}"
    mounts = {
        41: dataset.Mount(device_name, PurePosixPath("/old"), PurePosixPath(source), "zfs", "pool/photos"),
        42: dataset.Mount(device_name, PurePosixPath("/archive"), PurePosixPath(archive), "zfs", "pool/photos"),
    }
    monkeypatch.setattr(dataset, "mount_table", lambda: mounts)
    with ExitStack() as stack:
        left = stack.enter_context(bound_directory(source))
        right = stack.enter_context(bound_directory(archive))
        ids = {left: 41, right: 42}
        monkeypatch.setattr(dataset, "mount_id", ids.__getitem__)
        yield mounts, (source, archive, left, right)


def test_two_bind_mounts_of_one_zfs_dataset(zfs_views):
    _, arguments = zfs_views
    proof = dataset.prove(*arguments)
    assert proof["dataset"] == "pool/photos"
    assert proof["source_directory"] == "/old"
    assert proof["archive_directory"] == "/archive"
    assert dataset.revalidate(proof, *arguments) == proof


@pytest.mark.parametrize("filesystem,name", [
    ("zfs", "pool/other"), ("zfs", "other/photos"), ("ext4", "pool/photos"),
])
def test_refuses_other_datasets_and_filesystems(zfs_views, filesystem, name):
    mounts, arguments = zfs_views
    mounts[42] = replace(mounts[42], filesystem=filesystem, source=name)
    with pytest.raises(dataset.DatasetError, match="nicht auf demselben ZFS-Dataset"):
        dataset.prove(*arguments)


@pytest.mark.parametrize("change", ["unavailable", "nested", "overlap", "remounted"])
def test_revalidation_fails_closed(zfs_views, change):
    mounts, arguments = zfs_views
    before = dataset.prove(*arguments)
    if change == "unavailable":
        del mounts[42]
    elif change == "nested":
        mounts[43] = replace(mounts[42], target=mounts[41].target / "nested", source="pool/child")
    elif change == "overlap":
        mounts[42] = replace(mounts[42], root=PurePosixPath("/old/archive"))
    else:
        mounts[42] = replace(mounts[42], root=PurePosixPath("/changed"))
    with pytest.raises(dataset.DatasetError):
        dataset.revalidate(before, *arguments)


def test_kernel_mount_parser_preserves_escaped_paths(tmp_path, monkeypatch):
    from pathlib import Path

    fixture = tmp_path / "mountinfo"
    fixture.write_text(r"11 1 0:23 /Archiv\040Alt /sources/Photos\040Here rw - zfs pool/photos rw" + "\n")
    monkeypatch.setattr(dataset, "Path", lambda name: fixture if name == "/proc/self/mountinfo" else Path(name))
    observed = dataset.mount_table()[11]
    assert observed.root == PurePosixPath("/Archiv Alt")
    assert observed.target == PurePosixPath("/sources/Photos Here")
    assert observed.source == "pool/photos"


def test_source_browser_only_lists_the_archive_dataset_and_paths_to_it(zfs_views, monkeypatch):
    mounts, (source, archive, source_fd, archive_fd) = zfs_views
    matching = source / "container route" / "existing photos"
    different = source / "unrelated"
    for path in (matching, matching / "incoming", matching / "archive", different):
        path.mkdir(parents=True, exist_ok=True)
    mounts[41] = replace(mounts[41], root=PurePosixPath("/"), source="pool/parent")
    mounts[43] = replace(mounts[42], root=PurePosixPath("/"), target=PurePosixPath(matching))
    mounts[44] = replace(mounts[41], target=PurePosixPath(different), source="pool/parent/unrelated")
    identities = {path.stat().st_ino: mount for path, mount in ((source, 41), (archive, 42),
                   (matching.parent, 41), (matching, 43), (different, 44))}
    monkeypatch.setattr(dataset, "mount_id", lambda fd: identities[os.fstat(fd).st_ino])

    assert dataset.browsable_folders(source, source_fd, archive, archive_fd, ["container route", "unrelated"]) == ["container route"]
    with bound_directory(matching.parent) as parent_fd, bound_directory(matching) as matching_fd:
        assert dataset.browsable_folders(matching.parent, parent_fd, archive, archive_fd, ["existing photos"]) == ["existing photos"]
        assert dataset.browsable_folders(matching, matching_fd, archive, archive_fd, ["archive", "incoming"]) == ["incoming"]
        with pytest.raises(dataset.DatasetError, match="überschneiden"):
            dataset.prove(matching, archive, matching_fd, archive_fd)
