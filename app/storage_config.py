from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import tempfile


# Only genuinely new installations use English folder defaults. Existing
# folders from German installations retain their established physical paths.
DEFAULT_BACKUP_DIRECTORY_NAME = "SD Card Backups"
DEFAULT_WORKSPACES_DIRECTORY_NAME = "Library Workspaces"
DEFAULT_METADATA_DIRECTORY_NAME = "Metadata Correction"
DEFAULT_TRASH_DIRECTORY_NAME = "Trash"

LEGACY_STORAGE_DEFAULTS = {
    "backup_directory_name": "SD-Kartensicherungen",
    "workspaces_directory_name": "Arbeitsbereiche",
    "metadata_directory_name": "Metadatenkorrektur",
    "trash_directory_name": "Papierkorb",
}

ENGLISH_STORAGE_DEFAULTS = {
    "backup_directory_name": DEFAULT_BACKUP_DIRECTORY_NAME,
    "workspaces_directory_name": DEFAULT_WORKSPACES_DIRECTORY_NAME,
    "metadata_directory_name": DEFAULT_METADATA_DIRECTORY_NAME,
    "trash_directory_name": DEFAULT_TRASH_DIRECTORY_NAME,
}


def _effective_directory_default(setting: str, workspace_root: Path | None = None) -> str:
    """Avoid silently relocating existing German workspaces on upgrade.

    The configured workspace mount is inspected without creating or moving
    anything. Persisted user choices take precedence in load_storage_settings.
    """
    english = ENGLISH_STORAGE_DEFAULTS[setting]
    legacy = LEGACY_STORAGE_DEFAULTS[setting]
    workspace = Path(workspace_root) if workspace_root is not None else Path(os.environ.get("KAMERA_WORKSPACE", "/workspace"))
    try:
        if (workspace / legacy).is_dir():
            return legacy
    except OSError:
        pass
    return english


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


def load_storage_settings(*, workspace_root: Path | None = None) -> dict[str, str]:
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

    # Once administration names have been observed under F14, absence of a
    # German directory must not silently select an empty English replacement.
    workspace=Path(workspace_root) if workspace_root is not None else Path(os.environ.get('KAMERA_WORKSPACE','/workspace'))
    from app.root_operations import _control_location,_read
    pinned=_read(_control_location(workspace)/'state.json',{}).get('storage_names',{})
    def default(key):
        return pinned.get(key) or _effective_directory_default(key,workspace_root)

    return {
        "backup_directory_name": _clean_name(
            storage.get("backup_directory_name"),
            field="SD-Kartensicherungen",
            default=default("backup_directory_name"),
        ),
        "workspaces_directory_name": _clean_name(
            storage.get("workspaces_directory_name"),
            field="Arbeitsbereiche",
            default=default("workspaces_directory_name"),
        ),
        "metadata_directory_name": _clean_name(
            storage.get("metadata_directory_name"),
            field="Metadatenkorrektur",
            default=default("metadata_directory_name"),
        ),
        "trash_directory_name": _clean_name(
            storage.get("trash_directory_name"),
            field="Papierkorb",
            default=default("trash_directory_name"),
        ),
    }


def normalize_storage_settings(values: dict[str, Any]) -> dict[str, str]:
    current = load_storage_settings()
    merged = {
        **current,
        **{
            key: values[key]
            for key in (
                "backup_directory_name",
                "workspaces_directory_name",
                "metadata_directory_name",
                "trash_directory_name",
            )
            if key in values
        },
    }
    cleaned = {
        "backup_directory_name": _clean_name(
            merged["backup_directory_name"],
            field="SD-Kartensicherungen",
            default=_effective_directory_default("backup_directory_name"),
        ),
        "workspaces_directory_name": _clean_name(
            merged["workspaces_directory_name"],
            field="Arbeitsbereiche",
            default=_effective_directory_default("workspaces_directory_name"),
        ),
        "metadata_directory_name": _clean_name(
            merged["metadata_directory_name"],
            field="Metadatenkorrektur",
            default=_effective_directory_default("metadata_directory_name"),
        ),
        "trash_directory_name": _clean_name(
            merged["trash_directory_name"],
            field="Papierkorb",
            default=_effective_directory_default("trash_directory_name"),
        ),
    }
    if len(set(cleaned.values())) != len(cleaned):
        raise StorageSettingsError(
            "Die vier verwalteten Stammordner müssen unterschiedliche Namen haben."
        )
    return cleaned


def save_storage_settings(values: dict[str, Any]) -> dict[str, str]:
    """Reject the retired storage-name mutator, including internal callers.

    Existing persisted custom names remain readable. This function never
    rewrites them, including when a caller submits an identical payload.
    """
    raise StorageSettingsError("Die Verwaltungsordnernamen sind nicht mehr änderbar.")


def storage_paths(workspace_root: Path) -> dict[str, Path]:
    root = workspace_root.expanduser().resolve(strict=False)
    settings = load_storage_settings(workspace_root=root)
    return {
        "workspace_root": root,
        "backup_root": (root / settings["backup_directory_name"]).resolve(strict=False),
        "workspaces_root": (root / settings["workspaces_directory_name"]).resolve(strict=False),
        "metadata_root": (root / settings["metadata_directory_name"]).resolve(strict=False),
        "trash_root": (root / settings["trash_directory_name"]).resolve(strict=False),
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


def load_metadata_correction_settings() -> dict[str, str]:
    """Global settings for the independent „Allgemein“ metadata host path."""
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

    section = data.get("metadata_correction")
    if not isinstance(section, dict):
        section = {}

    if "general_root" in section:
        raw_root = str(section.get("general_root") or "").strip()
    else:
        raw_root = str(os.environ.get("KAMERA_METADATA_GENERAL_ROOT", "") or "").strip()
    if raw_root:
        root = Path(raw_root).expanduser()
        if not root.is_absolute():
            raise StorageSettingsError(
                "Der Host-Path für die allgemeine Metadatenkorrektur muss absolut sein."
            )
        raw_root = str(root.resolve(strict=False))

    return {"general_root": raw_root}


def save_metadata_correction_settings(values: dict[str, Any]) -> dict[str, str]:
    current = load_metadata_correction_settings()
    raw_root = str(values.get("general_root", current["general_root"]) or "").strip()

    if raw_root:
        root = Path(raw_root).expanduser()
        if not root.is_absolute():
            raise StorageSettingsError(
                "Der Host-Path für die allgemeine Metadatenkorrektur muss absolut sein."
            )
        raw_root = str(root.resolve(strict=False))

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

    section = data.get("metadata_correction")
    if not isinstance(section, dict):
        section = {}
    data["metadata_correction"] = {
        **section,
        "general_root": raw_root,
    }

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

    return {"general_root": raw_root}
