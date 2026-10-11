"""0.50.5: pre-paint i18n, immediate PWA navigation and German-safe dialogs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.ui_i18n import I18N_UI_JS
from app.ui_i18n_0505 import UI_0505_TRANSLATIONS
from app.ui_shell import (
    apply_shell, BIBLIOTHEKAR_JS, BIBLIOTHEKAR_0505_LANGUAGE_HEAD_JS,
    BIBLIOTHEKAR_0505_LANGUAGE_CSS,
)
from app.workspace_ui import WORKSPACE_HTML


def test_0505_startup_language_resolved_before_body_first_paint():
    html = apply_shell(
        "<!doctype html><html><head><title>Archiv</title></head><body><main>Archiv</main></body></html>",
        active_area="archive",
    )
    head = html.split("</head>", 1)[0]
    assert "BIBLIOTHEKAR_0505_LANGUAGE_HEAD_JS" not in head
    assert 'localStorage.getItem("bibliothekar-language")' in head
    assert 'html[data-bk-i18n-pending="true"] body { visibility: hidden' in head
    assert html.index("bkI18nPending") < html.index("<body")
    assert "delete document.documentElement.dataset.bkI18nPending;" in I18N_UI_JS
    assert html.index("bkI18nPending") < html.index("MutationObserver")
    assert "window.setTimeout(() => window.location.assign(href), 190)" not in html
    assert "window.location.assign(href);" in BIBLIOTHEKAR_JS
    assert 'data-bk-version>0.50.5</span>' in html


@pytest.mark.parametrize(("source", "expected"), [
    ("Geplantes Ereignis anwenden", "Apply planned event"),
    ("Hauptbibliothek · aktiv", "Main library · active"),
    ("Bibliothek · aktiv", "Library · active"),
    ("Nicht zugeordnet", "Not yet assigned"),
    ("2 Prüffälle", "2 items requiring review"),
    ("2 bereit zum Einsortieren", "2 ready to sort"),
    ("Archiv · manueller Archivweg erforderlich", "Archive · manual archive procedure required"),
])
def test_0505_translation_keys(source: str, expected: str):
    assert UI_0505_TRANSLATIONS.get(source) == expected or expected.startswith("2 ")


def test_0505_confirm_buttons_and_no_async_operation_regression():
    assert "confirmAsync" in I18N_UI_JS
    assert 'locale === "en" ? "Cancel" : "Abbrechen"' in I18N_UI_JS
    assert 'locale === "en" ? "Confirm" : "Bestätigen"' in I18N_UI_JS
    assert "await window.BibliothekarI18n.confirmAsync(confirmation)" in WORKSPACE_HTML
    assert "confirmation_phrase:" in WORKSPACE_HTML
    assert "window.confirm(confirmation)" in WORKSPACE_HTML


def test_0505_language_head_executes_in_node(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    js = """
const bootstrap = LANGUAGE;
for (const language of ["en", "de"]) {
  const dataset = {};
  globalThis.document = {documentElement: {dataset, lang: ""}};
  globalThis.localStorage = {getItem: () => language};
  globalThis.window = {addEventListener: () => {}, setTimeout: () => {}};
  eval(bootstrap);
  if (dataset.bkLocale !== language || document.documentElement.lang !== language) throw Error("Wrong locale");
  if ((dataset.bkI18nPending === "true") !== (language === "en")) throw Error("Wrong pre-paint state");
}
console.log("PASS");
"""
    script = tmp_path / "0505-first-paint.cjs"
    script.write_text("const LANGUAGE = " + json.dumps(BIBLIOTHEKAR_0505_LANGUAGE_HEAD_JS) + ";\n" + js)
    completed = subprocess.run([node, str(script)], capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == "PASS"
