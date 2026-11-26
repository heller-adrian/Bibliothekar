"""First-library setup editor backed by the normal library settings APIs."""
from html import escape

from app.legacy_adoption_i18n import PATTERNS, TRANSLATIONS
from app.ui_i18n import i18n_ui_js
from app.ui_shell import (
    EVENT_PREFERENCES_CSS, EVENT_PREFERENCES_JS, EVENT_PREFERENCES_MARKUP, SETTINGS_REQUEST_JS, apply_setup_shell,
)


def preferences_html(library_name: str) -> str:
    return apply_setup_shell(
        _PAGE.replace("{{EDITOR}}", EVENT_PREFERENCES_MARKUP)
        .replace("{{EDITOR_CSS}}", EVENT_PREFERENCES_CSS)
        .replace("{{SCRIPT}}", SETTINGS_REQUEST_JS + EVENT_PREFERENCES_JS)
        .replace("{{LIBRARY}}", escape(library_name, quote=True)),
        localization_js=i18n_ui_js(TRANSLATIONS, PATTERNS),
    )


_PAGE = r"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekseinstellungen · Bibliothekar</title>
<style>
{{EDITOR_CSS}}
#first-library-preferences{max-width:950px;margin:26px auto;padding:16px}
#first-library-editor{margin:0 0 16px;padding:0;border:0;min-inline-size:0}
#first-library-preferences h1{font-size:clamp(1.5rem,4vw,2.3rem);margin:4px 0}
#first-library-preferences p{color:var(--bk-muted);line-height:1.5}
#first-library-preferences input:not([type=checkbox]):not([type=radio]),#first-library-preferences select{box-sizing:border-box;max-width:100%;padding:8px;background:var(--bk-paper);color:var(--bk-ink);border:1px solid var(--bk-line);border-radius:9px}
#first-library-preferences button{background:var(--bk-surface-2);color:var(--bk-ink);border:1px solid var(--bk-line);border-radius:10px;padding:9px 15px;cursor:pointer}
#first-library-preferences #first-library-next{background:var(--bk-blue);color:white}
#first-library-preferences button:disabled{opacity:.55}
#first-library-preferences .actions{border-top:1px solid var(--bk-line);background:var(--bk-paper);padding:15px 0}
#first-library-status{white-space:pre-wrap;margin-top:10px}
#first-library-status[data-error=true]{color:var(--bk-danger)}
</style>
</head>
<body>
<main id="first-library-preferences">
<h1>Ordnerstruktur und Benennung</h1>
<p>Diese Einstellungen gelten für <strong>{{LIBRARY}}</strong> und bleiben nach der Übernahme
für spätere Ereignisse und Importe erhalten. Du kannst die Standardwerte unverändert übernehmen.</p>
<fieldset id="first-library-editor" aria-label="Ordnerstruktur und Benennung" disabled>{{EDITOR}}</fieldset>
<div class="actions"><button id="first-library-next" type="button" disabled>Weiter · Übernahme auswählen</button>
<div id="first-library-status" role="status" aria-live="polite">Einstellungen werden geladen …</div></div>
</main>
<script>
(() => {
  "use strict";
{{SCRIPT}}
  const next = document.getElementById("first-library-next");
  const editor = document.getElementById("first-library-editor");
  const status = document.getElementById("first-library-status");
  const preferences = bkEventPreferences(bkJson, bkEscape);
  const msg = (value, bad=false) => {status.textContent=value;status.dataset.error=String(bad);};
  next.addEventListener("click",async()=>{
    next.disabled=true;
    editor.disabled=true;
    msg("Einstellungen werden gespeichert …");
    try{
      await preferences.saveAndVerify();
      const result=await bkJson("/api/setup/preferences/continue",{method:"POST"});
      location.replace(result.next);
    }catch(error){
      msg(error.message,true);
      next.disabled=false;
      editor.disabled=false;
    }
  });
  preferences.load({strict:true}).then(()=>{
    editor.disabled=false;
    next.disabled=false;
    msg("Einstellungen geladen. Ohne Änderung direkt mit Weiter fortfahren.");
  }).catch(error=>msg(error.message,true));
})();
</script>
</body></html>"""
