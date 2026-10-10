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


def test_0502_language_switch_restores_dynamic_counter_text(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    harness = r'''
globalThis.Node = {TEXT_NODE: 3, ELEMENT_NODE: 1};
const parent = {closest: () => null};
const dynamic = {nodeType: 3, nodeValue: "3 Gruppen ausgewählt", parentElement: parent};
const body = {nodeType: 1, closest: () => null};
globalThis.document = {
  readyState: "loading",
  documentElement: {dataset: {}, lang: ""},
  body: body,
  addEventListener: () => {},
  querySelectorAll: () => [],
  createTreeWalker: () => {
    let seen = false;
    return {
      currentNode: null,
      nextNode() {
        if (seen) return false;
        seen = true;
        this.currentNode = dynamic;
        return true;
      },
    };
  },
};
globalThis.localStorage = {getItem: () => null, setItem: () => {}};
globalThis.window = {
  alert: () => {},
  confirm: () => true,
  prompt: () => "",
  dispatchEvent: () => {},
};
globalThis.CustomEvent = function () {};
eval(DICTIONARY_SCRIPT);
const i18n = window.BibliothekarI18n;
i18n.setLocale("en");
if (dynamic.nodeValue !== "3 groups selected") {
  throw new Error("English counter failed: " + dynamic.nodeValue);
}
i18n.setLocale("de");
if (dynamic.nodeValue !== "3 Gruppen ausgewählt") {
  throw new Error("Original German counter was lost: " + dynamic.nodeValue);
}
console.log("PASS");
'''
    script = "const DICTIONARY_SCRIPT = " + json.dumps(I18N_UI_JS, ensure_ascii=False) + ";\n" + harness
    file = tmp_path / "dynamic-locale-test.cjs"
    file.write_text(script, encoding="utf-8")
    result = subprocess.run([node, str(file)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "PASS"
