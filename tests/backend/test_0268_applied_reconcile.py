from pathlib import Path

from app.obsolete_structure import cleanup_obsolete_structure
from app.workspace_reconcile import _workspace_structure_text
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.ui_shell import BIBLIOTHEKAR_CSS, _shell_markup


def test_0268_cleanup_keeps_empty_standard_branches_for_active_target(tmp_path: Path):
    root = tmp_path / "Arbeitsbereich"
    event = root / "2026" / "07-19 - Applied Kernlauf bearbeitet"
    alle = event / "Alle"
    sortiert = event / "Sortiert"
    export = event / "Export"
    for directory in (alle, sortiert, export):
        directory.mkdir(parents=True, exist_ok=True)
    file_path = alle / "IMG_0001.JPG"
    file_path.write_bytes(b"x")

    removed = cleanup_obsolete_structure(
        root,
        [file_path],
        [file_path],
        {"EVENT_ACTIVE"},
    )

    assert alle.is_dir()
    assert sortiert.is_dir()
    assert export.is_dir()
    assert str(sortiert) not in removed
    assert str(export) not in removed


def test_0268_cleanup_still_removes_empty_obsolete_standard_branches(tmp_path: Path):
    root = tmp_path / "Arbeitsbereich"
    old = root / "2026" / "07-19 - Alt"
    for branch in ("Alle", "Sortiert", "Export"):
        (old / branch).mkdir(parents=True, exist_ok=True)

    new = root / "2026" / "07-19 - Neu" / "Alle"
    new.mkdir(parents=True, exist_ok=True)
    destination = new / "IMG_0001.JPG"

    cleanup_obsolete_structure(
        root,
        [old / "Alle" / "IMG_0001.JPG"],
        [destination],
        {"EVENT_ACTIVE"},
    )

    assert not (old / "Sortiert").exists()
    assert not (old / "Export").exists()


def test_0268_reconcile_tree_is_real_folder_tree():
    tree = _workspace_structure_text([
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Alle"},
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Sortiert"},
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Export"},
        {"relative_path": "2026/07-20 - Applied Rest/Alle"},
        {"relative_path": "2026/07-20 - Applied Rest/Sortiert"},
        {"relative_path": "2026/07-20 - Applied Rest/Export"},
    ])

    assert tree.startswith("2026\n")
    assert "07-19 - Applied Kernlauf bearbeitet" in tree
    assert "07-20 - Applied Rest" in tree
    assert "Gemeinsamer Arbeitsbereich-Abgleich" not in tree
    assert tree.index("Alle") < tree.index("Sortiert") < tree.index("Export")


def test_0268_applied_state_copy_and_refresh_contract():
    assert "⚠ Neu-Zuordnung offen" in EVENTS_HTML
    assert "⚠ Nachsortierung offen" in EVENTS_HTML
    assert "⚠ Änderung noch nicht angewendet" not in EVENTS_HTML
    assert "Das Ereignis bleibt angewendet" in EVENTS_HTML
    assert "await loadEvents({reset:true});" in EVENTS_HTML
    assert 'applyButton.textContent = "Schließen"' in EVENTS_HTML
    assert 'applyButton.dataset.completed = "true"' in EVENTS_HTML


def test_0268_reconcile_target_is_not_independent_apply_ui():
    assert "Ziel einer offenen gemeinsamen Nachsortierung" in WORKSPACE_HTML
    assert 'applySavedEventButton.dataset.action = "reconcile"' in WORKSPACE_HTML
    assert "Nachsortierung unter Ereignisse öffnen" in WORKSPACE_HTML
    assert "Boolean(Number(event.reconcile_target||0))" in WORKSPACE_HTML
    assert "if (dated.some(group => Boolean(group.reassignment_pending))) return [];" in WORKSPACE_HTML
    assert "Bestehendes Ereignis erweitern" in WORKSPACE_HTML


def test_0268_sort_plan_modal_is_compact_and_disclosed():
    assert "inline-size: min(1240px" in EVENTS_HTML
    assert "grid-template-columns: repeat(7, minmax(0, 1fr))" in EVENTS_HTML
    assert EVENTS_HTML.count('class="sort-plan-section sort-plan-disclosure"') >= 3
    assert '<summary>Sicherheitsstatus</summary>' in EVENTS_HTML
    assert '<summary>Arbeitsbestand</summary>' in EVENTS_HTML
    assert '<summary>Zielstruktur</summary>' in EVENTS_HTML


def test_0268_events_subnav_is_opaque():
    markup = _shell_markup("workspace", "events")
    assert "bk-workspace-subnav-events" in markup
    assert ".bk-workspace-subnav-events" in BIBLIOTHEKAR_CSS
    assert "var(--bk-page-bg) 98%" in BIBLIOTHEKAR_CSS
