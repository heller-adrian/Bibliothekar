"""0.47.3: Phasenplatzierung, ausschließlich heller Hover und randfreie PWA-Schnellauswahl."""
from pathlib import Path

from app import __version__, main
from app.ui_shell import BIBLIOTHEKAR_0455_CSS, BIBLIOTHEKAR_0456_CSS, apply_shell

ROOT = Path(__file__).resolve().parents[2]


def test_0456_versions_and_shell_load_new_css_last():
    assert __version__ == "0.52.0"
    assert main.DEPLOYMENT_VERSION == "0.52.0"
    html = apply_shell("<html><head></head><body></body></html>", active_area="workspace")
    assert "Version <span data-bk-version>0.52.0</span>" in html
    assert html.index(f"<style>{BIBLIOTHEKAR_0455_CSS}</style>") < html.index(
        f"<style>{BIBLIOTHEKAR_0456_CSS}</style>"
    )


def test_0456_phase_badge_is_only_in_expanded_details():
    html = main.index()
    detail = html.split('const detailMarkup = `', 1)[1].split(
        'const isDone =', 1
    )[0]
    assert 'class="bk-history-detail-date"' in detail
    assert 'bk-stage-badge bk-stage-badge-header' in detail
    assert 'activeStates.has(job.state)' in detail
    assert '<span>Aktuelle Phase</span>' in detail
    assert 'Aktuelle Phase <span class="bk-stage-badge">' not in detail
    strip = html.split('class="bk-history-strip"', 1)[1].split(
        'class="bk-history-details"', 1
    )[0]
    assert "bk-stage-badge-header" not in strip
    assert "bk-history-detail-date" in BIBLIOTHEKAR_0456_CSS
    assert "justify-content:space-between;" in BIBLIOTHEKAR_0456_CSS


def test_0456_light_hover_midpoint_does_not_override_dark_theme():
    css = BIBLIOTHEKAR_0456_CSS
    assert 'html[data-bk-theme="light"]' in css
    assert 'html[data-bk-theme="dark"]' not in css
    assert 'var(--surface) 97%,var(--bk-ink) 3%' in css
    assert 'var(--surface-2) 97%,var(--bk-ink) 3%' in css
    assert '.day-card.without-date.review-card:hover' in css
    assert 'border-color:color-mix(in srgb,var(--border) 91%,var(--bk-ink) 9%)' in css
    assert '.24s ease-in-out' in BIBLIOTHEKAR_0455_CSS or '.24s ease-in-out' in (
        Path(ROOT / "app/ui_shell.py").read_text()
    )


def test_0480_mobile_selection_keeps_bordered_children_stationary():
    from app.ui_shell import BIBLIOTHEKAR_0423_CSS, BIBLIOTHEKAR_0424_CSS
    assert "bk-pwa-select-inner-wobble" not in BIBLIOTHEKAR_0456_CSS
    assert "box-shadow: inset" in BIBLIOTHEKAR_0423_CSS
    assert "translateX(" not in BIBLIOTHEKAR_0424_CSS
    assert "will-change: transform" not in BIBLIOTHEKAR_0424_CSS
    script = (ROOT / "app/ui_shell.py").read_text()
    assert 'bkPwaSelectPulse(live)' in script
    assert 'bkPwaApplyRange(gesture, key)' in script
    assert 'window.setTimeout(() => card.classList.remove("bk-pwa-select-wobble"), 320)' in script
