"""0.47.3 UI-Abnahme: sichtbare Vorgänge, keine veralteten Ereigniswarnungen."""

from app import main
from app.events_ui import EVENTS_HTML
from app.ui_shell import _shell_markup


def test_0442_version_and_shared_shell_stay_consistent():
    assert main.DEPLOYMENT_VERSION == "0.53.2"
    assert "0.53.2" in _shell_markup("workspace", "events")
    assert 'id="sort-plan-dialog"' in EVENTS_HTML
    assert 'id="change-request-dialog"' in EVENTS_HTML


def test_0442_spinner_is_real_and_accessible():
    assert ".event-operation-spinner" in EVENTS_HTML
    assert "@keyframes event-operation-spin" in EVENTS_HTML
    assert 'class="event-operation-loading" role="status"' in EVENTS_HTML
    assert 'aria-hidden="true"' in EVENTS_HTML
    assert 'function showSortPreparation(eventName, operation=' in EVENTS_HTML
    assert 'sortPlanCloseButton.disabled = true;' in EVENTS_HTML


def test_0442_applied_edit_opens_modal_before_async_mutation():
    src = EVENTS_HTML
    start = src.index('async function saveEventEditor()')
    end = src.index('async function openReassignmentWorkflow(', start)
    body = src[start:end]
    assert 'eventEditDialog.close();\n        showSortPreparation(context.event.name, "Änderungen anwenden");' in body
    assert body.index('showSortPreparation(context.event.name') < body.index(
        'result = await updateEventWithEmptySubeventConfirmation(context, payload)'
    )
    assert 'if (!eventEditDialog.open) eventEditDialog.showModal();' in body
    assert 'releaseSortPreparation();' in body


def test_0442_applied_delete_opens_modal_before_async_delete():
    src = EVENTS_HTML
    start = src.index('async function deleteEvent(eventId, jobId)')
    end = src.index('eventEditClose.addEventListener', start)
    body = src[start:end]
    assert 'const confirmed = await window.BibliothekarI18n.confirmAsync(' in body
    assert 'if (preparingApplied) showSortPreparation(event.name, "Änderungen anwenden");' in body
    assert body.index('showSortPreparation(event.name') < body.index('result = await requestJson(')
    assert 'if (preparingArchived)' in body
    assert 'changeRequestDialog.showModal()' in body
    assert 'statusElement.classList.remove("bk-loading-status")' in body


def test_0442_discard_shows_page_spinner_and_is_retryable():
    start = EVENTS_HTML.index('async function discardMandatoryMutation()')
    end = EVENTS_HTML.index('sortPlanCloseButton.addEventListener(', start)
    body = EVENTS_HTML[start:end]
    assert body.index('sortPlanDialog.close()') < body.index(
        'setEventOperationBusy("Änderung wird verworfen …")'
    )
    assert body.index('setEventOperationBusy("Änderung wird verworfen …")') < body.index(
        'await requestJson('
    )
    assert 'if (!sortPlanDialog.open) sortPlanDialog.showModal();' in body
    assert 'statusElement.classList.remove("bk-loading-status")' in body
    assert 'sortPlanCloseButton.disabled=false;' in body
    assert 'setEventOperationBusy("Änderung wird verworfen …")' in EVENTS_HTML


def test_0442_no_stale_yellow_reassignment_card_but_recovery_remains():
    src = EVENTS_HTML
    start = src.index('function renderEvents(events)')
    end = src.index('async function loadEvents(', start)
    body = src[start:end]
    assert 'Neu-Zuordnung offen' not in body
    assert 'Nachsortierung offen' not in body
    assert '${reassign}' not in body
    assert '${mutation}' not in body
    assert 'data-reassign-event=' in body
    assert 'data-cancel-mutation=' in body
    assert 'data-sort-plan-event=' in body
    assert 'Neu-Zuordnung fortsetzen' in body
    assert 'Änderung fortsetzen' in body
