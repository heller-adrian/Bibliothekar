from __future__ import annotations

from app import main


def test_0357_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.41.1"


def test_0357_onboarding_script_keeps_newline_escape_for_browser():
    html = main._library_onboarding_html()

    valid = 'if(!check.valid)throw new Error((check.errors||[]).join("\\n"));'
    broken = 'if(!check.valid)throw new Error((check.errors||[]).join("\n"));'

    assert valid in html
    assert broken not in html
    assert 'button.addEventListener("click",async()=>{' in html
