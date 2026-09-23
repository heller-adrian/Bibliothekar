from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0231_version():
    assert main.APP_VERSION == "0.26.3"


def test_0231_workspace_main_actions_are_blue_and_card_is_aligned():
    html = main.workspace_interface().body.decode("utf-8")

    assert 'id="apply-saved-event-button" class="primary bk-positive-action"' in html
    assert 'id="save-event-button"' in html
    assert 'class="primary bk-positive-action"' in html
    assert 'id="post-save-action" class="card" hidden style="margin:0 0 18px;' in html

    assert 'body[data-bk-area="workspace"] .bk-positive-action {' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-blue) !important;' in BIBLIOTHEKAR_CSS


def test_0231_planned_selection_checkbox_is_visibly_toggleable_in_light_theme():
    html = main.workspace_interface().body.decode("utf-8")

    assert 'class="planned-check" type="checkbox"' in html
    assert 'html[data-bk-theme="light"] body.bibliothekar-redesign .planned-check:checked {' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-blue) !important;' in BIBLIOTHEKAR_CSS
    assert 'planned-check:checked::after' in BIBLIOTHEKAR_CSS


def test_0231_workspace_status_is_localized():
    html = main.workspace_interface().body.decode("utf-8")

    assert 'planned: "Geplant"' in html
    assert 'workspaceStatusLabel(event.status)' in html
    assert 'workspaceStatusLabel(group.status)' in html


def test_0231_event_actions_use_blue_positive_action_class():
    html = main.events_interface().body.decode("utf-8")

    assert 'class="plan-button bk-positive-action" data-sort-plan-event=' in html
    assert '<button type="submit" class="plan-button bk-positive-action">Änderungen speichern</button>' in html


def test_0231_multiple_time_ranges_have_explicit_editor_mode():
    html=main.events_interface().body.decode('utf-8')
    assert 'Mehrere Zeitbereiche</option>' not in html
    assert 'id="edit-start-time"' in html and 'id="edit-end-time"' in html
    assert 'isoTime(event.start_datetime' in html
    assert 'isoTime(event.end_datetime' in html
