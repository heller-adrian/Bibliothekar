"""0.55.4 regression: secure first-install configuration and desktop branding."""
from __future__ import annotations

from tests.backend.release_contract import EXPECTED_RELEASE_VERSION

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
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == EXPECTED_RELEASE_VERSION


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


def test_0554_startup_calls_bootstrap_before_database(tmp_path,monkeypatch):
    # Technical bootstrap was separated from domain recovery. Verify its real
    # effects/order rather than requiring both calls in one function's source.
    from app import config_bootstrap
    config=tmp_path/'config'/'settings.json';config.parent.mkdir()
    db=tmp_path/'catalogue.sqlite3';registry=tmp_path/'registry.sqlite3'
    calls=[];actual_config=config_bootstrap.ensure_settings_file
    actual_database=main.initialize_database;actual_registry=main.initialize_library_registry
    def settings(path):
        calls.append('config');return actual_config(path)
    def catalogue(path):
        assert config.is_file() and isinstance(json.loads(config.read_text()),dict)
        calls.append('catalogue');return actual_database(path)
    def libraries(path):
        assert config.is_file() and db.is_file()
        calls.append('registry');return actual_registry(path)
    for key,value in {'CONFIG_PATH':config,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':registry,
        'DATABASE_INITIALIZATION':None,'LIBRARY_REGISTRY_INITIALIZATION':None,'DATABASE_INITIALIZATION_ERROR':None}.items():monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(config_bootstrap,'ensure_settings_file',settings)
    monkeypatch.setattr(main,'initialize_database',catalogue)
    monkeypatch.setattr(main,'initialize_library_registry',libraries)
    main._prepare_technical_storage()
    assert calls==['config','catalogue','registry'] and json.loads(config.read_text())=={}
    config.write_text('{"ui":{"language":"de"}}\n');before=config.read_bytes();calls.clear()
    main._prepare_technical_storage()
    assert calls==['config','catalogue','registry'] and config.read_bytes()==before
    assert main.DATABASE_INITIALIZATION['newly_applied_versions']==[]
    assert main.LIBRARY_REGISTRY_INITIALIZATION['newly_applied_versions']==[]


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
