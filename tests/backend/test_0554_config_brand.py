"""0.55.4 regression: secure first-install configuration and desktop branding."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import __version__
from app import main
from app.config_bootstrap import ensure_settings_file
from app.security import _login_html
from app.main import _library_onboarding_html
from app.setup_language import _CSS


def test_0554_version():
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == "0.56.1"


def test_0554_creates_missing_settings_safely(tmp_path: Path):
    config = tmp_path / "config" / "settings.json"
    secret = config.parent / "admin-password"
    config.parent.mkdir()
    secret.write_text("kept-securely")
    assert ensure_settings_file(config) is True
    assert json.loads(config.read_text("utf-8")) == {}
    assert secret.read_text() == "kept-securely"
    if os.name == "posix":
        assert config.stat().st_mode & 0o077 == 0


def test_0554_repeated_bootstrap_preserves_existing_options(tmp_path: Path):
    config=tmp_path/"config"/"settings.json"
    assert ensure_settings_file(config) is True
    config.write_text('{"storage":{"trash_directory_name":"My Trash"}}\n', encoding="utf-8")
    previous=config.read_bytes()
    assert ensure_settings_file(config) is False
    assert config.read_bytes() == previous


def test_0554_does_not_repair_invalid_or_symlink_settings(tmp_path: Path):
    config=tmp_path/"settings.json"
    config.write_text("{ invalid JSON", encoding="utf-8")
    assert ensure_settings_file(config) is False
    assert config.read_text() == "{ invalid JSON"
    config.unlink()
    other=tmp_path/"other"
    other.write_text('{"keep":true}')
    try:
        config.symlink_to(other)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    assert ensure_settings_file(config) is False
    assert other.read_text() == '{"keep":true}'


def test_0554_startup_calls_bootstrap_before_database():
    import inspect
    source = inspect.getsource(main.startup_database)
    assert source.index("ensure_settings_file(CONFIG_PATH)") < source.index("initialize_database(")


def test_0554_desktop_logo_no_form_displacement_and_mobile_unchanged():
    css=_CSS
    assert '@media(min-width:821px)' in css
    desktop=css.split('@media(min-width:821px)', 1)[1].split('.bk-setup-lang{', 1)[0]
    assert "position:fixed;" in desktop
    assert "left:50%;" in desktop
    assert "transform:translateX(-50%);" in desktop
    assert "width:min(830px,48vw);" in desktop
    assert "place-items:center;" in desktop
    assert "justify-self:center;" in desktop
    assert '@media(max-width:540px)' in css
    for page in (_login_html(), _library_onboarding_html()):
        assert 'class="bk-setup-brand"' in page
        assert 'class="bk-setup-page"' in page
        assert 'data-bk-setup-choice="en"' in page
        assert 'data-bk-setup-choice="de"' in page
