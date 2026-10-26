"""Bilingual storage recovery: rescan or explicit, audited replacement only."""
from html import escape
import json

from app.ui_i18n import I18N_UI_JS


def _phrase(en, de):
    return '<span class="bk-translate" data-en="'+escape(en,quote=True)+'" data-de="'+escape(de,quote=True)+'">'+escape(en)+'</span>'


def storage_warning_html(status):
    from app.storage_replacement import replacement_candidates
    rows=''.join('<li><code>'+escape(str(i['path']))+'</code> · <code>'+
                 escape(str(i['code']))+'</code></li>' for i in status['issues'])
    reasons={
        'workspace_not_empty':('Existing or unknown files must be preserved.',
                               'Vorhandene oder unbekannte Dateien müssen erhalten bleiben.'),
        'catalogue_history':('A historical media catalogue remains.',
                             'Ein früherer Medienkatalog ist erhalten.'),
        'library_or_stock_registry_history':('An existing library or inventory is registered.',
                                             'Eine bestehende Bibliothek oder Bestandserfassung ist registriert.'),
        'retention_survives':('Recovery copies must be preserved.',
                              'Rückfallkopien müssen erhalten bleiben.'),
        'unresolved_reservation':('A previous operation needs recovery first.',
                                  'Ein früherer Vorgang muss zuerst geklärt werden.'),
    }
    reason=str(status.get('setup_blocker') or 'evidence_unreadable')
    en,de=reasons.get(reason,('Existing state cannot be safely treated as a new installation.',
                              'Der vorhandene Zustand kann nicht sicher als Neuinstallation gelten.'))
    available=bool(status.get('can_setup_again') or status.get('can_initialize'))
    setup=('<button type="button" id="storage-initialize">'+
           _phrase('Set up again','Neu einrichten')+'</button>') if available else ''
    guidance=('<p id="storage-setup-evidence">'+
             _phrase('Verified unused storage can be initialized without deleting previous identity records.',
                     'Geprüfter unbenutzter Speicher kann eingerichtet werden, ohne Identitätsbelege zu löschen.')+
             '</p>') if available else (
             '<section id="storage-setup-blocker"><h2>'+
             _phrase('New setup is blocked','Neue Einrichtung ist gesperrt')+
             '</h2><p>'+_phrase(en,de)+'</p><p>Code: <code>'+escape(reason)+'</code></p></section>'
             '<p id="storage-recovery-help">'+
             _phrase('Restore original mounts and folders, preserving databases, journals and retained media. Recheck afterwards. Never delete evidence to make setup pass.',
                     'Stelle ursprüngliche Einbindungen und Ordner wieder her und bewahre Datenbanken, Journale und Rückfallkopien. Prüfe danach erneut. Lösche keine Nachweise, um die Einrichtung zu erzwingen.')+
             '</p>')
    replacements=replacement_candidates(status)
    buttons=''.join('<li><code>'+escape(str(row['path']))+'</code> '
                    '<button type="button" class="storage-replace" data-key="'+
                    escape(str(row['key']),quote=True)+'">'+
                    _phrase('Create replacement folder','Ersatzordner anlegen')+'</button></li>'
                    for row in replacements)
    if buttons:
        buttons=('<h3>'+_phrase('Confirmed loss: create a replacement',
                               'Bestätigter Verlust: Ersatzordner anlegen')+'</h3><p>'+
                _phrase('Only use this when the original folder and its files cannot be recovered. Existing media records are retained as loss evidence. Missing copies can be imported again.',
                        'Nur verwenden, wenn sich der ursprüngliche Ordner und seine Dateien nicht wiederherstellen lassen. Medienhistorie bleibt als Verlustnachweis erhalten. Fehlende Kopien können erneut importiert werden.')+
                '</p><ul>'+buttons+'</ul>')
    token=status.get('setup_token') or ''
    assert not token or (len(token)==64 and all(c in '0123456789abcdef' for c in token))
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekar · Storage recovery</title>
<style>body{font:16px system-ui;background:#141922;color:#edf0f5;margin:0}
dialog{color:inherit;background:#202938;border:2px solid #ffbd57;border-radius:12px;width:min(710px,calc(100% - 36px));max-height:90dvh;overflow:auto;box-sizing:border-box;overflow-wrap:anywhere;padding:24px}
dialog::backdrop{background:#000b}button{padding:11px;margin:6px;min-height:44px;border-radius:7px;cursor:pointer}
li{margin:12px 0}code{font-size:.88em}.languages{display:flex;justify-content:flex-end;gap:8px}.languages button{min-height:34px}
#storage-recovery-panel[hidden]{display:none}section{margin:14px 0}</style></head><body>
<dialog id="storage-protection" open aria-labelledby="storage-title">
<div class="languages"><button type="button" class="bk-lang" data-lang="en">EN</button><button type="button" class="bk-lang" data-lang="de">DE</button></div>
<h1 id="storage-title">'''+_phrase('Storage unavailable','Speicherordner nicht verfügbar')+'''</h1>
<p>'''+_phrase('A previously managed folder is missing, moved or inaccessible. File operations are paused to protect existing data.',
             'Ein bisher verwalteter Ordner fehlt, wurde verschoben oder ist nicht erreichbar. Dateioperationen sind zum Schutz vorhandener Daten angehalten.')+'''</p>
<ul>'''+rows+'''</ul>
<p>'''+_phrase('First restore the original folder or mount, then select Check again.',
             'Stelle zuerst den ursprünglichen Ordner oder Mount wieder her und wähle Erneut prüfen.')+'''</p>
'''+guidance+'''
<button type="button" id="storage-retry">'''+_phrase('Check again','Erneut prüfen')+'''</button>'''+setup+'''
<button type="button" id="storage-recovery-open">'''+_phrase('Repair options','Reparaturmöglichkeiten')+'''</button>
<section id="storage-recovery-panel" hidden><h2>'''+_phrase('Repair existing storage','Vorhandenen Speicher reparieren')+'''</h2>
<p>'''+_phrase('Option 1: restore or rename the original folder and check again. No files or records are changed.',
             'Option 1: den ursprünglichen Ordner wiederherstellen oder umbenennen und erneut prüfen. Dateien und Nachweise bleiben unverändert.')+'''</p>
'''+buttons+'''
<p>'''+_phrase('The independent external archive is never automatically adopted or modified.',
             'Das unabhängige externe Archiv wird niemals automatisch übernommen oder verändert.')+'''</p></section>
<p id="storage-setup-result" role="status" aria-live="polite"></p></dialog>
<script>
(function(){
 const key='bibliothekar-language',root=document.documentElement,result=document.getElementById('storage-setup-result');
 function lang(){try{return localStorage.getItem(key)==='de'?'de':'en'}catch(_){return 'en'}}
 function sync(){const value=lang();root.lang=value;root.dataset.bkLocale=value;
  document.querySelectorAll('.bk-translate').forEach(el=>{el.textContent=el.dataset[value]||''});
  document.querySelectorAll('.bk-lang').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lang===value)));
 }
 for(const b of document.querySelectorAll('.bk-lang'))b.addEventListener('click',()=>{try{localStorage.setItem(key,b.dataset.lang)}catch(_){}sync()});
 sync();
 const dialog=document.getElementById('storage-protection');
 if(dialog.showModal){dialog.removeAttribute('open');dialog.showModal();dialog.addEventListener('cancel',e=>e.preventDefault())}
 document.getElementById('storage-recovery-open').addEventListener('click',()=>{const panel=document.getElementById('storage-recovery-panel');panel.hidden=!panel.hidden});
 function csrf(){const entry=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));return entry?decodeURIComponent(entry.slice(entry.indexOf('=')+1)):''}
 async function post(path,payload){const headers={'Content-Type':'application/json'},token=csrf();if(token)headers['X-Bibliothekar-CSRF']=token;
   const response=await fetch(path,{method:'POST',headers,credentials:'same-origin',body:JSON.stringify(payload)});
   let data={};try{data=await response.json()}catch(_){}if(!response.ok)throw new Error(String(data.detail||response.status));return data;
 }
 document.getElementById('storage-retry').addEventListener('click',async e=>{e.currentTarget.disabled=true;try{await post('/api/settings/storage-recheck',{});}catch(_){result.textContent=lang()==='de'?'Ordner weiterhin nicht verfügbar.':'Storage is still unavailable.'}finally{location.reload()}});
 const setup=document.getElementById('storage-initialize');
 if(setup)setup.addEventListener('click',async()=>{if(!confirm(lang()==='de'?'Geprüfte leere Installation neu einrichten?':'Initialize verified unused storage?'))return;
  setup.disabled=true;try{await post('/api/settings/storage-initialize',{confirmation:'SET UP AGAIN',token:'''+json.dumps(token)+'''});location.reload()}
  catch(_){result.textContent=lang()==='de'?'Neue Einrichtung wurde aus Sicherheitsgründen verweigert.':'Setup was refused for safety.';setup.disabled=false}
 });
 for(const button of document.querySelectorAll('.storage-replace'))button.addEventListener('click',async()=>{
   const path=button.closest('li').querySelector('code').textContent;
   const question=lang()==='de'?'Der bisherige Ordner und seine Dateien können verloren sein. Ersatz für '+path+' anlegen?':'The previous folder and its files may be lost. Replace '+path+'?';
   if(!confirm(question))return;
   const typed=prompt(lang()==='de'?'Zur Bestätigung REPLACE eingeben:':'Type REPLACE to acknowledge the loss:');
   if(typed!=='REPLACE')return;
   button.disabled=true;
   try{const data=await post('/api/settings/storage-replace',{key:button.dataset.key,confirmation:'I ACCEPT MISSING FILES'});
      if(data.restart_required){result.textContent=lang()==='de'?'Ersatz angelegt und dokumentiert. Containerneustart erforderlich.':'Replacement recorded. Restart the container.'}
      else location.reload();
   }catch(_){result.textContent=lang()==='de'?'Ersatz verweigert. Prüfe die weiteren Ordner und Vorgänge.':'Replacement refused. Check other folders and pending operations.';button.disabled=false}
 });
})();
</script><script>'''+I18N_UI_JS+'''</script></body></html>'''
