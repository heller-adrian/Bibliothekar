from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML


def test_0261_reassignment_action_and_event_opening_spacing():
    assert '.reassignment-dialog-action { display:flex; margin-top:14px; }' in EVENTS_HTML
    assert 'class="reassignment-dialog-action"' in EVENTS_HTML
    # 0.26.4 ersetzt die alte Dreieck-Disclosure durch die einheitliche Karten-UI.
    assert '.collapse-card > summary::before' in EVENTS_HTML
    assert 'content:none !important' in EVENTS_HTML
    assert 'class="event-card-actions" hidden' in EVENTS_HTML
    assert 'data-view-event=' in EVENTS_HTML


def test_0261_child_event_editor_uses_named_accordion_and_spacing():
    assert 'class="card child-segment-card"' in EVENTS_HTML
    assert 'data-child-summary' in EVENTS_HTML
    assert 'summary.textContent=String(nameInput.value||"").trim() || "Unterereignis"' in EVENTS_HTML
    assert 'class="child-segment-fields"' in EVENTS_HTML
    assert 'class="danger-button child-segment-remove"' in EVENTS_HTML


def test_0261_structure_preview_is_collapsible_and_single_line():
    assert '<details class="preview-day">' in WORKSPACE_HTML
    assert 'class="preview-family-row"' in WORKSPACE_HTML
    assert 'class="preview-family-stem"' in WORKSPACE_HTML
    assert 'class="preview-family-time"' in WORKSPACE_HTML
    assert 'white-space:nowrap' in WORKSPACE_HTML
    assert 'structurePreview.innerHTML' in WORKSPACE_HTML
