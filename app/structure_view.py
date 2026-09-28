"""One structure renderer for previews, stored events and portable documents."""
from pathlib import PurePosixPath


def render_structure(year, folder, day_keys=(), children=(), preserve_days=False):
    paths = []
    default_days = sorted(set(day_keys or ()))
    child_list = list(children or ())
    branches = []
    # The parent branch represents files assigned directly to the parent.
    # If children exist and the parent has no own capture days, rendering an
    # empty Alle/Sortiert/Export triplet would describe folders that are not
    # needed. A parent without children still keeps its normal triplet.
    if default_days or not child_list:
        branches.append(("", default_days))
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
        branches.append((branch, child_days))

    for branch, branch_days in branches:
        rendered_days = branch_days if preserve_days and branch_days else [""]
        for day in rendered_days:
            for leaf in ("Alle", "Sortiert", "Export"):
                paths.append(
                    "/".join(
                        x
                        for x in [str(year), str(folder), branch, day, leaf]
                        if x
                    )
                )

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
