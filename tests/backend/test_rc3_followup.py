"""RC3 manual follow-up, synthetic filesystem and catalogue only."""
import json,hashlib
from pathlib import Path
import pytest
from app import main,trash_import as ti
from app.database import database_connection,create_job
from app.event_structure_changes import verify_archived_structure_change
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import direct_import_lifecycle,setup_live_import,queue_and_run
from tests.backend.test_rc1_package_a import archived_change


def test_repeat_verified_does_not_queue_empty_job(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context);before=source.read_bytes()
    with database_connection(dbs[0]) as c: count=c.execute("SELECT COUNT(*) FROM jobs WHERE operation='folder_import'").fetchone()[0]
    response=main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':True})
    assert response.status_code==202
    from app.database import claim_next_job,get_job
    check=claim_next_job(dbs[0]);assert check['operation']=='sd_recheck'
    main.process_claimed_job(check,library_context=context)
    done=get_job(dbs[0],check['id']);assert done['state']=='completed'
    assert done['result']['status']=='already_backed_up'
    assert done['result']['integrity_verified'] is True
    with database_connection(dbs[0]) as c:
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='folder_import'").fetchone()[0]==count
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert source.read_bytes()==before


def test_verified_rename_updates_canonical_name(tmp_path):
    db,ws,archive,root,change,prepared=archived_change(tmp_path)
    document=json.loads(Path(prepared['prepared_event_json_path']).read_text())
    assert document['event']['name']=='Renamed'
    before=hashlib.sha256((root/'Alle/A.JPG').read_bytes()).hexdigest()
    assert verify_archived_structure_change(db,archive,ws,change['id'])['status']=='completed'
    from app.database import initialize_database
    for _ in range(3):
        initialize_database(db)
        with database_connection(db) as c:
            assert tuple(c.execute("SELECT name,folder_name FROM events WHERE id='e'").fetchone())==('Renamed',root.name)
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert hashlib.sha256((root/'Alle/A.JPG').read_bytes()).hexdigest()==before
    from app.database import list_job_events
    from app.archive_transfer import list_archive_candidates
    assert next(e for e in list_job_events(db,'j') if e['id']=='e')['name']=='Renamed'
    summary=list_archive_candidates(db,archive,observe_current=True)
    matches=[e for e in summary['candidates'] if e['event_id']=='e']
    assert matches and all(e['name']=='Renamed' for e in matches)


@pytest.mark.parametrize('state',['completed','copying','failed','missing'])
def test_cleanup_skips_release_only_with_completed_catalogue(fixture,state):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    root=storage_paths(ws)['trash_root'];p=root/'unknown.JPG';p.write_bytes(b'original')
    jid='TRASH_IMPORT_FINISHED';stage=ti.stage_parent(ws)/jid;stage.mkdir()
    record={'job_id':jid,'relative_paths':[p.name],'files':[{'relative_path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size}]}
    journal=ti.stage_parent(ws)/(jid+'.json');journal.write_text(json.dumps(record))
    create_job(db,job_id=jid,kind='sd_import',trigger_type='manual',operation='trash_import',source_path=str(stage))
    cleanup=ti.cleanup_successful_trash_import(ws,jid,[])
    with database_connection(db) as c:
        if state=='missing': c.execute('DELETE FROM jobs WHERE id=?',(jid,))
        else:c.execute('UPDATE jobs SET state=?,result_json=? WHERE id=?',(state,json.dumps({'trash_source_cleanup':cleanup}),jid))
    assert ti.protected_trash_paths(None,ws)==(set() if state=='completed' else {p.name})
    assert p.read_bytes()==b'original' and journal.is_file()


def test_complete_cleanup_allows_explicit_empty_keeps_journal(fixture):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    root=storage_paths(ws)['trash_root'];p=root/'old.JPG';p.write_bytes(b'original')
    jid='TRASH_IMPORT_CLEAN';stage=ti.stage_parent(ws)/jid;stage.mkdir()
    record={'job_id':jid,'relative_paths':[p.name],'files':[{'relative_path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size}]}
    journal=ti.stage_parent(ws)/(jid+'.json');journal.write_text(json.dumps(record))
    create_job(db,job_id=jid,kind='sd_import',trigger_type='manual',operation='trash_import',source_path=str(stage))
    cleanup=ti.cleanup_successful_trash_import(ws,jid,[])
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='completed',result_json=? WHERE id=?",(json.dumps({'trash_source_cleanup':cleanup}),jid))
    before=journal.read_bytes()
    import subprocess,sys
    code="""from pathlib import Path
import sys
from app.trash_import import protected_trash_paths
from app.database import initialize_database,database_connection
ws,db,journal=map(Path,sys.argv[1:])
initialize_database(db)
assert not protected_trash_paths(None,ws)
assert journal.is_file()
with database_connection(db) as c:
 assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 assert not c.execute('PRAGMA foreign_key_check').fetchall()
"""
    for _ in range(3):subprocess.run([sys.executable,'-c',code,str(ws),str(db),str(journal)],check=True,capture_output=True,text=True)
    assert journal.read_bytes()==before and p.read_bytes()==b'original'
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert not p.exists() and journal.read_bytes()==before


def test_localized_message_projection_keeps_original_data(tmp_path):
    from app.main import index
    from app.ui_i18n import I18N_UI_JS
    from tests.backend.test_rc3_mobile import node
    html=index();start=html.index('    function bk0511ImportLabel(');end=html.index('    function renderJob(',start)
    note='Der Ordnerimport ist vollständig geprüft. Ein echter ZFS-Snapshot und die Freigabe zum Formatieren werden erst mit der Host-Schnittstelle aktiviert.'
    script="""globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Import',readyState:'loading',documentElement:{dataset:{bkLocale:'en'}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
"""+I18N_UI_JS+html[start:end]+"\nconst input="+json.dumps({'progress_message':'Ordnerimport erfolgreich abgeschlossen. 18 Mediendateien wurden verifiziert.','result':{'note':note},'source_volume_label':'Mehrere Aufnahmegeräte','path':'2026/Test 2/< & original.JPG'},ensure_ascii=False)+""";
const original=JSON.stringify(input),projected=localizedTechnicalJob(input);
if(!projected.progress_message.startsWith('Import completed.')||!projected.result.note.startsWith('The folder import'))throw Error('German message');
if(JSON.stringify(input)!==original||input.path!==projected.path||input.source_volume_label!==projected.source_volume_label)throw Error('raw data changed');
window.BibliothekarI18n.setLocale('de');if(localizedTechnicalJob(input).result.note!==input.result.note)throw Error('German view');
"""
    node(tmp_path,script)


def test_trash_nested_cause_and_opaque_path_localization(tmp_path):
    from app.trash_ui import TRASH_HTML
    from app.ui_i18n import I18N_UI_JS
    from tests.backend.test_rc3_mobile import node
    start=TRASH_HTML.index('  const localError=');end=TRASH_HTML.index('  function updateControls',start)
    prefix="""globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Trash',readyState:'loading',documentElement:{dataset:{}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
"""
    node(tmp_path,prefix+I18N_UI_JS+TRASH_HTML[start:end]+"""
const raw='Papierkorb konnte nicht sicher geleert werden: Wiederherstellung läuft; der Papierkorb kann noch nicht geleert werden.';
if(localError(raw)!=='Could not empty trash safely: A restore is active or unresolved; trash cannot be emptied yet.')throw Error(localError(raw));
if(localError('Datei keiner Sicherung zuzuordnen; Wiederherstellung nicht möglich: Vertrauen')!=='File has no backup provenance; restoration is not possible: Vertrauen')throw Error('opaque filename changed');
window.BibliothekarI18n.setLocale('de');if(localError(raw)!==raw)throw Error('German raw error');
""")
