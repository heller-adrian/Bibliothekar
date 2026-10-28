"""Bilingual storage recovery: rescan or explicit, audited replacement only."""
from html import escape
import json

from app.ui_i18n import I18N_UI_JS


def _phrase(en, de):
    return '<span class="bk-translate" data-en="'+escape(en,quote=True)+'" data-de="'+escape(de,quote=True)+'">'+escape(en)+'</span>'


def storage_warning_html(status):
    from app.storage_replacement import replacement_candidates
    explanations = {
        'bootstrap_incomplete': ('Technical setup is incomplete. Check again to resume the verified startup.', 'Die technische Einrichtung ist unvollständig. Erneut prüfen setzt den verifizierten Start fort.'),
        'bootstrap_administrative_review_required': ('RC10 evidence needs offline administrative review and an explicit adoption receipt.', 'RC10-Nachweise benötigen eine administrative Offlineprüfung und einen ausdrücklichen Übernahmebeleg.'),
        'legacy_lock_not_migrated': ('The old shared RC10 lock is preserved and must be migrated to private coordination.', 'Das alte gemeinsame RC10-Lock bleibt erhalten und muss auf private Koordination migriert werden.'),
        'private_acl_untrusted_write': ('Another principal can change private control data. Secure this private dataset and its parents; the shared workspace ACL can remain.', 'Andere Berechtigte können private Steuerdaten verändern. Sichere dieses private Dataset und seine Eltern; die gemeinsame Workspace-ACL kann bestehen bleiben.'),
        'acl_backend_unavailable': ('Native ACL safety could not be verified. Grant the app readable native ACLs on an owner/admin-only private dataset.', 'Die native ACL-Sicherheit konnte nicht geprüft werden. Die App benötigt lesbare native ACLs auf einem privaten Dataset für Eigentümer und Administratoren.'),
        'bootstrap_reservation_mismatch': ('The saved startup reservation contradicts current evidence. Preserve all records for recovery.', 'Die gespeicherte Startupreservation widerspricht den aktuellen Nachweisen. Bewahre alle Nachweise zur Wiederherstellung auf.'),
        'bootstrap_additional_operation': ('An additional operation prevents first-install resume.', 'Eine zusätzliche Operation verhindert die Fortsetzung der Erstinstallation.'),
        'workspace_unknown_entry': ('Unknown content is preserved; it is not automatic first-install data.', 'Unbekannter Inhalt bleibt erhalten; er ist kein automatisch übernehmbarer Erstinstallationsbestand.'),
        'workspace_scan_error': ('The workspace could not be inspected reliably.', 'Der Workspace konnte nicht zuverlässig geprüft werden.'),
        'workspace_scan_changed': ('The workspace changed during inspection. Stop concurrent editors and retry.', 'Der Workspace wurde während der Prüfung verändert. Beende parallele Zugriffe und prüfe erneut.'),
        'bootstrap_completion_receipt_missing': ('The startup completion proof is missing or inconsistent.', 'Der Abschlussnachweis des Starts fehlt oder ist widersprüchlich.'),
        'historical_library_generation': ('Historical library generations prevent automatic first-install resume.', 'Historische Bibliotheksgenerationen verhindern eine automatische Erstinstallationsfortsetzung.'),
        'retention_survives': ('Retained recovery media must be preserved.', 'Aufbewahrte Wiederherstellungsmedien müssen erhalten bleiben.'),
        'startup_failed': ('Technical startup failed; the original cause follows.', 'Der technische Start ist fehlgeschlagen; die ursprüngliche Ursache folgt.'),
    }
    explanations.update({
        'workspace_claim_conflict':('This workspace belongs to another instance or its appdata was lost. Restore the matching appdata backup or select a separate empty workspace.','Dieser Workspace gehört zu einer anderen Instanz oder seine Appdaten gingen verloren. Stelle die zugehörige Appdatensicherung wieder her oder wähle einen getrennten leeren Workspace.'),
        'unresolved_reservation':('A pending file operation requires its original roots and journal recovery before replacement.','Ein offener Dateivorgang benötigt seine ursprünglichen Wurzeln und Journal-Recovery vor einem Ersatz.'),
        'registry_history_mismatch':('The registry contradicts historical library evidence. Restore its consistent backup; a missing registration flag does not authorize new setup.','Die Registry widerspricht historischen Bibliotheksnachweisen. Stelle die konsistente Sicherung wieder her; ein fehlendes Registrierungsmerkmal erlaubt keine Neueinrichtung.'),
        'catalog_identity_mismatch':('The registered catalogue identity is missing or different. Restore its database backup; an empty replacement is not a library recovery.','Die registrierte Katalogidentität fehlt oder weicht ab. Stelle die Datenbanksicherung wieder her; ein leerer Ersatz ist keine Bibliothekswiederherstellung.'),
        'installation_history_missing':('Database or control history is missing. Restore a consistent appdata backup; folder replacement cannot reconstruct a catalogue.','Datenbank oder Steuerhistorie fehlt. Stelle eine konsistente Appdatensicherung wieder her; ein Ersatzordner kann keinen Katalog rekonstruieren.'),
        'mount_identity_changed':('The dataset mount changed or disappeared. Restore the expected mount; no replacement is created on the underlying filesystem.','Die Dataset-Einbindung fehlt oder hat sich geändert. Stelle die erwartete Einbindung wieder her; auf dem darunterliegenden Dateisystem wird kein Ersatz angelegt.'),
        'workspace_identity_changed':('The workspace identity changed. Restore the original dataset; copying individual files into a new folder does not restore its identity.','Die Workspace-Identität hat sich geändert. Stelle das ursprüngliche Dataset wieder bereit; einzelne Dateien in einem neuen Ordner stellen dessen Identität nicht wieder her.'),
        'legacy_layout_requires_explicit_migration':('Keep the existing RC10/RC11 mount layout and its review procedure. A new appdata profile does not automatically adopt old control data.','Behalte das bestehende RC10-/RC11-Mountlayout und dessen Übernahmeverfahren bei. Das neue Appdatenprofil übernimmt alte Steuerdaten nicht automatisch.'),
        'control_file_invalid':('A technical control file has an invalid type or link count. Operations remain paused until the original evidence is verified.','Eine technische Steuerdatei besitzt einen ungültigen Typ oder Linkstatus. Vorgänge bleiben bis zur Prüfung der ursprünglichen Nachweise angehalten.'),
        'private_path_unavailable':('The application cannot open this path with its actual credentials. Check the mount and effective access permissions.','Die Anwendung kann diesen Pfad mit ihren tatsächlichen Benutzerrechten nicht öffnen. Prüfe Einbindung und effektive Zugriffsrechte.'),
    })
    rows = ''
    for item in status['issues']:
        code = str(item['code'])
        message = explanations.get(code)
        rows += '<li><code>'+escape(str(item['path']))+'</code> · <code>'+escape(code)+'</code>'
        if message: rows += '<p>'+_phrase(*message)+'</p>'
        if item.get('detail'):
            detail=str(item['detail'])
            if 'Quellfamilien-ID' in detail or 'source_inventory_conflict:' in detail:
                rows += '<p>'+_phrase('Source history and current inventory disagree. Original source identity is preserved. This is a provenance conflict; check the matching loss records.', 'Quellhistorie und aktueller Bestand widersprechen sich. Die ursprüngliche Quellenidentität bleibt erhalten. Prüfe die zugehörigen Verlustnachweise.')+'</p>'
                rows += '<details><summary>'+_phrase('Technical details','Technische Details')+'</summary><code>'+escape(detail)+'</code></details>'
            else: rows += '<p><code>'+escape(detail)+'</code></p>'
        expected = next((r.get('expected_identity') for r in status.get('folders',[]) if r['path']==item['path']),None)
        if expected is not None:
            from pathlib import Path
            name=Path(item['path']).name
            rows += '<p>'+_phrase('Expected folder: ','Erwarteter Ordner: ')+'<code>'+escape(name)+'</code> <button type="button" class="storage-copy" data-copy="'+escape(name,quote=True)+'">'+_phrase('Copy name','Namen kopieren')+'</button></p>'
            rows += '<details><summary>'+_phrase('Technical identity','Technische Identität')+'</summary><code>'+escape(str(expected))+'</code></details>'
        rows += '</li>'
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
    resume_only=any(i['code']=='bootstrap_incomplete' for i in status['issues'])
    setup=('<button type="button" id="storage-initialize">'+
           _phrase('Set up again','Neu einrichten')+'</button>') if available and not resume_only else ''
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
    if status.get('existing_installation') and not available:
        guidance=''
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
    state = status.get('state','AMBIGUOUS')
    state_text = _phrase('Storage state: ','Speicherzustand: ')+'<code>'+escape(state)+'</code>'
    token=status.get('setup_token') or ''
    assert not token or (len(token)==64 and all(c in '0123456789abcdef' for c in token))
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekar · Storage recovery</title>
<style>body{font:16px system-ui;background:#141922;color:#edf0f5;margin:0}
dialog{color:inherit;background:#202938;border:2px solid #ffbd57;border-radius:12px;width:min(710px,calc(100% - 36px));max-height:90dvh;overflow:auto;box-sizing:border-box;overflow-wrap:anywhere;padding:24px}
dialog::backdrop{background:#000b}button{padding:11px;margin:6px;min-height:44px;border-radius:7px;cursor:pointer}
li{margin:12px 0}code{font-size:.88em}.storage-heading{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.storage-heading h1{margin:0}.languages{display:flex;gap:8px}.languages button{min-height:34px}
#storage-recovery-panel[hidden]{display:none}section{margin:14px 0}</style></head><body>
<dialog id="storage-protection" open aria-labelledby="storage-title">
<div class="storage-heading"><h1 id="storage-title">'''+_phrase('Storage unavailable','Speicherordner nicht verfügbar')+'''</h1><div class="languages"><button type="button" class="bk-lang" data-lang="en">EN</button><button type="button" class="bk-lang" data-lang="de">DE</button></div></div>
<p>'''+_phrase('Storage or technical startup requires verification. File operations are paused to protect existing data.',
             'Speicher oder technischer Start benötigen eine Prüfung. Dateioperationen sind zum Schutz vorhandener Daten angehalten.')+'''</p>
<p>'''+state_text+'''</p><ul>'''+rows+'''</ul>
<p>'''+_phrase('Follow the cause shown above, then select Check again.',
             'Beachte die oben genannte Ursache und wähle anschließend Erneut prüfen.')+'''</p>
'''+guidance+'''
<button type="button" id="storage-retry">'''+_phrase('Check again','Erneut prüfen')+'''</button>'''+setup+'''
<button type="button" id="storage-recovery-open">'''+_phrase('Repair options','Reparaturmöglichkeiten')+'''</button>
<section id="storage-recovery-panel"><h2>'''+_phrase('Repair existing storage','Vorhandenen Speicher reparieren')+'''</h2>
<p>'''+_phrase('Option 1: restore or rename the original folder and check again. No files or records are changed.',
             'Option 1: den ursprünglichen Ordner wiederherstellen oder umbenennen und erneut prüfen. Dateien und Nachweise bleiben unverändert.')+'''</p>
'''+buttons+'''
<p>'''+_phrase('The independent external archive is never automatically adopted or modified.',
             'Das unabhängige externe Archiv wird niemals automatisch übernommen oder verändert.')+'''</p></section>
<p id="storage-setup-result" role="status" aria-live="polite"></p></dialog>
<script>try{document.documentElement.lang=localStorage.getItem('bibliothekar-language')==='de'?'de':'en'}catch(_){document.documentElement.lang='en'}</script>
<script>
(function(){
 const key='bibliothekar-language',root=document.documentElement,result=document.getElementById('storage-setup-result');
 function lang(){try{return localStorage.getItem(key)==='de'?'de':'en'}catch(_){return 'en'}}
 function sync(){const value=lang();root.lang=value;root.dataset.bkLocale=value;
  document.querySelectorAll('.bk-translate').forEach(el=>{el.textContent=el.dataset[value]||''});
  document.querySelectorAll('.bk-lang').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lang===value)));
  window.BibliothekarI18n?.setLocale(value);
 }
 for(const b of document.querySelectorAll('.bk-lang'))b.addEventListener('click',()=>{try{localStorage.setItem(key,b.dataset.lang)}catch(_){}sync()});
 sync();
 document.querySelectorAll('.storage-copy').forEach(b=>b.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(b.dataset.copy)}catch(_){result.textContent=b.dataset.copy}}));
 const dialog=document.getElementById('storage-protection');
 if(dialog.showModal){dialog.removeAttribute('open');dialog.showModal();dialog.addEventListener('cancel',e=>e.preventDefault())}
 document.getElementById('storage-recovery-open').addEventListener('click',()=>{const panel=document.getElementById('storage-recovery-panel');panel.hidden=!panel.hidden});
 function csrf(){const entry=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));return entry?decodeURIComponent(entry.slice(entry.indexOf('=')+1)):''}
 async function post(path,payload){const headers={'Content-Type':'application/json'},token=csrf();if(token)headers['X-Bibliothekar-CSRF']=token;
   const response=await fetch(path,{method:'POST',headers,credentials:'same-origin',body:JSON.stringify(payload)});
   let data={};try{data=await response.json()}catch(_){}if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));return data;
 }
 document.getElementById('storage-retry').addEventListener('click',async e=>{e.currentTarget.disabled=true;try{await post('/api/settings/storage-recheck',{});location.reload()}catch(error){result.textContent=error.message;e.currentTarget.disabled=false}});
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
   }catch(error){result.textContent=error.message;button.disabled=false}
 });
})();
</script><script>'''+I18N_UI_JS+'''</script></body></html>'''
