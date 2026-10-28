"""The release must prove complete coverage, including all heavy crash cases."""
import pytest
from qa.rc13.partition import partition_nodes


def test_partitions_cover_each_test_once():
    nodes = [f'tests/backend/test_crash.py::test_boundary[{i}]' for i in range(257)]
    selected = []
    for index in range(8):
        all_nodes, part = partition_nodes(list(reversed(nodes)), index)
        assert all_nodes == sorted(nodes)
        selected.extend(part)
    assert len(selected) == len(set(selected)) == len(nodes)
    assert set(selected) == set(nodes)


def test_duplicate_collected_ids_are_not_accepted():
    with pytest.raises(AssertionError, match='Duplicate'):
        partition_nodes(['same', 'same'], 0)
