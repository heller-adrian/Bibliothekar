"""Regression protection for Bibliothekar 0.50.8.

Translation checks cover literal UI labels and dynamically interpolated content,
while file paths remain opaque user data. No real archive or workspace writes.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import __version__
from app import main
from app.background_activity import current_activity
from app.event_inventory import _branch_for
from app.transfer_ui import TRANSFER_HTML
from app.ui_shell import BIBLIOTHEKAR_0444_JS, BIBLIOTHEKAR_0444_CSS
from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS


def translate(source: str) -> str:
    core = source.strip()
    if core in UI_TRANSLATIONS:
        return UI_TRANSLATIONS[core]
    normalized = " ".join(core.split())
    if normalized in UI_TRANSLATIONS:
        return UI_TRANSLATIONS[normalized]
    for expression, target in UI_PATTERNS:
        match = re.search(expression, core)
        if match:
            replacement = re.sub(
                r"\$(\d+)",
                lambda m: match.group(int(m.group(1))) or "",
                target,
            )
            return match.expand(replacement) if "$" not in replacement else replacement
    return core


def test_0508_version_and_compatibility():
    assert __version__ in {"0.50.8", "0.54.0"}
    assert main.RELEASE_VERSION in {"0.50.8", "0.54.0"}
    assert main.DEPLOYMENT_VERSION in {"0.50.8", "0.54.0"}
    assert _branch_for("2026/Test/All/photo.JPG") == "All"
    assert _branch_for("2026/Test/Sorted/photo.JPG") == "Sorted"
    assert _branch_for("2026/Test/Alle/photo.JPG") == "Alle"
    assert _branch_for("2026/Test/Export/photo.JPG") == "Export"


def test_0508_external_drive_and_archive_labels():
    for german, english in {
        "Kein externes Laufwerk erkannt.": "No external drive detected.",
        "Komplettes Laufwerk sichern": "Back up entire drive",
        "Noch kein Laufwerk eingebunden": "No drive mounted yet",
        "Unterereignisse:": "Subevents:",
        "Unterordnerstruktur aktiv": "Subfolder structure enabled",
        "Freigabe abgeschlossen": "Release completed",
        "Der Ordner ist leer.": "The folder is empty.",
        "Prüfung/Korrektur erforderlich": "Review/correction required",
    }.items():
        assert translate(german) == english


def test_0508_dynamic_counts_and_preview():
    examples = {
        "32\n                Dateien": "32 Files",
        "16\n                Familien": "16 Families",
        "Unterereignisse: 1": "Subevents: 1",
        "Zeitsegmente: 3": "Time segments: 3",
        "angewendet · Ereignis": "applied · Event",
        "Ohne Tagesunterordner · Unterordnerstruktur aktiv":
            "Without day subfolders · Subfolder structure enabled",
        "Tagesordner bleiben erhalten · Direkt im Ereignis":
            "Day folders preserved · Directly in event folder",
    }
    for source, expected in examples.items():
        assert translate(source) == expected, (source, translate(source))


def test_0508_archive_error_preserves_exact_path():
    path = "/main-library/2026/07-24 - Test eng"
    source = "Ereignisordner wurde nicht gefunden: " + path
    assert translate(source) == "Event folder not found: " + path


def test_0508_release_confirmation_is_handled_before_api():
    release = TRANSFER_HTML
    assert "const question=" in release
    assert "const confirmation=window.BibliothekarI18n?.confirmAsync" in release
    assert "if (!confirmation) return" in release
    assert "if (!response.task_id)" in release
    assert 'window.dispatchEvent(new Event("bk-activity-refresh"))' in release
    assert "result.hidden=false;result.className='result danger'" in release


def test_0508_activity_and_capacity_choose_actual_root():
    import inspect
    health = inspect.getsource(main.get_health)
    assert "health_workspace = current_library_context().workspace_root" in health
    assert "health_workspace = current_workspace_root()" not in health
    assert "window.matchMedia(\"(min-width: 0px)\")" in BIBLIOTHEKAR_0444_JS
    assert "#bk-background-cancel-notice {display:none!important}" not in BIBLIOTHEKAR_0444_CSS
    assert 'window.addEventListener("bk-activity-refresh", refresh)' in BIBLIOTHEKAR_0444_JS
    activity = inspect.getsource(current_activity)
    assert "recent_cutoff" in activity
    assert "recent_cutoff" in activity
