"""Real, isolated registered metadata libraries for historical unit fixtures.

A fixture has to establish F14 control BEFORE registering its library.
Otherwise a successful test on an invented fresh control root could mask a
registered installation whose real control state was lost.
"""
from pathlib import Path
from unittest.mock import patch
import os

from app.database import initialize_database
from app.library_registry import initialize_library_registry, adopt_main_library
from app.root_operations import reserve
from app.storage_config import storage_paths, LEGACY_STORAGE_DEFAULTS
from app.workspace_layout import ensure_workspace_layout


def registered_metadata_fixture(tmp_path, *, workspace=None, database=None):
    root=Path(workspace) if workspace is not None else Path(tmp_path)/"workspace"
    db=Path(database) if database is not None else Path(tmp_path)/"kamera.sqlite3"
    # The immutable historical SIGKILL workers construct a nested
    # case/fixture workspace and later adopt it with the already-existing
    # case/archive and the historical case/fixture/workspace/Arbeitsbereich.
    # Materialize those exact paths BEFORE their first F14 control baseline.
    # Ordinary tests still use their own isolated archive and workspaces root.
    case=Path(tmp_path).parent
    historical=(Path(tmp_path).name=="fixture"
                and (case/"registry.sqlite3").is_file()
                and (case/"settings.json").is_file()
                and (case/"archive").is_dir())
    # An immutable historical worker will initialize/adopt the same
    # fixture/registry.sqlite3 again. Never create a second registered
    # catalogue for one workspace: F14 forbids competing registry authorities.
    registry=Path(tmp_path)/("registry.sqlite3" if historical else "bibliothekar-global.sqlite3")
    archive=case/"archive" if historical else Path(tmp_path)/"archive"
    root.mkdir(parents=True, exist_ok=True)
    archive.mkdir(exist_ok=True)
    if historical:
        (root/"Arbeitsbereich").mkdir(exist_ok=True)
    # Preserve real German legacy roots BEFORE layout and F14 registration.
    for name in LEGACY_STORAGE_DEFAULTS.values():
        (root/name).mkdir(exist_ok=True)
    # Register the historical internal metadata children as well. Merely
    # creating Metadatenkorrektur makes ensure_workspace_layout pick newly
    # named English subfolders, so legacy snapshots otherwise reference a
    # missing Mehrfachkorrektur directory. They must exist BEFORE F14 pins
    # directory identities or the library is adopted.
    metadata=root/LEGACY_STORAGE_DEFAULTS["metadata_directory_name"]
    for name in ("Allgemein","Mehrfachkorrektur"):
        (metadata/name).mkdir(exist_ok=True)
    layout=ensure_workspace_layout(root)
    work=layout.get("work_root")
    if work is None:
        work=storage_paths(root)["workspaces_root"]/"main"
        Path(work).mkdir(parents=True,exist_ok=True)
    initialize_database(db)
    # The temporary registry authority is applied before the original control
    # baseline is created, but no registered row exists yet.
    with patch.dict(os.environ,{"KAMERA_REGISTRY_DATABASE":str(registry)}):
        with reserve(root,library_id="main",database=db,kind="startup",
                     ids={"function":"tests.backend.registered_metadata_fixture.bootstrap"},
                     paths=[root,Path(work),archive,*storage_paths(root).values()]):
            pass
        initialize_library_registry(registry)
        adopt_main_library(registry,database_path=db,workspace_root=root,
                           work_root=Path(work),archive_root=archive)
    return db,root,registry
