from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML


def test_workspace_free_card_and_preview_put_capture_times_on_right():
    assert 'name.appendChild(marker);' in WORKSPACE_HTML
    assert 'main.appendChild(marker);' not in WORKSPACE_HTML
    assert "details.innerHTML='<summary>Aufnahmezeiten</summary>'" not in WORKSPACE_HTML
    assert 'family.original_stem || family.family_key' in WORKSPACE_HTML
    assert 'capture.slice(0,10)} ${capture.slice(11,19)' in WORKSPACE_HTML
    assert '#calculate-preview-button { background:#374151' in WORKSPACE_HTML


def test_event_card_navigates_directly_and_editor_closes_on_save():
    assert 'href="/workspace?job=${encodeURIComponent(event._job_id||event.job_id||"")}&task=free"' in EVENTS_HTML
    assert 'data-reassign-workspace=' not in EVENTS_HTML
    assert 'a.plan-button { display:inline-flex;' in EVENTS_HTML
    assert 'list-style:none !important' in EVENTS_HTML
    assert '.event-details[open] > summary::before' in EVENTS_HTML
    assert 'eventEditDialog.close();\n\n      if (result.archive_manual?' in EVENTS_HTML
