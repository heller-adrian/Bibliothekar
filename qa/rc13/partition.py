"""Disjoint collected-test partitions; every collected node runs exactly once."""
import json
import os
from pathlib import Path


def partition_nodes(nodes, partition, count=8):
    assert 0 <= partition < count
    ordered = sorted(nodes)
    assert len(ordered) == len(set(ordered)), 'Duplicate test node IDs'
    return ordered, ordered[partition::count]


def pytest_collection_modifyitems(config, items):
    index = int(os.environ['RC13_PARTITION'])
    count = 8
    nodes, selected = partition_nodes([item.nodeid for item in items], index, count)
    chosen = set(selected)
    excluded = [item for item in items if item.nodeid not in chosen]
    items[:] = [item for item in items if item.nodeid in chosen]
    config.hook.pytest_deselected(items=excluded)
    manifest = {'partition': index, 'partitions': count, 'all_nodes': nodes,
                'selected_nodes': selected,
                'all_files': sorted({node.split('::')[0] for node in nodes})}
    (Path(os.environ['RUNNER_TEMP'])/'rc13-partition.json').write_text(json.dumps(manifest, indent=2))
