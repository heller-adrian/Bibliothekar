"""0.45.0: einheitliche Typografie und ausgeblendete KI-Navigation."""
from pathlib import Path
import re

from app import __version__
from app import main
from app.ui_shell import BIBLIOTHEKAR_0450_CSS, apply_shell

FONT_STACK = 'Futura, "Helvetica Neue", Helvetica, Arial, sans-serif'


def _render(area, subarea=None):
    return apply_shell(
        '<!doctype html><html><head><title>Test</title></head><body><main>Test</main></body></html>',
        active_area=area,
        subarea=subarea,
    )


def test_0450_version_and_existing_core_remain_separate():
    assert __version__ == "0.55.2"
    assert main.DEPLOYMENT_VERSION == "0.55.2"
    assert main.RELEASE_VERSION == "0.55.2"


def test_0450_no_assistant_link_in_desktop_or_mobile_navigation():
    for area, subarea in (
        ("import", None),
        ("workspace", "captures"),
        ("workspace", "events"),
        ("archive", None),
        ("metadata", "general"),
        ("trash", None),
    ):
        rendered = _render(area, subarea)
        assert 'href="/assistant"' not in rendered
        header = rendered.split('<header class="bk-shell">', 1)[1].split('</header>', 1)[0]
        assert 'bk-assistant-button' not in header
        assert '<span>Assistent</span>' not in rendered
        assert 'href="/metadata-correction"' in rendered
        assert 'href="/trash"' in rendered
        assert 'data-bk-open-settings' in rendered


def test_0450_font_is_applied_to_controls_and_code():
    html = _render("workspace", "captures")
    assert FONT_STACK in BIBLIOTHEKAR_0450_CSS
    assert f'<style>{BIBLIOTHEKAR_0450_CSS}</style>' in html
    for selector in ("body.bibliothekar-redesign button",
                     "body.bibliothekar-redesign input",
                     "body.bibliothekar-redesign select",
                     "body.bibliothekar-redesign textarea",
                     "body.bibliothekar-redesign code",
                     "body.bibliothekar-redesign pre"):
        assert selector in BIBLIOTHEKAR_0450_CSS


def test_0450_no_unintentional_legacy_font_family():
    for name in ("ui_shell.py", "main.py", "events_ui.py",
                 "workspace_ui.py", "metadata_correction_ui.py",
                 "transfer_ui.py", "trash_ui.py"):
        source = (Path(__file__).resolve().parents[2] / "app" / name).read_text(encoding="utf-8")
        if name == "ui_shell.py":
            source = source[source.index("BIBLIOTHEKAR_0450_CSS = "):]
        for rule in re.findall(r"font-family\\s*:\\s*([^;\\n]+)", source, flags=re.I):
            assert FONT_STACK in rule or rule.strip() in {"inherit", "var(--bk-font-ui)"}, (name, rule)


def test_0450_navigation_prevents_overflow_on_narrow_viewports():
    assert 'text-overflow: ellipsis;' in BIBLIOTHEKAR_0450_CSS
    assert '.bk-brand-title {' in BIBLIOTHEKAR_0450_CSS
    assert '.bk-tab-mobile-label,' in BIBLIOTHEKAR_0450_CSS
    assert '.bk-pwa-label {' in BIBLIOTHEKAR_0450_CSS
    assert '@media (max-width: 400px)' in BIBLIOTHEKAR_0450_CSS
