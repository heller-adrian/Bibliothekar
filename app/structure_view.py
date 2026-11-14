"""One structure renderer for previews, stored events and portable documents."""
from pathlib import PurePosixPath


def _layout_paths(layout_state=None):
    if layout_state is None:
        return ["Alle", "Sortiert", "Export"]
    if not bool(layout_state.get("structure_enabled", True)):
        return [""]
    from app.event_layout import layout_paths
    paths = layout_paths(layout_state.get("layout") or {"version": 1, "nodes": []})
    return paths or [""]


def render_structure(year, folder, day_keys=(), children=(), preserve_days=False, layout_state=None, *, leaf_layouts=(), parent_event_id=None):
    paths = []
    default_days = sorted(set(day_keys or ()))
    child_list = list(children or ())
    branches = []
    leaf_by_key = {str(leaf.get('leaf_key')): leaf for leaf in (leaf_layouts or [])}
    # The parent branch represents files assigned directly to the parent.
    flat_child_days = {day for child in child_list if child.get("folder_name") == "" for day in child.get("day_keys", [])}
    default_days = sorted(set(default_days) | flat_child_days)
    if default_days or not child_list or any(child.get("folder_name") == "" for child in child_list):
        branches.append(("", default_days, str(parent_event_id or ""), layout_state))
    seen = {""}
    for child in child_list:
        branch = str(child.get("folder_name") or child.get("folder") or "")
        if branch in seen:
            continue
        seen.add(branch)
        child_days = (
            sorted(set(child.get("day_keys") or ()))
            if "day_keys" in child
            else default_days
        )
        branches.append((branch, child_days, str(child.get("id") or ""), child.get("folder_layout") or layout_state))

    for branch, branch_days, owner_id, branch_layout in branches:
        rendered_days = branch_days if preserve_days and branch_days else [""]
        for day in rendered_days:
            key = owner_id + ('@' + day if day else '')
            leaf_layout = leaf_by_key.get(key) or leaf_by_key.get(owner_id) or branch_layout
            for leaf in _layout_paths(leaf_layout):
                parts = [str(year), str(folder), branch, day]
                if leaf:
                    parts.extend(PurePosixPath(leaf).parts)
                paths.append("/".join(x for x in parts if x))

    tree = {}
    for path in paths:
        cursor = tree
        for part in PurePosixPath(path).parts:
            cursor = cursor.setdefault(part, {})

    lines = []

    def walk(node, prefix="", root=False):
        for index, (name, children) in enumerate(node.items()):
            last = index == len(node) - 1
            lines.append(
                prefix
                + ("" if root else ("└── " if last else "├── "))
                + name
            )
            walk(
                children,
                prefix + ("" if root else ("    " if last else "│   ")),
            )

    walk(tree, root=True)
    return lines
