"""Optional per-leaf folder layout snapshots.

A parent event can have independently organized root, subevent and day leaves.
Stable event IDs (plus a day when applicable) identify leaves, never a user
editable folder name. This table is additive to the historical parent layout;
old events with no rows continue to use their original layout unmodified.
"""
from __future__ import annotations

import json
from typing import Any
from datetime import datetime, timezone
from app.event_layout import normalize_layout, layout_paths, validate_input_path


def leaf_descriptors(connection: Any, parent: dict[str, Any], prefixes: list[str]) -> list[dict[str, str]]:
    parent_id = str(parent["id"])
    preserve_days = bool(parent.get("preserve_day_folders"))
    children = {
        str(row["folder_name"]): str(row["id"])
        for row in connection.execute(
            "SELECT id,folder_name FROM events WHERE parent_event_id=?", (parent_id,)
        ).fetchall()
    }
    result = []
    seen = set()
    for prefix in prefixes:
        parts = prefix.split("/") if prefix else []
        owner = parent_id
        if parts and parts[0] in children:
            owner = children[parts[0]]
            parts = parts[1:]
        day = parts[-1] if preserve_days and parts and len(parts[-1]) == 10 else ""
        stable = owner + ("@" + day if day else "")
        if stable in seen:
            raise ValueError("Ambiguous structural leaf: " + stable)
        seen.add(stable)
        result.append({"leaf_key": stable, "leaf_prefix": prefix, "event_id": owner, "day": day})
    return result


def stored_leaf_layouts(connection: Any, parent_id: str) -> dict[str, dict[str, Any]]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_leaf_folder_layouts'"
    ).fetchone()
    if not table:
        return {}
    rows = connection.execute(
        "SELECT * FROM event_leaf_folder_layouts WHERE parent_event_id=?",
        (str(parent_id),),
    ).fetchall()
    result = {}
    for row in rows:
        try:
            layout = normalize_layout(json.loads(str(row["layout_json"])))
            input_path = validate_input_path(
                layout, row["input_path"],
                structure_enabled=bool(row["structure_enabled"]),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Stored leaf layout is invalid: " + str(row["leaf_key"])) from exc
        result[str(row["leaf_key"])] = {
            "leaf_key": str(row["leaf_key"]),
            "leaf_prefix": str(row["leaf_prefix"]),
            "structure_enabled": bool(row["structure_enabled"]),
            "input_path": input_path,
            "layout": layout,
        }
    return result


def validate_leaf_choices(
    leaves: list[dict[str, Any]], selected: dict[str, str] | None,
    fallback: str,
) -> list[dict[str, Any]]:
    selected = selected or {}
    keys = {str(leaf["leaf_key"]) for leaf in leaves}
    if set(selected) - keys:
        raise ValueError("Unknown input-folder leaf keys.")
    result = []
    for leaf in leaves:
        layout = normalize_layout(leaf["layout"])
        enabled = bool(leaf["structure_enabled"])
        key = str(leaf["leaf_key"])
        value = selected.get(key, leaf.get("input_path", fallback))
        input_path = validate_input_path(
            layout, value, structure_enabled=enabled,
        )
        if enabled and not input_path:
            raise ValueError("Please choose an input folder for leaf " + key)
        if enabled and input_path not in layout_paths(layout):
            raise ValueError("The input folder does not belong to leaf " + key)
        result.append({**leaf, "layout": layout, "input_path": input_path})
    return result


def save_leaf_layouts(connection: Any, parent_id: str, leaves: list[dict[str, Any]], *, now: str) -> None:
    """Call in the same transaction as the confirmed event revision."""
    connection.execute(
        "DELETE FROM event_leaf_folder_layouts WHERE parent_event_id=?",
        (str(parent_id),),
    )
    for leaf in leaves:
        connection.execute(
            """INSERT INTO event_leaf_folder_layouts(
               parent_event_id,leaf_key,leaf_prefix,structure_enabled,
               input_path,layout_json,updated_at) VALUES (?,?,?,?,?,?,?)""",
            (
                str(parent_id), str(leaf["leaf_key"]), str(leaf["leaf_prefix"]),
                int(bool(leaf["structure_enabled"])), str(leaf["input_path"]),
                json.dumps(leaf["layout"], ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
