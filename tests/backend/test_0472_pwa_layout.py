"""0.47.3: Korrigierte iPhone-Safe-Area und einheitlicher rahmenloser PWA-Dock."""
from app import __version__, main
from app.ui_shell import BIBLIOTHEKAR_0472_CSS, apply_shell


def test_0472_runtime_and_logo_v2_intact():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.53.1"
    for area in ("import", "workspace", "archive", "metadata", "trash"):
        html = apply_shell("<html><head></head><body></body></html>", active_area=area)
        assert f"<style>{BIBLIOTHEKAR_0472_CSS}</style>" in html
        assert html.count('/assets/bibliothekar-logo-v2.svg?v=0.47.3') == 2
        assert html.count('id="bk-current-library-name"') == 1
    assert main.bibliothekar_brand_logo().path.name == "bibliothekar-logo-v2.svg"


def test_0472_headings_and_subnav_move_up_in_document_flow():
    css = BIBLIOTHEKAR_0472_CSS
    assert 'html[data-bk-display-mode="standalone"]' in css
    assert "@media (max-width:820px)" in css
    assert '> .bk-page-heading' in css
    assert '> .bk-workspace-subnav' in css
    assert '> .bk-metadata-subnav' in css
    assert 'margin-top:-26px !important;' in css
    assert 'padding-top:max(38px, calc(env(safe-area-inset-top) - 6px)) !important;' in css
    assert "transform:translateY" not in css
    assert "padding-top:0 !important;" in css


def test_0472_dock_has_fixed_identical_height_and_bottom_on_all_pages():
    css = BIBLIOTHEKAR_0472_CSS
    assert "height:calc(112px + env(safe-area-inset-bottom)) !important;" in css
    assert "max-height:calc(112px + env(safe-area-inset-bottom)) !important;" in css
    assert "bottom:0 !important;" in css
    assert "height:100% !important;" in css
    assert "grid-template-rows:47px 22px !important;" in css
    assert "width:36px !important;" in css
    assert "width:42px !important;" in css
    assert ".bk-pwa-nav-item.active .bk-pwa-icon svg" in css
    assert 'body.bibliothekar-redesign main' in css


def test_0472_task_and_menu_become_borderless_aligned_items():
    css = BIBLIOTHEKAR_0472_CSS
    task = css.split('html[data-bk-display-mode="standalone"] .bk-pwa-task-toggle {', 1)[1].split("}", 1)[0]
    menu = css.split('html[data-bk-display-mode="standalone"] .bk-pwa-menu-toggle {', 1)[1].split("}", 1)[0]
    assert "border:0 !important;" in task
    assert "background:transparent !important;" in task
    assert 'grid-template-areas:"icon" "label" !important;' in task
    assert "border:0 !important;" in menu
    assert "background:transparent !important;" in menu
    assert "height:100% !important;" in menu
    assert ".bk-pwa-task-toggle .bk-pwa-task-count" in css
    assert "grid-area:icon;" in css
    assert "grid-area:label;" in css
    assert "width:39px !important;" in css
    assert "bottom:calc(112px + env(safe-area-inset-bottom)) !important;" in css
