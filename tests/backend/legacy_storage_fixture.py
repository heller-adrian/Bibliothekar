"""Explicit historical layout for legacy media fixtures; no production bypass."""
from pathlib import Path
from app.storage_config import LEGACY_STORAGE_DEFAULTS

def provision_legacy_storage(workspace):
    root=Path(workspace)
    for name in LEGACY_STORAGE_DEFAULTS.values():(root/name).mkdir(parents=True,exist_ok=True)
    from app.managed_directory_names import directory_name
    metadata=root/LEGACY_STORAGE_DEFAULTS['metadata_directory_name']
    for kind in ('metadata_general','metadata_multiple'):
        (metadata/directory_name(metadata,kind)).mkdir(exist_ok=True)
    (root/'SD-Kartensicherungen/Freigewordene Archivdateien').mkdir(exist_ok=True)
    work=root/'Arbeitsbereich'
    if work.is_dir() and not work.is_symlink():(work/'Später zuordnen').mkdir(exist_ok=True)
