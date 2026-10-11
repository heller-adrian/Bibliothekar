"""0.44.4: UI-Vertrag für die eigenständige Papierkorbseite.

Der Patch ändert bewusst weder das physische Inventar noch die Lösch-API.
"""

from app.trash_ui import TRASH_HTML
from app.ui_shell import _shell_markup, apply_shell


def test_0441_trash_keeps_its_own_shell_area_and_neutral_navigation():
    page = apply_shell(TRASH_HTML, active_area="trash")

    assert '<body class="bibliothekar-redesign" data-bk-area="trash">' in page
    assert 'class="bk-tabs bk-tabs-active-trash"' in page
    assert 'data-area="import"' in page
    assert 'data-area="workspace"' in page
    assert 'data-area="archive"' in page
    assert 'class="bk-tab active"' not in page
    assert 'class="bk-pwa-nav-item active"' not in page
    assert '>Papierkorb</h1>' in page
    assert '>Import &amp; Prüfung</h1>' not in page
    assert '<main class="trash-page">' in page
    assert '<section class="card">' not in TRASH_HTML


def test_0441_collapsible_full_inventory_without_pagination():
    assert '<details class="trash-content">' in TRASH_HTML
    assert '<details class="trash-folder">' in TRASH_HTML
    assert 'renderChildren(makeTree(entries))' in TRASH_HTML
    assert 'const depth=entry.entry_type==="directory"?parts.length:parts.length-1' in TRASH_HTML
    assert 'if(entry.entry_type!=="directory") parent.items.push(entry)' in TRASH_HTML
    assert 'folder.items.slice().sort(' in TRASH_HTML
    assert 'title="' in TRASH_HTML
    assert 'Mehr anzeigen' not in TRASH_HTML
    assert 'slice(0,15)' not in TRASH_HTML
    assert 'data.entries||[]' in TRASH_HTML


def test_0441_statistics_and_destructive_confirmation_are_preserved():
    for element_id in ("trash-files", "trash-directories", "trash-size"):
        assert 'id="' + element_id + '"' in TRASH_HTML
    assert 'id="trash-empty-button"' in TRASH_HTML
    assert 'class="danger-button trash-danger"' in TRASH_HTML
    assert 'window.BibliothekarI18n.confirmAsync("Papierkorb wirklich endgültig entleeren?' in TRASH_HTML
    assert 'confirmation:"PAPIERKORB ENDGÜLTIG LEEREN"' in TRASH_HTML
    assert '"/api/trash"' in TRASH_HTML
    assert '"/api/trash/empty"' in TRASH_HTML


def test_0441_responsive_spacing_and_unified_settings():
    from app.ui_shell import BIBLIOTHEKAR_0441_CSS

    assert 'body[data-bk-area="trash"] main.trash-page{padding-bottom:72px!important}' in TRASH_HTML
    assert '@media(min-width:701px)' in TRASH_HTML
    assert '@media(max-width:700px)' in TRASH_HTML
    assert 'body[data-bk-area="trash"] {' in BIBLIOTHEKAR_0441_CSS
    assert 'html[data-bk-theme="dark"] body[data-bk-area="trash"] {' in BIBLIOTHEKAR_0441_CSS
    assert 'body[data-bk-area="trash"] main {' in BIBLIOTHEKAR_0441_CSS
    assert 'bk-tabs-active-trash' in BIBLIOTHEKAR_0441_CSS
    assert 'id="bk-settings-dialog"' in _shell_markup("trash", None)
