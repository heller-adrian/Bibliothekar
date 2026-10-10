"""Browser-native confirmation localisation, with no change to decision semantics."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from app.ui_i18n import I18N_UI_JS


def test_0502_native_dialogs_keep_confirmation_semantics(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    harness = r'''
globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
};
globalThis.document = {
  readyState: "loading",
  documentElement: {dataset: {}, lang: ""},
  addEventListener: () => {},
  querySelectorAll: () => [],
  body: null,
};
const seen = [];
globalThis.window = {
  alert: (message) => { seen.push(["alert", message]); return undefined; },
  confirm: (message) => { seen.push(["confirm", message]); return false; },
  prompt: (message, defaultValue) => {
    seen.push(["prompt", message, defaultValue]);
    return "keep user-typed characters: Ü";
  },
  dispatchEvent: () => {},
};
globalThis.CustomEvent = function CustomEvent(name, options) {
  this.name = name; this.detail = options.detail;
};
eval(DICTIONARY_SCRIPT);
const t = window.BibliothekarI18n;
if (t.getLocale() !== "en") throw new Error("New browser locale must default to English");
if (window.confirm("Papierkorb wirklich endgültig entleeren?") !== false) {
  throw new Error("Native cancel must stay cancel");
}
window.alert("Änderungsauftrag");
if (window.prompt("Ereignisname", "Ein Benutzername") !== "keep user-typed characters: Ü") {
  throw new Error("User input must never be translated");
}
t.setLocale("de");
window.confirm("Papierkorb wirklich endgültig entleeren?");
if (seen[0][1] !== "Permanently empty the trash?") throw new Error("English confirmation missing");
if (seen[1][1] !== "Change request") throw new Error("English alert missing");
if (seen[2][1] !== "Event name" || seen[2][2] !== "Ein Benutzername") {
  throw new Error("Prompt title/default incorrectly processed");
}
if (seen[3][1] !== "Papierkorb wirklich endgültig entleeren?") {
  throw new Error("German native prompt text must remain original");
}
console.log("PASS");
'''
    # The translator payload is inserted as a JSON JavaScript string;
    # this fixture never mounts any external directory.
    script = "const DICTIONARY_SCRIPT = " + json.dumps(I18N_UI_JS, ensure_ascii=False) + ";\n" + harness
    file = tmp_path / "native-dialog-test.cjs"
    file.write_text(script, encoding="utf-8")
    result = subprocess.run([node, str(file)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "PASS"
