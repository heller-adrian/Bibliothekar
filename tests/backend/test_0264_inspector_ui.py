from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_version_sources_are_consistent():
    from app import __version__ as package_version
    from tests.backend.release_contract import EXPECTED_RELEASE_VERSION, EXPECTED_STABLE_VERSION

    main_source = source("app/main.py")
    assert "from app import __version__" in main_source
    assert "APP_VERSION = __version__" in main_source
    readme = source("README.md")
    assert package_version == EXPECTED_RELEASE_VERSION
    assert f"**Stable version:** {EXPECTED_STABLE_VERSION}" in readme
    assert f"ghcr.io/heller-adrian/bibliothekar:{EXPECTED_STABLE_VERSION}" in readme
    if package_version != EXPECTED_STABLE_VERSION:
        assert f"**Release candidate version:** {package_version}" in readme
    assert "Deploy the Custom App" in readme


def test_workspace_preview_preserves_tree_and_db_facts():
    html = source("app/workspace_ui.py")
    assert "white-space: pre;" in html
    assert "function fitTreeText(root)" in html
    assert "function renderStoredEventPreview" in html
    assert "Datenbank-Zeitraum:" in html
    assert 'class="structure-lines"' in html
    assert "selected-preview" in html


def test_workspace_uses_markerless_card_expansion():
    html = source("app/workspace_ui.py")
    assert 'class="collapse-card card"' in html
    assert 'id="no-event-range-details"' not in html
    assert 'existing-segment-static' in html
    assert 'class="card collapse-card"' in html
    assert ".collapse-card > summary::before" in html


def test_events_tab_opens_read_only_before_editing():
    html = source("app/events_ui.py")
    assert 'class="event-card-actions" hidden' in html
    assert "data-view-event=" in html
    assert "function renderEventViewer" in html
    assert "function openEventViewer" in html
    assert 'id="event-edit-header-button"' in html
    assert 'id="inspect-edit-event"' not in html
    assert "Datenbank-Beginn" in html
    assert "Datenbank-Zeitraum" in html
    assert "komplex" in html
    assert 'id="inspect-more-segments"' in html
    assert 'id="inspect-family-days"' in html
    assert "Dateifamilien nach Aufnahmetag" in html
    assert "edit-mode .sort-plan-content" in html


def test_structure_api_exposes_persisted_facts():
    main = source("app/main.py")
    assert '"assigned_family_count": len(assigned_families)' in main
    assert '"start_datetime": str(event.get("start_datetime") or "")' in main
    assert '"end_datetime": str(event.get("end_datetime") or "")' in main
    assert '"time_segments": [' in main
    assert '"event": event_facts' in main
