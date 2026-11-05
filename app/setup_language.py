"""Language selector for the two unauthenticated/first-run screens.

The choice uses exactly the ordinary app's browser-local language key; it
does not translate or modify physical directory paths and stored settings.
"""
from __future__ import annotations
import re

_HEAD = r"""<script>
(function(){var l="en";try{l=localStorage.getItem("bibliothekar-language")==="de"?"de":"en"}catch(_){}
document.documentElement.lang=l;document.documentElement.dataset.bkLocale=l})();
</script>"""
_CSS = r"""<style>

/* Login and first-library onboarding share the original dark-blue brand field. */
html:has(body.bk-setup-page) { background:#15222c; color-scheme:dark; }
body.bk-setup-page {
  min-height:100dvh;
  display:flex!important;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  gap:16px;
  margin:0!important;
  padding:26px 16px!important;
  background:#15222c!important;
  color:#f4f1e8;
}
body.bk-setup-page .bk-setup-brand {
  display:flex;
  justify-content:center;
  align-items:center;
  width:min(440px,calc(100vw - 32px));
  margin:0 auto;
  background:#15222c;
}
body.bk-setup-page .bk-setup-brand img {
  display:block;
  width:min(360px,78vw);
  max-width:100%;
  height:auto;
  aspect-ratio:489.84 / 133.36;
  object-fit:contain;
}
body.bk-setup-page main {
  margin:0 auto!important;
  max-width:calc(100vw - 32px);
}
body.bk-setup-page .bk-setup-lang { margin-bottom:16px; }
@media(max-width:540px) {
  body.bk-setup-page { justify-content:flex-start; padding-top: min(10vh,52px)!important; }
  body.bk-setup-page .bk-setup-brand img {width:min(315px,82vw);}
}
/* Desktop: brand is a fixed, left-aligned page title independent of the
   form. Keep the login and onboarding forms at their original center. */
@media(min-width:821px) {
  body.bk-setup-page {
    display:grid!important;
    place-items:center;
    justify-content:initial;
    align-items:initial;
    padding:24px!important;
  }
  body.bk-setup-page main {
    margin:0 auto!important;
    justify-self:center;
    align-self:center;
  }
  body.bk-setup-page .bk-setup-brand {
    position:fixed;
    top:clamp(24px,4vh,64px);
    left:50%;
    transform:translateX(-50%);
    width:min(830px,48vw);
    max-width:calc(100vw - 56px);
    margin:0;
    justify-content:center;
    pointer-events:none;
  }
  body.bk-setup-page .bk-setup-brand img {
    width:100%;
    max-width:100%;
    height:auto;
  }
}
.bk-setup-lang{display:flex;justify-content:flex-end;gap:6px;margin:0 0 18px}
.bk-setup-lang button{width:auto!important;min-width:43px;margin:0!important;padding:7px 10px!important;
border:1px solid #586774!important;border-radius:8px;background:transparent!important;font-size:.85rem!important}
.bk-setup-lang button[aria-pressed=true]{background:#1974c6!important;border-color:#1974c6!important;color:white!important}
[data-bk-setup-lang][hidden]{display:none!important}
html[data-bk-locale=en] [data-bk-setup-lang=de],
html[data-bk-locale=de] [data-bk-setup-lang=en]{display:none!important}
</style>"""
_JS = r"""<script>
(function(){
const key="bibliothekar-language";
function locale(){try{return localStorage.getItem(key)==="de"?"de":"en"}catch(_){return document.documentElement.dataset.bkLocale==="de"?"de":"en"}}
window.bkSetupText=(en,de)=>locale()==="de"?de:en;
function sync(){
 const l=locale(),root=document.documentElement;
 root.lang=l;root.dataset.bkLocale=l;
 document.querySelectorAll("[data-bk-setup-en][data-bk-setup-de]").forEach(el=>{
   el.textContent=l==="de"?el.dataset.bkSetupDe:el.dataset.bkSetupEn;
 });
 document.querySelectorAll("[data-bk-setup-placeholder-en]").forEach(el=>{
   el.placeholder=l==="de"?el.dataset.bkSetupPlaceholderDe:el.dataset.bkSetupPlaceholderEn;
 });
 document.querySelectorAll("[data-bk-setup-lang]").forEach(el=>{el.hidden=el.dataset.bkSetupLang!==l});
 document.querySelectorAll("[data-bk-setup-choice]").forEach(el=>el.setAttribute("aria-pressed",String(el.dataset.bkSetupChoice===l)));
 document.title=l==="de"?document.body.dataset.bkSetupTitleDe:document.body.dataset.bkSetupTitleEn;
}
document.querySelectorAll("[data-bk-setup-choice]").forEach(button=>button.addEventListener("click",()=>{
 const l=button.dataset.bkSetupChoice;
 if(l!=="de"&&l!=="en")return;
 try{localStorage.setItem(key,l)}catch(_){}
 if(window.BibliothekarI18n)window.BibliothekarI18n.setLocale(l);
 sync();
}));
window.addEventListener("bk-language-changed",sync);
window.addEventListener("load",sync,{once:true});
sync();
})();
</script>"""
_SWITCH = ('<div class="bk-setup-lang" role="group" aria-label="Language / Sprache">'
           '<button type="button" data-bk-setup-choice="en" aria-pressed="true">EN</button>'
           '<button type="button" data-bk-setup-choice="de" aria-pressed="false">DE</button></div>')


def _label(en: str, de: str) -> str:
    return (f'<span data-bk-setup-en="{en}" data-bk-setup-de="{de}" '
            f'data-bk-preserve-language>{en}</span>')


def localize_setup_html(html: str, page: str) -> str:
    if page == "onboarding":
        html=html.replace('<body><main><section class="card">',
            '<body class="bk-setup-page" data-bk-setup-title-en="Bibliothekar · Set up library" '
            'data-bk-setup-title-de="Bibliothekar · Bibliothek einrichten">'
            '<main><section class="card">'+_SWITCH,1)
        html=html.replace('<h1>Erste Bibliothek einrichten</h1>',
            '<h1 data-bk-setup-en="Set up your first library" '
            'data-bk-setup-de="Erste Bibliothek einrichten" data-bk-preserve-language>'
            'Set up your first library</h1>',1)
        de=('Bibliothekar besitzt noch keine Bibliothek. Lege jetzt Name, Arbeitsbereich '
            'und das in TrueNAS read-only gemountete Archiv fest. Es wird kein '
            'technischer <code>main</code>-Arbeitsordner angelegt.')
        en=('Bibliothekar has no library yet. Choose a name, workspace and the archive '
            'mounted read-only in TrueNAS. No technical <code>main</code> workspace folder is created.')
        html=html.replace('<p>'+de+'</p>',
            '<p data-bk-setup-lang="en" data-bk-preserve-language>'+en+'</p>'
            '<p data-bk-setup-lang="de" data-bk-preserve-language>'+de+'</p>',1)
        for de,en in (("Bibliotheksname","Library name"),
                      ("Arbeitsbereich · RW","Workspace · RW"),
                      ("Archiv · eigener RO-Mount","Archive · separate RO mount")):
            html=html.replace("<label>"+de+"<input", "<label>"+_label(en,de)+"<input",1)
        html=html.replace('placeholder="z. B. Kamerabibliothek"',
            'placeholder="e.g. Camera Library" data-bk-preserve-language '
            'data-bk-setup-placeholder-en="e.g. Camera Library" '
            'data-bk-setup-placeholder-de="z. B. Kamerabibliothek"',1)
        html=re.sub(r'placeholder="([^"]+)/Kamerabibliothek"',
            lambda m:(f'placeholder="{m.group(1)}/Camera-Library" data-bk-preserve-language '
                      f'data-bk-setup-placeholder-en="{m.group(1)}/Camera-Library" '
                      f'data-bk-setup-placeholder-de="{m.group(1)}/Kamerabibliothek"'),
            html,count=1)
        html=re.sub(r'<p class="hint">Leer lassen: Bibliothekar erzeugt unter (<code>.*?</code>) '
                    r'automatisch einen Ordner aus dem Bibliotheksnamen.</p>',
            lambda m:('<p class="hint" data-bk-setup-lang="en" data-bk-preserve-language>'
                      'Leave blank: Bibliothekar automatically creates a folder under '+m.group(1)+
                      ' based on the library name.</p>'
                      '<p class="hint" data-bk-setup-lang="de" data-bk-preserve-language>'
                      'Leer lassen: Bibliothekar erzeugt unter '+m.group(1)+
                      ' automatisch einen Ordner aus dem Bibliotheksnamen.</p>'),
            html,count=1)
        html=html.replace('id="create" type="button">Bibliothek prüfen und anlegen</button>',
            'id="create" type="button" data-bk-setup-en="Check and create library" '
            'data-bk-setup-de="Bibliothek prüfen und anlegen" data-bk-preserve-language>'
            'Check and create library</button>',1)
        html=html.replace('id="status" role="status"', 'id="status" role="status" data-bk-preserve-language',1)
        html=html.replace('statusEl.textContent="Bibliothek wird geprüft …"',
            'statusEl.textContent=bkSetupText("Checking library…","Bibliothek wird geprüft …")',1)
        html=html.replace('statusEl.textContent="Bibliothek eingerichtet. Bibliothekar wird geöffnet …"',
            'statusEl.textContent=bkSetupText("Library created. Opening Bibliothekar…",'
            '"Bibliothek eingerichtet. Bibliothekar wird geöffnet …")',1)
        html=html.replace('statusEl.textContent=e.message',
            'statusEl.textContent=window.BibliothekarI18n?.t(e.message)||e.message',1)
        html=html.replace('payload.display_name||"Bibliothek"', 'payload.display_name||"Library"',1)
    elif page == "login":
        html=html.replace('<body><main><h1>Bibliothekar</h1>',
            '<body class="bk-setup-page" data-bk-setup-title-en="Bibliothekar · Sign in" '
            'data-bk-setup-title-de="Bibliothekar · Anmelden">'
            '<main>'+_SWITCH+'<h1>Bibliothekar</h1>',1)
        html=html.replace('<p>Secure access to your camera library</p>',
            '<p data-bk-setup-lang="en" data-bk-preserve-language>'
            'Secure access to your camera library</p>'
            '<p data-bk-setup-lang="de" data-bk-preserve-language>'
            'Sicherer Zugang zu deiner Kamerabibliothek</p>',1)
        warning=("<p class='warning'>No administrator password has been configured. "
                 "Create an <code>admin-password</code> file in the TrueNAS config directory "
                 "with a strong password of at least 16 characters and restart the container.</p>")
        html=html.replace(warning, warning.replace("<p class='warning'>",
            "<p class='warning' data-bk-setup-lang='en' data-bk-preserve-language>")
            +"<p class='warning' data-bk-setup-lang='de' data-bk-preserve-language>"
            "Es ist noch kein Administratorpasswort eingerichtet. Erstelle im "
            "TrueNAS-Konfigurationsverzeichnis eine Datei <code>admin-password</code> "
            "mit einem sicheren Passwort von mindestens 16 Zeichen und starte den Container neu.</p>",1)
        html=html.replace('<label for="password">Administrator password</label>',
            '<label for="password">'+_label("Administrator password","Administratorpasswort")+'</label>',1)
        html=html.replace('<button type="submit">Sign in</button>',
            '<button type="submit" data-bk-setup-en="Sign in" '
            'data-bk-setup-de="Anmelden" data-bk-preserve-language>Sign in</button>',1)
        html=html.replace('id="error" role="alert"', 'id="error" role="alert" data-bk-preserve-language',1)
        html=html.replace('"Too many attempts. Please try again later."',
            'bkSetupText("Too many attempts. Please try again later.",'
            '"Zu viele Anmeldeversuche. Bitte versuche es später erneut.")',1)
        html=html.replace('"Sign-in failed. Check your password and configuration."',
            'bkSetupText("Sign-in failed. Check your password and configuration.",'
            '"Anmeldung fehlgeschlagen. Bitte prüfe Passwort und Konfiguration.")',1)
    else:
        raise ValueError(page)
    html=html.replace(
        "<main>",
        '<div class="bk-setup-brand" aria-label="Bibliothekar">'
        '<img src="/assets/bibliothekar-logo-v3.svg?v=0.56.2" alt="Bibliothekar" '
        'width="360" height="98" decoding="async"></div><main>',
        1,
    )
    html=html.replace(
        "</head>",
        '<link rel="icon" type="image/svg+xml" '
        'href="/assets/bibliothekar-logo-symbol-background.svg?v=0.56.2">'
        '<link rel="apple-touch-icon" sizes="192x192" '
        'href="/assets/bibliothekar-icon-192.png?v=0.56.2">'
        '<link rel="manifest" href="/manifest.webmanifest">'
        + _HEAD + _CSS + "</head>",
        1,
    )
    html=html.replace("</body>",_JS+"</body>",1)
    return html
