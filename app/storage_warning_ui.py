"""Reachable warning for manual restoration of established storage paths."""
from html import escape
from app.ui_i18n import I18N_UI_JS


def storage_warning_html(status):
    rows=''.join('<li><code>'+escape(str(i['path']))+'</code> · <code>'+escape(str(i['code']))+'</code></li>' for i in status['issues'])
    reasons={
        'unknown_initialization':'Die historischen Einrichtungsbelege sind unvollständig oder widersprüchlich.',
        'incomplete_historical_roots':'Die früheren Verwaltungsordner sind nicht vollständig durch Identitäten belegt.',
        'ambiguous_historical_roots':'Die historischen Verwaltungsordner sind nicht eindeutig zugeordnet.',
        'workspace_or_legacy_binding':'Die Workspace-Identität oder die historischen Ordnernamen sind nicht eindeutig bestätigt.',
        'database_binding_changed':'Die Datenbankablage widerspricht den historischen Bindungen.',
        'archive_content_survives':'Im Archiv sind noch Daten vorhanden. Diese dürfen nicht als neue Installation übergangen werden.',
        'archive_unavailable':'Das konfigurierte Archiv ist nicht nachweislich erreichbar. Prüfen Sie zuerst seine Einbindung und Leserechte.',
        'historical_external_binding':'Ein früher gebundener externer Speicherort fehlt, wurde ersetzt oder enthält noch Daten.',
        'workspace_not_empty':'Im Arbeitsbereich sind noch Daten oder unbekannte Einträge vorhanden.',
        'catalogue_history':'Eine erhaltene Datenbank enthält noch frühere Aufträge oder Bestandsdaten.',
        'library_or_stock_registry_history':'Die Registry enthält noch Bibliotheks- oder Bestandszuordnungen.',
        'retention_survives':'Private Rückfallkopien sind noch vorhanden und müssen erhalten bleiben.',
        'unresolved_reservation':'Es bestehen noch ungeklärte Operations- oder Recoverybelege.',
    }
    available=status.get('can_setup_again') or status.get('can_initialize')
    reason=str(status.get('setup_blocker') or 'evidence_unreadable')
    explanation=reasons.get(reason,'Die sichere Leerheit und Zuordnung der Installation ist noch nicht vollständig nachgewiesen.')
    guidance=('''<p id="storage-setup-evidence">Die leere Installation und ihre verbleibenden Bindungen wurden geprüft. Eine neue Einrichtung erfordert Ihre Bestätigung und bewahrt die bisherigen Identitätsbelege.</p>''' if available else
        '<section id="storage-setup-blocker"><h2>Neue Einrichtung derzeit gesperrt</h2><p>'+escape(explanation)+'</p><p>Diagnose: <code>'+escape(reason)+'</code></p></section>'
        '<p id="storage-recovery-help">Stoppen Sie die App und weitere Schreibzugriffe. Sichern Sie alle erhaltenen Datenbanken einschließlich WAL-Dateien, Konfiguration, Journale und Retentionskopien. Stellen Sie die ursprünglichen Dataset-Einbindungen und einen zusammengehörigen Sicherungsstand wieder her. Danach erneut prüfen. Keine Operationsnachweise löschen und keine leeren Ersatzordner über vorhandene Daten legen.</p>')
    # The recovery entrance is always reachable; server-side authorization
    # still decides whether the actual setup transition is safe.
    setup=('<button id="storage-initialize">Set up again</button>' if available else '')
    recovery=('<button id="storage-recovery-open" type="button">Setup / recovery options</button>'
              '<section id="storage-recovery-panel" hidden><h2>Setup and recovery</h2>'
              '<p>A new installation can use an existing archive; choose an archive when registering your first library. It will not be modified or adopted automatically.</p>'
              '<p>For an established installation with missing or renamed folders, restore their original paths rather than replacing them with empty folders.</p>'
              '<p>If setup is blocked, the reason shown above explains which existing data or safety record must be preserved.</p>'
              '</section>')
    token=str(status.get('setup_token') or '')
    assert not token or (len(token)==64 and all(c in '0123456789abcdef' for c in token))
    return '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Speicherordner nicht verfügbar</title>
<style>body{font:16px system-ui;background:#141922;color:#edf0f5}dialog{color:inherit;background:#202938;border:2px solid #ffbd57;border-radius:12px;width:min(640px,calc(100% - 48px));box-sizing:border-box;overflow-wrap:anywhere}dialog::backdrop{background:#000b}button{padding:12px;margin:6px;min-height:44px}li{margin:12px 0}</style></head><body>
<dialog id="storage-protection" open aria-labelledby="storage-title"><h1 id="storage-title">Speicherordner nicht verfügbar</h1>
<p>Ein benötigter Verwaltungsordner fehlt, wurde verschoben oder ist nicht eindeutig zugänglich.</p>
<p>Betroffene Vorgänge sind zum Schutz Ihrer Dateien angehalten.</p><ul>'''+rows+'''</ul>
<p>Bitte stellen Sie den ursprünglichen Ordner gegebenenfalls außerhalb der App im NAS-Dateisystem wieder her. Prüfen Sie die Einbindung und den erwarteten Pfad. Es werden keine Ordner automatisch ersetzt.</p>'''+guidance+'''
<button id="storage-retry">Erneut prüfen</button>'''+setup+recovery+'''<p id="storage-setup-result" role="status"></p></dialog>
<script>const d=document.getElementById('storage-protection');if(d.showModal){d.removeAttribute('open');d.showModal();d.addEventListener('cancel',e=>e.preventDefault());}document.getElementById('storage-retry').addEventListener('click',async()=>{const button=document.getElementById('storage-retry');button.disabled=true;try{const token=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));const headers={};if(token)headers['X-Bibliothekar-CSRF']=decodeURIComponent(token.slice(token.indexOf('=')+1));await fetch('/api/settings/storage-recheck',{method:'POST',headers,credentials:'same-origin'});}finally{location.reload();}});</script>
<script>
document.getElementById('storage-recovery-open').addEventListener('click',()=>{const panel=document.getElementById('storage-recovery-panel');panel.hidden=!panel.hidden;});
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
