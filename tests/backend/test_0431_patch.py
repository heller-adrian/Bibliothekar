from app.event_naming import (
    naming_from_library_settings,
    render_subevent_folder_name,
)
from app.ui_shell import BIBLIOTHEKAR_JS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def test_0431_subevent_naming_options_are_combinable():
    common = {
        "event_name": "Stadtbesuch",
        "start_datetime": "2026-07-20T14:00:00",
        "end_datetime": "2026-07-21T18:30:59",
    }

    assert render_subevent_folder_name(
        **common,
        naming={
            "subevent_date_mode": "start",
            "subevent_include_year": False,
            "subevent_include_time": False,
            "subevent_prefix_enabled": True,
        },
    ) == "07-20 - Stadtbesuch"

    assert render_subevent_folder_name(
        **common,
        naming={
            "subevent_date_mode": "range",
            "subevent_include_year": True,
            "subevent_include_time": True,
            "subevent_prefix_enabled": True,
        },
    ) == "2026-07-20 14-00–2026-07-21 18-30 - Stadtbesuch"

    assert render_subevent_folder_name(
        **common,
        naming={
            "subevent_date_mode": "start",
            "subevent_include_year": True,
            "subevent_include_time": True,
            "subevent_prefix_enabled": True,
        },
    ) == "2026-07-20 · 14-00–18-30 - Stadtbesuch"

    assert render_subevent_folder_name(
        **common,
        naming={
            "subevent_date_mode": "range",
            "subevent_include_year": False,
            "subevent_include_time": True,
            "subevent_prefix_enabled": False,
        },
    ) == "Stadtbesuch"


def test_0431_legacy_0430_subevent_mode_stays_exact():
    assert render_subevent_folder_name(
        event_name="Stadtbesuch",
        start_datetime="2026-07-20T14:00:00",
        end_datetime="2026-07-21T18:30:59",
        naming={
            "subevent_prefix_mode": "time",
            "subevent_prefix_enabled": True,
        },
    ) == "14-00–18-30 - Stadtbesuch"

    migrated = naming_from_library_settings({
        "event_naming": {
            "subevent_prefix_mode": "date_range",
            "subevent_prefix_enabled": True,
        }
    })
    assert "subevent_prefix_mode" not in migrated
    assert migrated["subevent_date_mode"] == "range"
    assert migrated["subevent_include_year"] is False
    assert migrated["subevent_include_time"] is False


def test_0431_settings_match_normal_event_checkbox_model():
    shell = _shell_markup("workspace", "captures")

    assert 'id="bk-subevent-prefix-mode"' not in shell
    assert "Kein Präfix" not in shell
    assert 'id="bk-subevent-include-year"' in shell
    assert 'id="bk-subevent-include-time"' in shell
    assert 'id="bk-subevent-date-range"' in shell
    assert 'id="bk-subevent-prefix-enabled"' in shell
    assert "Jahr einbeziehen" in shell
    assert "Uhrzeit einbeziehen" in shell
    assert "Von–bis im Namen" in shell
    assert "Standardmäßig verwenden" in shell

    assert "subevent_date_mode:Boolean" in BIBLIOTHEKAR_JS
    assert "subevent_include_year:Boolean" in BIBLIOTHEKAR_JS
    assert "subevent_include_time:Boolean" in BIBLIOTHEKAR_JS


def test_0431_preview_nests_subevent_in_normal_event_card():
    assert "bkPreviewStructure(normal,subevent)" in BIBLIOTHEKAR_JS
    assert '<strong>Unterereignis</strong>' not in BIBLIOTHEKAR_JS
    assert BIBLIOTHEKAR_JS.count(
        '<div class="bk-settings-preview-case"><strong>'
    ) >= 2


def test_0431_native_date_controls_restore_localized_browser_entry():
    assert 'id="event-start-date" type="date"' in WORKSPACE_HTML
    assert 'id="event-end-date" type="date"' in WORKSPACE_HTML
    assert 'data-create-child-start-date type="date"' in WORKSPACE_HTML
    assert 'data-create-child-end-date type="date"' in WORKSPACE_HTML
    assert "📅" not in WORKSPACE_HTML

    assert 'id="edit-start-date" type="date"' in EVENTS_HTML
    assert 'id="edit-end-date" type="date"' in EVENTS_HTML
    assert 'data-child-start-date type="date"' in EVENTS_HTML
    assert 'data-child-end-date type="date"' in EVENTS_HTML
    assert "📅" not in EVENTS_HTML


def test_0431_compact_prefix_toggle_is_preserved():
    assert 'id="subevent-prefix-toggle"' in WORKSPACE_HTML
    assert ">Präfix: an<" in WORKSPACE_HTML
    assert 'subeventPrefixToggle.textContent=dialogSubeventPrefixEnabled ? "Präfix: an" : "Präfix: aus"' in WORKSPACE_HTML
