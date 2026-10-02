"""0.27.3: Archiv-UI und Rückänderungsauftrag."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_0273_reversal_is_separate_right_to_left_three_step_workflow():
    source = (ROOT / "app" / "events_ui.py").read_text()
    assert 'changeRequestTitle.textContent = "Rückänderungsauftrag"' in source
    verify = source.index('{phase:"verify", number:3')
    finder = source.index('{phase:"finder", number:2')
    prepare = source.index('{phase:"prepare", number:1')
    assert verify < finder < prepare
    assert "Dieser Wiederherstellungsbereich wird erst mit „Rückänderung vorbereiten“ angelegt:" in source
    assert "/reversal/prepare" in source
    assert "/reversal/verify" in source
    assert "/reversal/finish" in source
    assert "wird anschließend ein eigener Rückänderungsauftrag geöffnet" in source


def test_0273_finder_disclosures_are_left_aligned_and_share_triangle():
    source = (ROOT / "app" / "events_ui.py").read_text()
    assert "#change-request-dialog details > summary" in source
    assert "#change-request-dialog details > summary::before" in source
    assert 'content:"▸"' in source
    assert 'content:"▾"' in source
    assert "text-align:left !important" in source
    assert 'class="card change-disclosure"' in source
    assert '<summary style="display:flex;align-items:center;justify-content:space-between' not in source


def test_0273_help_uses_bk_help_and_sort_button_is_only_plannable():
    events = (ROOT / "app" / "events_ui.py").read_text()
    workspace = (ROOT / "app" / "workspace_ui.py").read_text()
    assert 'class="bk-help"' in events
    assert 'data-help="Freigewordene Archivdateien werden zuerst sicher auf die SSD' in events
    assert 'isSortPlannable(event)' in events
    assert 'event.status === "applied" ? "Nachsortierung prüfen" : "Sortierung prüfen"' not in events
    assert 'class="bk-help"' in workspace
    assert 'cursor:help' not in workspace
