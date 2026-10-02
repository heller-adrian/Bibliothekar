from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import tempfile


DEFAULT_BACKUP_DIRECTORY_NAME = "SD-Kartensicherungen"
DEFAULT_WORKSPACES_DIRECTORY_NAME = "Arbeitsbereiche"
DEFAULT_METADATA_DIRECTORY_NAME = "Metadatenkorrektur"


class StorageSettingsError(RuntimeError):
    pass


def _config_path() -> Path:
    return Path(os.environ.get("KAMERA_CONFIG", "/config/settings.json"))


def _clean_name(value: Any, *, field: str, default: str) -> str:
    name = " ".join(str(value or default).split()).strip()
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise StorageSettingsError(
            f"{field} muss ein einzelner sicherer Ordnername sein."
        )
    return name


def load_storage_settings() -> dict[str, str]:
    path = _config_path()
    data: dict[str, Any] = {}
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
    except Exception as exc:
        raise StorageSettingsError(
            "Die Anwendungskonfiguration ist nicht lesbar: " + str(exc)
        ) from exc

    storage = data.get("storage")
    if not isinstance(storage, dict):
        storage = {}

    return {
        "backup_directory_name": _clean_name(
            storage.get("backup_directory_name"),
            field="SD-Kartensicherungen",
            default=DEFAULT_BACKUP_DIRECTORY_NAME,
        ),
        "workspaces_directory_name": _clean_name(
            storage.get("workspaces_directory_name"),
            field="Arbeitsbereiche",
            default=DEFAULT_WORKSPACES_DIRECTORY_NAME,
        ),
        "metadata_directory_name": _clean_name(
            storage.get("metadata_directory_name"),
            field="Metadatenkorrektur",
            default=DEFAULT_METADATA_DIRECTORY_NAME,
        ),
    }


def save_storage_settings(values: dict[str, Any]) -> dict[str, str]:
    current = load_storage_settings()
    merged = {
        **current,
        **{
            key: values[key]
            for key in (
                "backup_directory_name",
                "workspaces_directory_name",
                "metadata_directory_name",
            )
            if key in values
        },
    }
    cleaned = {
        "backup_directory_name": _clean_name(
            merged["backup_directory_name"],
            field="SD-Kartensicherungen",
            default=DEFAULT_BACKUP_DIRECTORY_NAME,
        ),
        "workspaces_directory_name": _clean_name(
            merged["workspaces_directory_name"],
            field="Arbeitsbereiche",
            default=DEFAULT_WORKSPACES_DIRECTORY_NAME,
        ),
        "metadata_directory_name": _clean_name(
            merged["metadata_directory_name"],
            field="Metadatenkorrektur",
            default=DEFAULT_METADATA_DIRECTORY_NAME,
        ),
    }
    if len(set(cleaned.values())) != len(cleaned):
        raise StorageSettingsError(
            "Die drei verwalteten Stammordner müssen unterschiedliche Namen haben."
        )

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise StorageSettingsError(
                "Die Anwendungskonfiguration muss ein JSON-Objekt sein."
            )
        data = raw
    data["storage"] = cleaned

    encoded = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".settings-",
        suffix=".json",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return cleaned


def storage_paths(workspace_root: Path) -> dict[str, Path]:
    root = workspace_root.expanduser().resolve(strict=False)
    settings = load_storage_settings()
    return {
        "workspace_root": root,
        "backup_root": (root / settings["backup_directory_name"]).resolve(strict=False),
        "workspaces_root": (root / settings["workspaces_directory_name"]).resolve(strict=False),
        "metadata_root": (root / settings["metadata_directory_name"]).resolve(strict=False),
    }


def default_library_work_root(workspace_root: Path, library_id: str) -> Path:
    clean_id = str(library_id or "").strip()
    if (
        not clean_id
        or clean_id in {".", ".."}
        or "/" in clean_id
        or "\\" in clean_id
    ):
        raise StorageSettingsError("Ungültige Bibliotheks-ID für den Arbeitsbereich.")
    return storage_paths(workspace_root)["workspaces_root"] / clean_id
