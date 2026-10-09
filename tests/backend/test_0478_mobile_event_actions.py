"""0.47.8: mobile PWA and browser event actions stay within equal button slots."""
import re

from app.events_ui import EVENTS_HTML
from app.ui_shell import apply_shell


def test_0478_mobile_event_action_font_is_explicit_and_responsive():
    css = EVENTS_HTML.split("<style>", 1)[1].split("</style>", 1)[0]
    anchor = css.index("0.47.8: mobile Browserseite")
    next_rule = css.index("/* 0.40.2:", anchor)
    scoped = css[anchor:next_rule]
    assert "@media (max-width:820px)" in scoped
    assert "body.bibliothekar-redesign[data-bk-area=\"workspace\"]" in scoped
    assert ".event-card-actions > button" in scoped
    assert ".event-card-actions > a" in scoped
    assert re.search(r"font-size:\s*clamp\(\.625rem,2\.8vw,\.72rem\)\s*!important", scoped)
    assert "white-space:nowrap" in scoped
    assert "min-width:0 !important" in scoped
    # No display-mode selector: the same mobile rule covers browser and PWA.
    assert "data-bk-display-mode" not in scoped


def test_0478_three_planned_event_actions_keep_original_labels_and_layout():
    html = EVENTS_HTML
    assert '<div class="event-card-actions" hidden>' in html
    assert "Sortierung prüfen</button>" in html
    assert "Ereignis löschen</button>" in html
    assert ">Öffnen</button>" in html
    assert "flex-wrap:nowrap" in html
    assert ".event-card-actions[hidden]" in html


def test_0478_shell_includes_mobile_fix_without_changing_desktop():
    output = apply_shell(EVENTS_HTML, active_area="workspace", subarea="events")
    assert "0.47.8: mobile Browserseite" in output
    assert "data-bk-area=\"workspace\"" in output
    assert "@media (max-width:820px)" in output
    assert 'data-bk-display-mode="standalone"' in output
