"""Reachable warning for manual restoration of established storage paths."""
from html import escape
from app.ui_i18n import I18N_UI_JS


def storage_warning_html(status):
    rows=''.join('<li><code>'+escape(str(i['path']))+'</code> · <code>'+escape(str(i['code']))+'</code></li>' for i in status['issues'])
    setup=('<button id="storage-initialize">Neu einrichten</button>' if status.get('can_setup_again') or status.get('can_initialize') else '')
    token=str(status.get('setup_token') or '')
    assert not token or (len(token)==64 and all(c in '0123456789abcdef' for c in token))
    return '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Speicherordner nicht verfügbar</title>
<style>body{font:16px system-ui;background:#141922;color:#edf0f5}dialog{color:inherit;background:#202938;border:2px solid #ffbd57;border-radius:12px;width:min(640px,calc(100% - 48px));box-sizing:border-box;overflow-wrap:anywhere}dialog::backdrop{background:#000b}button{padding:12px;margin:6px;min-height:44px}li{margin:12px 0}</style></head><body>
<dialog id="storage-protection" open aria-labelledby="storage-title"><h1 id="storage-title">Speicherordner nicht verfügbar</h1>
<p>Ein benötigter Verwaltungsordner fehlt, wurde verschoben oder ist nicht eindeutig zugänglich.</p>
<p>Betroffene Vorgänge sind zum Schutz Ihrer Dateien angehalten.</p><ul>'''+rows+'''</ul>
<p>Bitte stellen Sie den ursprünglichen Ordner gegebenenfalls außerhalb der App im NAS-Dateisystem wieder her. Prüfen Sie die Einbindung und den erwarteten Pfad. Es werden keine Ordner automatisch ersetzt.</p>
<button id="storage-retry">Erneut prüfen</button>'''+setup+'''<p id="storage-setup-result" role="status"></p></dialog>
<script>const d=document.getElementById('storage-protection');if(d.showModal){d.removeAttribute('open');d.showModal();d.addEventListener('cancel',e=>e.preventDefault());}document.getElementById('storage-retry').addEventListener('click',async()=>{const button=document.getElementById('storage-retry');button.disabled=true;try{const token=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));const headers={};if(token)headers['X-Bibliothekar-CSRF']=decodeURIComponent(token.slice(token.indexOf('=')+1));await fetch('/api/settings/storage-recheck',{method:'POST',headers,credentials:'same-origin'});}finally{location.reload();}});</script>
<script>
const setupButton=document.getElementById('storage-initialize');
if(setupButton)setupButton.addEventListener('click',async()=>{
const en=document.documentElement.lang==='en';
if(!confirm(en?'Set up this verified empty installation again? Previous identity records will be retained.':'Diese geprüfte leere Installation neu einrichten? Bisherige Identitätsbelege bleiben erhalten.'))return;
setupButton.disabled=true;
try{
const cookie=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));
const headers={'Content-Type':'application/json'};
if(cookie)headers['X-Bibliothekar-CSRF']=decodeURIComponent(cookie.slice(cookie.indexOf('=')+1));
const response=await fetch('/api/settings/storage-initialize',{method:'POST',headers,credentials:'same-origin',body:JSON.stringify({confirmation:'SET UP AGAIN',token:'''+repr(token)+'''})});
const data=await response.json();if(!response.ok)throw new Error(data.detail||'Setup failed');location.reload();
}catch(error){document.getElementById('storage-setup-result').textContent=error.message;setupButton.disabled=false;}
});
</script><script>'''+I18N_UI_JS+'''</script></body></html>'''
