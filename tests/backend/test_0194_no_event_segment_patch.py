from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION


def test_0194_version():
    assert APP_VERSION >= "0.19.4"


def test_workspace_manual_day_segment_does_not_retrigger_target_auto_attach():
    marker = 'document.getElementById("add-no-event-segment")?.addEventListener("click"'
    block = WORKSPACE_HTML.split(marker, 1)[1].split('calculatePreviewButton.addEventListener', 1)[0]
    assert 'autoAttachExistingNoEventCollection().catch' not in block
    assert 'day_key:""' in block
    assert '＋ Tagessegment' in WORKSPACE_HTML
    assert '<strong>Tagessegmente</strong>' in WORKSPACE_HTML


def test_workspace_switch_to_new_collection_clears_imported_segments():
    assert 'renderNoEventSegmentEditor([]);' in WORKSPACE_HTML
    assert 'activeNoEventTarget=null;' in WORKSPACE_HTML
    assert 'Neue Monats-Sammlung / noch kein Ziel' in WORKSPACE_HTML


def test_events_editor_uses_day_segment_terms_and_compact_rows():
    assert '＋ Zeitspanne ergänzen' not in EVENTS_HTML
    assert 'Zeitspanne übernehmen' not in EVENTS_HTML
    assert '<span>Tagessegmente</span>' in EVENTS_HTML
    assert '＋ Tagessegment hinzufügen' in EVENTS_HTML
    assert 'grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px' in EVENTS_HTML
    assert 'display:block;padding:8px 10px;margin:6px 0' in EVENTS_HTML
