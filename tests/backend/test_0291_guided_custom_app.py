
from tests.backend.release_contract import EXPECTED_RELEASE_VERSION
from tests.backend.default_constant_fixture import shipped_constants
from app import __version__ as PACKAGE_VERSION
from pathlib import Path

from app import container_supervisor
from app import main
from app import source_helper


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_0291_keeps_frozen_camera_core_and_bumps_only_deployment():
    assert main.APP_VERSION == PACKAGE_VERSION
    assert main.RELEASE_VERSION == EXPECTED_RELEASE_VERSION
    assert tuple(map(int, main.DEPLOYMENT_VERSION.split("-", 1)[0].split("."))) >= (0, 29, 1)


def test_0291_image_starts_single_container_supervisor_as_root():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    assert "USER 0:0" in dockerfile
    assert 'CMD ["python", "-m", "app.container_supervisor"]' in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' not in dockerfile


def test_0291_supervisor_separates_root_helper_from_web_uid(monkeypatch):
    for name,value in shipped_constants(container_supervisor,["WEB_UID","WEB_GID","HELPER_ENABLED"]).items():monkeypatch.setattr(container_supervisor,name,value)
    assert container_supervisor.WEB_UID == 568
    assert container_supervisor.WEB_GID == 568
    assert container_supervisor.HELPER_ENABLED is False  # optional privileged helper requires opt-in
    assert container_supervisor.web_command()[-3:] == [
        "0.0.0.0",
        "--port",
        "8080",
    ]
    assert container_supervisor.helper_command()[-3:] == [
        "127.0.0.1",
        "--port",
        "8090",
    ]


def test_0291_source_helper_mounts_directly_without_host_namespace(monkeypatch):
    for name,value in shipped_constants(source_helper,["MOUNT_ROOT","HOST_MOUNT_ROOT"]).items():monkeypatch.setattr(source_helper,name,value)
    helper_source = (REPO_ROOT / "app" / "source_helper.py").read_text()
    assert "nsenter" not in helper_source
    assert str(source_helper.MOUNT_ROOT) == "/sources/removable"
    assert source_helper.HOST_MOUNT_ROOT == source_helper.MOUNT_ROOT
    assert '"mount",' in helper_source
    assert '"umount",' in helper_source


def test_0291_compose_is_one_service_and_guided_custom_app_compatible():
    compose = (REPO_ROOT / "compose.example.yaml").read_text()
    assert ("ghcr.io/heller-adrian/bibliothekar:" + EXPECTED_RELEASE_VERSION) in compose
    assert "\n  source-helper:" not in compose
    assert "pid: host" not in compose
    assert "network_mode:" not in compose
    assert 'user: "0:0"' in compose
    import yaml
    base=yaml.safe_load(compose)['services']['bibliothekar']
    removable=yaml.safe_load((REPO_ROOT/'compose.removable.yaml').read_text())['services']['bibliothekar']
    assert not base.get('privileged',False)
    assert base['environment']['KAMERA_SOURCE_HELPER_ENABLED']=='false'
    assert removable['privileged'] is True
    assert removable['environment']['KAMERA_SOURCE_HELPER_ENABLED']=='true'
    assert '/run/udev:/run/udev:ro' in removable['volumes']
    assert all(row['target']!='/sources/removable' for row in base['volumes'])


def test_0291_removable_media_are_still_forced_read_only():
    helper_source = (REPO_ROOT / "app" / "source_helper.py").read_text()
    assert 'options = "ro,nosuid,nodev,noexec"' in helper_source
    assert "Die Quelle konnte nicht nachweislich nur lesend eingebunden werden." in helper_source
