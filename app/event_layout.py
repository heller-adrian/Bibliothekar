"""Configurable per-event folder layouts for Bibliothekar 0.28.0."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
import json

DEFAULT_LAYOUT = {
    "version": 1,
    "nodes": [
        {"id": "legacy-alle", "name": "Alle", "children": []},
        {"id": "legacy-sortiert", "name": "Sortiert", "children": []},
        {"id": "legacy-export", "name": "Export", "role": "export", "children": []},
    ],
}
DEFAULT_SETTING = {
    "structure_enabled": True,
    "input_path": "Alle",
    "layout": DEFAULT_LAYOUT,
}
RESERVED_NAMES = {"event.json"}


class EventLayoutError(ValueError):
    pass


def _safe_name(value: Any) -> str:
    name = str(value or "").strip()
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or name.casefold() in {item.casefold() for item in RESERVED_NAMES}
    ):
        raise EventLayoutError("Ungültiger Ordnername: " + (name or "—"))
    return name


def normalize_layout(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EventLayoutError("Die Ordnerstruktur ist ungültig.")
    raw_nodes = value.get("nodes")
    if not isinstance(raw_nodes, list):
        raise EventLayoutError("Die Ordnerstruktur enthält keine gültige Ordnerliste.")

    seen_ids: set[str] = set()
    seen_roles: set[str] = set()

    def normalize_nodes(nodes: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        sibling_names: set[str] = set()
        for item in nodes:
            if not isinstance(item, dict):
                raise EventLayoutError("Ein Ordnerknoten ist ungültig.")
            node_id = str(item.get("id") or "").strip()
            if not node_id or node_id in seen_ids:
                raise EventLayoutError("Jeder Ordner benötigt eine eindeutige interne ID.")
            seen_ids.add(node_id)
            name = _safe_name(item.get("name"))
            folded = name.casefold()
            if folded in sibling_names:
                raise EventLayoutError("Ordnernamen derselben Ebene müssen eindeutig sein.")
            sibling_names.add(folded)
            role = str(item.get("role") or "").strip().casefold()
            # Alte 0.28.x-Snapshots besitzen noch keine Rollenangabe. Der
            # historische Exportknoten bleibt deshalb semantisch ein
            # Exportordner, auch wenn er später umbenannt wird.
            if not role and node_id == "legacy-export":
                role = "export"
            if role and role != "export":
                raise EventLayoutError("Unbekannte Ordnerrolle: " + role)
            if role:
                if role in seen_roles:
                    raise EventLayoutError("Die Rolle „Exportordner“ darf nur einmal vergeben werden.")
                seen_roles.add(role)

            children = item.get("children") or []
            if not isinstance(children, list):
                raise EventLayoutError("Unterordner sind ungültig.")
            normalized_node = {
                "id": node_id,
                "name": name,
                "children": normalize_nodes(children),
            }
            if role:
                normalized_node["role"] = role
            result.append(normalized_node)
        return result

    return {"version": 1, "nodes": normalize_nodes(raw_nodes)}


def layout_paths(layout: dict[str, Any]) -> list[str]:
    normalized = normalize_layout(layout)
    result: list[str] = []

    def walk(nodes: list[dict[str, Any]], prefix: tuple[str, ...] = ()) -> None:
        for node in nodes:
            parts = (*prefix, str(node["name"]))
            result.append(PurePosixPath(*parts).as_posix())
            walk(node.get("children") or [], parts)

    walk(normalized["nodes"])
    return result


def layout_role_paths(layout: dict[str, Any], role: str) -> list[str]:
    """Return configured organization paths carrying one semantic role."""
    normalized = normalize_layout(layout)
    wanted = str(role or "").strip().casefold()
    result: list[str] = []

    def walk(nodes: list[dict[str, Any]], prefix: tuple[str, ...] = ()) -> None:
        for node in nodes:
            parts = (*prefix, str(node["name"]))
            if str(node.get("role") or "").casefold() == wanted:
                result.append(PurePosixPath(*parts).as_posix())
            walk(node.get("children") or [], parts)

    walk(normalized["nodes"])
    return result


def validate_input_path(
    layout: dict[str, Any],
    input_path: Any,
    *,
    structure_enabled: bool,
) -> str:
    raw = str(input_path or "").replace("\\", "/").strip("/")
    # Deaktivieren löscht die konfigurierte Struktur nicht. Der Input-Pfad
    # bleibt als Teil des Ereignis-/Global-Snapshots gespeichert und wird beim
    # erneuten Aktivieren wieder benutzt. Ein leerer Pfad bedeutet unabhängig
    # davon ausdrücklich "direkt im strukturellen Blatt".
    if not raw:
        return ""
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise EventLayoutError("Der Input-Ordner besitzt einen unsicheren Pfad.")
    valid = set(layout_paths(layout))
    if path.as_posix() not in valid:
        raise EventLayoutError("Der gewählte Input-Ordner existiert nicht in der Ereignisstruktur.")
    return path.as_posix()


def _table_exists(connection: Any, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def get_global_default(connection: Any) -> dict[str, Any]:
    if not _table_exists(connection, "app_settings"):
        return json.loads(json.dumps(DEFAULT_SETTING))
    row = connection.execute(
        "SELECT value_json FROM app_settings WHERE setting_key='event_folder_layout_default'"
    ).fetchone()
    if row is None:
        return json.loads(json.dumps(DEFAULT_SETTING))
    try:
        data = json.loads(str(row["value_json"]))
    except Exception as exc:
        raise EventLayoutError("Die globale Ordnerstruktur ist beschädigt.") from exc
    layout = normalize_layout(data.get("layout") or DEFAULT_LAYOUT)
    enabled = bool(data.get("structure_enabled", True))
    input_path = validate_input_path(layout, data.get("input_path", "Alle"), structure_enabled=enabled)
    return {"structure_enabled": enabled, "input_path": input_path, "layout": layout}


def set_global_default(
    connection: Any,
    value: dict[str, Any],
    *,
    updated_at: str,
) -> dict[str, Any]:
    layout = normalize_layout(value.get("layout") or DEFAULT_LAYOUT)
    enabled = bool(value.get("structure_enabled", True))
    input_path = validate_input_path(layout, value.get("input_path", ""), structure_enabled=enabled)
    stored = {"structure_enabled": enabled, "input_path": input_path, "layout": layout}
    connection.execute(
        """INSERT INTO app_settings(setting_key,value_json,updated_at)
           VALUES ('event_folder_layout_default',?,?)
           ON CONFLICT(setting_key) DO UPDATE SET
             value_json=excluded.value_json,updated_at=excluded.updated_at""",
        (json.dumps(stored, ensure_ascii=False, sort_keys=True), updated_at),
    )
    return stored


def ensure_event_layout_snapshot(connection: Any, event_id: str, *, now: str) -> dict[str, Any]:
    if not _table_exists(connection, "event_folder_layouts"):
        default = get_global_default(connection)
        return {
            "event_id": str(event_id),
            "structure_enabled": bool(default["structure_enabled"]),
            "input_path": str(default["input_path"]),
            "layout": default["layout"],
            "revision": 1,
        }
    row = connection.execute(
        "SELECT * FROM event_folder_layouts WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if row is None:
        default = get_global_default(connection)
        connection.execute(
            """INSERT INTO event_folder_layouts(
                   event_id,structure_enabled,input_path,layout_json,revision,created_at,updated_at)
               VALUES (?,?,?,?,1,?,?)""",
            (
                event_id,
                int(default["structure_enabled"]),
                default["input_path"],
                json.dumps(default["layout"], ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM event_folder_layouts WHERE event_id=?",
            (event_id,),
        ).fetchone()
    return event_layout_from_row(row)


def event_layout_from_row(row: Any) -> dict[str, Any]:
    if row is None:
        raise EventLayoutError("Die Ereignisstruktur wurde nicht gefunden.")
    try:
        layout = normalize_layout(json.loads(str(row["layout_json"])))
    except Exception as exc:
        if isinstance(exc, EventLayoutError):
            raise
        raise EventLayoutError("Die Ereignisstruktur ist beschädigt.") from exc
    enabled = bool(row["structure_enabled"])
    input_path = validate_input_path(layout, row["input_path"], structure_enabled=enabled)
    return {
        "event_id": str(row["event_id"]),
        "structure_enabled": enabled,
        "input_path": input_path,
        "layout": layout,
        "revision": int(row["revision"] or 1),
    }


def get_event_layout(connection: Any, event_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM event_folder_layouts WHERE event_id=?",
        (event_id,),
    ).fetchone()
    return event_layout_from_row(row)


def update_event_layout(
    connection: Any,
    event_id: str,
    *,
    structure_enabled: bool,
    input_path: str,
    layout: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    normalized = normalize_layout(layout)
    clean_input = validate_input_path(
        normalized,
        input_path,
        structure_enabled=bool(structure_enabled),
    )
    connection.execute(
        """UPDATE event_folder_layouts
           SET structure_enabled=?,input_path=?,layout_json=?,
               revision=revision+1,updated_at=?
           WHERE event_id=?""",
        (
            int(bool(structure_enabled)),
            clean_input,
            json.dumps(normalized, ensure_ascii=False, sort_keys=True),
            updated_at,
            event_id,
        ),
    )
    return get_event_layout(connection, event_id)


def leaf_layout_directories(layout_state: dict[str, Any]) -> list[str]:
    if not bool(layout_state.get("structure_enabled")):
        return []
    return layout_paths(layout_state["layout"])
