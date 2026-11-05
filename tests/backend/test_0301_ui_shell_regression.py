import shutil
import subprocess

import pytest

from app import main, source_helper, ui_shell
from tests.backend.release_contract import EXPECTED_RELEASE_VERSION


def _fnv1a32(text: str) -> str:
    value = 0x811C9DC5
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return f"{value:08x}"


def test_0301_shell_css_matches_frozen_0287_design():
    assert len(ui_shell.BIBLIOTHEKAR_CSS) == 44539
    assert _fnv1a32(ui_shell.BIBLIOTHEKAR_CSS) == "d024e005"


def test_0301_shell_javascript_version_block_is_real_javascript():
    malformed = (
        'document.querySelectorAll("[data-bk-version]").forEach(node => {\\n'
    )
    assert malformed not in ui_shell.BIBLIOTHEKAR_JS

    expected = """document.querySelectorAll("[data-bk-version]").forEach(node => {
      const deployment = data.deployment_version || data.version || "";
      node.textContent = deployment;
    });"""
    assert expected in ui_shell.BIBLIOTHEKAR_JS


def test_0301_complete_shell_javascript_has_valid_syntax(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node ist in dieser Testumgebung nicht verfügbar")

    script_path = tmp_path / "bibliothekar-shell.js"
    script_path.write_text(ui_shell.BIBLIOTHEKAR_JS, encoding="utf-8")
    result = subprocess.run(
        [node, "--check", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_0301_critical_shell_initializers_are_present():
    script = ui_shell.BIBLIOTHEKAR_JS

    assert "applyTheme(stored);" in script
    assert 'menuButton?.addEventListener("click"' in script
    assert "async function refreshTasks()" in script
    assert 'fetch("/api/tasks", {cache:"no-store", headers:{"X-Bibliothekar-Library":bkLibraryId}})' in script
    assert 'fetch("/api/health", {cache: "no-store"})' in script


def test_0301_task_backend_contract_is_unchanged():
    source = main.api_global_tasks.__code__
    assert source.co_argcount == 0


def test_0301_versions_are_consistent():
    assert main.DEPLOYMENT_VERSION == EXPECTED_RELEASE_VERSION
    deployment = tuple(map(int, main.DEPLOYMENT_VERSION.split("-", 1)[0].split(".")))
    assert deployment >= (0, 30, 1)
    assert source_helper.app.version == main.DEPLOYMENT_VERSION
    assert source_helper.healthz()["version"] == main.DEPLOYMENT_VERSION


def test_0301_compose_uses_patch_image():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    compose = (repo_root / "compose.example.yaml").read_text()
    assert (
        "ghcr.io/heller-adrian/bibliothekar:"
        + EXPECTED_RELEASE_VERSION
    ) in compose
