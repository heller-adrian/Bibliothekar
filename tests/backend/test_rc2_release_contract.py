"""RC2 packaging checks; all writes remain in the synthetic test directory."""
from pathlib import Path
import json

from app import __version__, main, source_helper
from app.security import _login_html
from app.main import _library_onboarding_html
from qa.release.check_web_assets import check_pages
from tests.backend.release_contract import EXPECTED_RELEASE_VERSION


def test_rc2_versions_are_consistent():
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == EXPECTED_RELEASE_VERSION
    assert source_helper.app.version == source_helper.healthz()['version'] == EXPECTED_RELEASE_VERSION
    assert main.api_health()['version'] == EXPECTED_RELEASE_VERSION


def test_rc2_delivered_web_assets_syntax(tmp_path):
    pages = {'import': main.index(), 'workspace': main.workspace_interface().body.decode(),
             'events': main.events_interface().body.decode(), 'archive': main.transfer_interface().body.decode(),
             'login': _login_html(), 'setup': _library_onboarding_html()}
    from app.metadata_correction_ui import METADATA_CORRECTION_HTML
    from app.trash_ui import TRASH_HTML
    from app.legacy_adoption_ui import wizard_html
    from app.ui_shell import apply_shell
    pages.update(metadata=apply_shell(METADATA_CORRECTION_HTML,active_area='metadata'),
                 trash=apply_shell(TRASH_HTML,active_area='trash'),
                 legacy_adoption=wizard_html('main'))
    result = check_pages(pages, tmp_path/'assets')
    assert result['pages'] == 9 and result['scripts'] > 0 and result['styles'] > 0
