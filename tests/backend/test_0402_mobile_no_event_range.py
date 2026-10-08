"""0.43.4: mobile Von–Bis-Darstellung und Release-Vertrag."""
from pathlib import Path

from app import __version__ as PACKAGE_VERSION
from app import main, source_helper


def test_0402_version_contract():
    assert PACKAGE_VERSION == "0.43.4"
    assert main.APP_VERSION == PACKAGE_VERSION
    assert main.DEPLOYMENT_VERSION == PACKAGE_VERSION
    assert source_helper.app.version == PACKAGE_VERSION
    assert source_helper.healthz()["version"] == PACKAGE_VERSION
    assert "patch-0.43.4" in Path("compose.example.yaml").read_text(encoding="utf-8")
    assert "0.43.4 · Kamerakern 0.32.11" in Path("app/ui_shell.py").read_text(encoding="utf-8")


def test_0402_mobile_no_event_range_has_one_heading_and_two_full_rows():
    for path in ("app/workspace_ui.py", "app/events_ui.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert "no-event-mobile-range-title" in source
        assert "Von–Bis" in source
        assert "no-event-end-date-mirror" in source
        assert "data-segment-end-day-display" in source
        assert "data-segment-end-month-year-display" in source
        assert 'aria-label="Von"' in source
        assert 'aria-label="Bis"' in source
        assert ".no-event-segment-fields .no-event-desktop-caption" in source
        assert "grid-row:2;" in source
        assert "grid-row:3;" in source


def test_0402_readme_declares_latest_update_channel():
    source = Path("README.md").read_text(encoding="utf-8")
    assert "Aktuelle veröffentlichte Version: **0.43.4**" in source
    assert "ghcr.io/heller-adrian/bibliothekar:latest" in source
    assert "latest" in source
