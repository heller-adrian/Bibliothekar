"""Regression evidence for legacy adoption: families, names, and content reuse.

These tests operate on synthetic in-memory naming state only.  They never touch
real archives or an active TrueNAS installation.
"""
from pathlib import Path

import pytest

from app.legacy_adoption_plan import (_family_duplicate_conflict, _family_targets,
                                      _automatic_family_targets, _adoption_occurrence_sequences)


def _missing(_path):
    return None


def _member(path, checksum):
    return {"relative_path": path, "sha256": checksum}


def test_two_distinct_photos_with_same_target_get_001_and_002():
    from collections import Counter
    folder = Path("event/All")
    used = set()
    sequence = Counter()
    first = _family_targets(
        folder, "A/DSCF0001", [_member("A/DSCF0001.RAF", "sha-1")],
        None, _missing, set(), used, sequence, collision_index=1,
    )
    second = _family_targets(
        folder, "B/DSCF0001", [_member("B/DSCF0001.RAF", "sha-2")],
        None, _missing, set(), used, sequence, collision_index=2,
    )
    assert first == [str(folder / "DSCF0001_001.RAF")]
    assert second == [str(folder / "DSCF0001_002.RAF")]


def test_distinct_extensions_do_not_occupy_a_whole_camera_stem():
    from collections import Counter
    folder = Path("event/All")
    used = set()
    seq = Counter()
    raw = _family_targets(
        folder, "anywhere/DSCF0001", [_member("a/DSCF0001.RAF", "raw")],
        None, _missing, set(), used, seq,
    )
    jpeg = _family_targets(
        folder, "elsewhere/DSCF0001", [_member("b/DSCF0001.JPG", "jpeg")],
        None, _missing, set(), used, seq,
    )
    assert raw == [str(folder / "DSCF0001.RAF")]
    assert jpeg == [str(folder / "DSCF0001.JPG")]


def test_collision_sequence_is_shared_across_a_family():
    from collections import Counter
    folder = Path("event/All")
    used = set()
    seq = Counter()
    first = _family_targets(
        folder, "A/DSCF0001", [_member("A/DSCF0001.RAF", "sha-1")],
        None, _missing, set(), used, seq, collision_index=1,
    )
    second = _family_targets(
        folder, "B/DSCF0001",
        [_member("B/DSCF0001.RAF", "sha-2"), _member("B/DSCF0001.JPG", "sha-3")],
        None, _missing, set(), used, seq, collision_index=2,
    )
    assert first == [str(folder / "DSCF0001_001.RAF")]
    assert second == [str(folder / "DSCF0001_002.RAF"),
                      str(folder / "DSCF0001_002.JPG")]


def test_all_exact_hash_copies_receive_duplicate_001_and_002():
    from collections import Counter
    folder = Path("event/All")
    used = set()
    seq = Counter()
    original = _family_targets(
        folder, "A/DSCF0001", [_member("A/DSCF0001.RAF", "same-sha")],
        None, _missing, set(), used, seq, duplicate_index=1,
    )
    second = _family_targets(
        folder, "B/DSCF0001", [_member("B/DSCF0001.RAF", "same-sha")],
        None, _missing, set(), used, seq, duplicate_index=2,
    )
    assert original == [str(folder / "DSCF0001_Duplicate_001.RAF")]
    assert second == [str(folder / "DSCF0001_Duplicate_002.RAF")]


def test_script_reuses_real_subseconds_and_numbers_all_exact_millisecond_collisions():
    from collections import Counter
    folder = Path("event/All")
    used = set()
    names = {}
    second = "2026-07-19T17:11:37"
    distinct = []
    for ms in ("125", "875"):
        distinct.extend(_automatic_family_targets(
            folder, "A", [_member("A/a.RAF", "some-sha")], second+"."+ms+"+03:00",
            "Fuji-X-E5", True, names, set(), used,
        ))
    assert distinct == [
        str(folder / "20260719_171137125_Fuji-X-E5.RAF"),
        str(folder / "20260719_171137875_Fuji-X-E5.RAF"),
    ]
    used.clear()
    equal_ms = []
    for _ in range(2):
        equal_ms.extend(_automatic_family_targets(
            folder, "A", [_member("A/a.RAF", "other-sha")], second+".425+03:00",
            "Fuji-X-E5", True, names, set(), used, number_all=True,
        ))
    assert equal_ms == [
        str(folder / "20260719_171137425_Fuji-X-E5_001.RAF"),
        str(folder / "20260719_171137425_Fuji-X-E5_002.RAF"),
    ]


def test_script_identical_copies_get_duplicate_suffix_not_arbitrary_original():
    folder = Path("event/All")
    used = set()
    result = []
    for index in (1, 2):
        result.extend(_automatic_family_targets(
            folder, "A", [_member("A/a.JPG", "same-sha")],
            "2026-07-19T17:11:37.425+03:00", "Fuji-X-E5",
            True, {}, set(), used, duplicate_index=index,
        ))
    assert result == [
        str(folder / "20260719_171137425_Fuji-X-E5_Duplicate_001.JPG"),
        str(folder / "20260719_171137425_Fuji-X-E5_Duplicate_002.JPG"),
    ]


def test_occurrence_detection_uses_sha_and_actual_target_path_not_source_folders():
    import json
    folder = Path("event/All")
    def item(key, ending, sha):
        member = {"relative_path": key + ending, "sha256": sha,
                  "metadata_json": json.dumps({"media_type": "raw" if ending == ".RAF" else "jpeg"})}
        return (key, [member], "2026-07-19T17:11:37+03:00", {},
                (None, folder, None, {"structure_enabled": False}))
    selected = [
        item("some/DSCF1000", ".RAF", "same-sha"),
        item("any/where/DSCF1000", ".RAF", "same-sha"),
        item("other/DSCF1000", ".JPG", "jpeg-sha"),
    ]
    duplicates, collisions, _ = _adoption_occurrence_sequences(selected, {})
    assert duplicates["some/DSCF1000"] == 2
    assert duplicates["any/where/DSCF1000"] == 1
    assert "other/DSCF1000" not in duplicates
    assert set(collisions) == {"some/DSCF1000", "any/where/DSCF1000"}


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
