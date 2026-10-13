"""0.55.1 first-run language, PWA dock and English clean-install regression."""
from pathlib import Path, PurePosixPath

from app import __version__
from app.archive_staging import BRANCHES, LEGACY_BRANCHES, KNOWN_BRANCHES, _fallback_branches
from app.main import _library_onboarding_html
from app.security import _login_html
from app.ui_shell import apply_shell, BIBLIOTHEKAR_JS
from app.workspace_layout import ensure_workspace_layout


def test_0551_bilingual_first_run():
    assert __version__ == "0.55.2"
    for html in (_login_html(), _login_html(unavailable=True), _library_onboarding_html()):
        assert 'data-bk-setup-choice="en"' in html
        assert 'data-bk-setup-choice="de"' in html
        assert 'localStorage.setItem(key,l)' in html
        assert "bibliothekar-language" in html
        assert "bk-language-changed" in html
        assert "data-bk-setup-title-de" in html
    assert "Set up your first library" in _library_onboarding_html()
    assert "Check and create library" in _library_onboarding_html()
    assert "Administratorpasswort" in _login_html()
    assert "Es ist noch kein Administratorpasswort eingerichtet." in _login_html(unavailable=True)


def test_0551_bottom_dock_is_interactive_before_navigation():
    html = apply_shell("<html><head></head><body><main>x</main></body></html>", active_area="workspace")
    assert 'link.addEventListener("pointerdown"' in BIBLIOTHEKAR_JS
    assert 'link.addEventListener("touchstart"' in BIBLIOTHEKAR_JS
    assert 'bkDockActivate(link);' in BIBLIOTHEKAR_JS
    assert 'root.dataset.bkNavLoading="true"' in BIBLIOTHEKAR_JS
    assert 'requestAnimationFrame(()=>window.location.assign(href));' in BIBLIOTHEKAR_JS
    assert 'inset:0 0 calc(112px + env(safe-area-inset-bottom)) 0!important;' in html


def test_0551_empty_install_does_not_create_legacy_alias(tmp_path: Path, monkeypatch):
    root=tmp_path/"workspace"
    root.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(root))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path/"config"/"settings.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    result=ensure_workspace_layout(root)
    assert not (root/"Arbeitsbereich").exists()
    assert not (root/"Arbeitsbereich").is_symlink()
    for name in ("SD Card Backups","Library Workspaces","Metadata Correction","Trash"):
        assert (root/name).is_dir()
    assert (root/"Metadata Correction"/"General").is_dir()
    assert (root/"Metadata Correction"/"Batch Correction").is_dir()
    assert result["work_root"]==str(root/"Library Workspaces")


def test_0551_archive_branch_fallback_keeps_legacy_compatibility():
    assert BRANCHES==("All","Sorted","Export")
    assert LEGACY_BRANCHES==("Alle","Sortiert","Export")
    assert {"All","Sorted","Alle","Sortiert","Export"}<=KNOWN_BRANCHES
    assert _fallback_branches(PurePosixPath("2026/Trip/All/photo.jpg"))==BRANCHES
    assert _fallback_branches(PurePosixPath("2026/Trip/Alle/photo.jpg"))==LEGACY_BRANCHES
