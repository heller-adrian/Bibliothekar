from app import __version__ as PACKAGE_VERSION
from pathlib import Path

from app import main
from app import source_helper


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_0290_runtime_defaults_are_portable():
    assert main.APP_VERSION == PACKAGE_VERSION
    assert main.RELEASE_VERSION == "0.47.7"
    assert tuple(map(int, main.DEPLOYMENT_VERSION.split("."))) >= (0, 29, 1)
    assert str(main.WORKSPACE_PATH) == "/workspace"
    assert str(main.DATABASE_DIRECTORY) == "/database"
    assert str(main.LOG_PATH) == "/logs"
    assert str(main.POOL_PROBE_PATH) == "/workspace"
    assert str(main.ARCHIVE_ROOT) == "/main-library"
    assert str(main.IMPORT_ROOT) == "/sources/import"
    assert str(main.NAS_SOURCE_ROOT) == "/sources/nas"
    assert str(main.REMOVABLE_ROOT) == "/sources/removable"


def test_0290_no_fixed_legacy_truenas_host_path_in_runtime():
    helper_source = (REPO_ROOT / "app" / "source_helper.py").read_text()
    main_source = (REPO_ROOT / "app" / "main.py").read_text()
    legacy = "/mnt/apps/appdata/kamera-automatisierung"
    assert legacy not in helper_source
    assert legacy not in main_source
    assert str(source_helper.HOST_MOUNT_ROOT) == "/sources/removable"


def test_0290_compose_uses_custom_app_mount_contract():
    compose = (REPO_ROOT / "compose.example.yaml").read_text()
    assert "ghcr.io/heller-adrian/bibliothekar:patch-" in compose
    assert "KAMERA_WORKSPACE: /workspace" in compose
    assert "KAMERA_POOL_PROBE: /workspace" in compose
    assert "KAMERA_ARCHIVE_ROOT: /main-library" in compose
    assert "KAMERA_IMPORT_ROOT: /sources/import" not in compose
    assert "KAMERA_NAS_SOURCE_ROOT: /sources/nas" in compose
    assert "KAMERA_REMOVABLE_ROOT: /sources/removable" in compose
    assert "${BIBLIOTHEKAR_MAIN_LIBRARY_DIR}:/main-library:ro" in compose
    assert "${BIBLIOTHEKAR_WORKSPACE_DIR}:/workspace" in compose


def test_0290_workspace_owns_sd_backup_structure():
    compose = (REPO_ROOT / "compose.example.yaml").read_text()
    workspace_layout = (REPO_ROOT / "app" / "workspace_layout.py").read_text()
    assert "BIBLIOTHEKAR_SD_BACKUP_DIR" not in compose
    assert 'BACKUP_DIRECTORY_NAME = "SD-Kartensicherungen"' in workspace_layout
    assert 'WORK_DIRECTORY_NAME = "Arbeitsbereich"' in workspace_layout
