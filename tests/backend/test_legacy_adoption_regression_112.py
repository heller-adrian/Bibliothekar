"""Regression evidence for legacy adoption: families, names, and content reuse.

These tests operate on synthetic in-memory naming state only.  They never touch
real archives or an active TrueNAS installation.
"""
from pathlib import Path

import pytest

from app.legacy_adoption_plan import _family_duplicate_conflict, _family_targets


def _missing(_path):
    return None


def _member(path, checksum):
    return {"relative_path": path, "sha256": checksum}


def test_distinct_photos_with_same_stem_get_collision_safe_names():
    used = set()
    from collections import Counter

    sequence = Counter()
    folder = Path("2026/07-21 - Event/All")
    first = _family_targets(folder, "A/DSCF0001", [_member("A/DSCF0001.RAF", "sha-1")],
                            None, _missing, set(), used, sequence)
    second = _family_targets(folder, "B/DSCF0001", [_member("B/DSCF0001.RAF", "sha-2")],
                             None, _missing, set(), used, sequence)
    assert first == [str(folder / "DSCF0001.RAF")]
    assert second == [str(folder / "DSCF0001_Adopted_001.RAF")]


def test_unverified_split_raw_and_jpeg_families_keep_distinct_target_stems():
    """The allocator cannot infer a capture relationship from a name alone.

    Independently certified capture members are joined by inventory before
    reaching this function; see the DSCF4762 integrated adoption test.
    """
    from collections import Counter

    used = set()
    sequence = Counter()
    folder = Path("2026/07-21 - Event/All")
    raw = _family_targets(folder, "RAW/DSCF0001", [_member("RAW/DSCF0001.RAF", "raw-sha")],
                          None, _missing, set(), used, sequence)
    jpeg = _family_targets(folder, "JPEG/DSCF0001", [_member("JPEG/DSCF0001.JPG", "jpeg-sha")],
                           None, _missing, set(), used, sequence)
    assert raw == [str(folder / "DSCF0001.RAF")]
    assert jpeg == [str(folder / "DSCF0001_Adopted_001.JPG")]


def test_suffix_is_shared_by_all_members_of_a_true_family():
    from collections import Counter

    used = set()
    sequence = Counter()
    folder = Path("2026/07-21 - Event/All")
    _family_targets(folder, "A/DSCF0001", [_member("A/DSCF0001.RAF", "sha-1")],
                    None, _missing, set(), used, sequence)
    targets = _family_targets(
        folder, "B/DSCF0001",
        [_member("B/DSCF0001.RAF", "sha-2"), _member("B/DSCF0001.JPG", "sha-3")],
        None, _missing, set(), used, sequence,
    )
    assert targets == [
        str(folder / "DSCF0001_Adopted_001.RAF"),
        str(folder / "DSCF0001_Adopted_001.JPG"),
    ]

@pytest.mark.parametrize(
    "checksums, known, expected",
    [
        (["raw", "jpeg"], [False, False], None),
        (["raw", "jpeg"], [True, True], None),
        (["raw", "jpeg"], [True, False], "Nur ein Teil"),
        (["raw", "jpeg"], [False, True], "Nur ein Teil"),
        (["same", "same"], [False, False], "denselben SHA-256"),
        (["same", "same"], [True, False], "denselben SHA-256"),
    ],
)
def test_historic_family_duplicate_conflicts_are_distinguished(checksums, known, expected):
    conflict = _family_duplicate_conflict(checksums, known)
    if expected is None:
        assert conflict is None
    else:
        assert expected in conflict


def test_historic_family_duplicate_conflict_rejects_missing_registration_states():
    with pytest.raises(ValueError, match="equal length"):
        _family_duplicate_conflict(["a", "b"], [False])
