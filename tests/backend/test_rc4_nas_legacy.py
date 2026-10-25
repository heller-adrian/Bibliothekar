"""Only synthetic reproductions of the two diagnosed NAS legacy states."""
import hashlib,json,shutil
from pathlib import Path
import pytest
from app import main,trash_import as ti,event_structure_changes as es
from app.database import create_job,database_connection
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc1_package_a import archived_change


def failed_restore(fixture):
    case,ws,reg,dbs,ev=fixture;db=dbs[0];root=storage_paths(ws)['trash_root']
    for ext in ['JPG','RAF']:(root/('20260722_101404_Fuji-X-E5.'+ext)).write_bytes(('original '+ext).encode())
    staged=ti.stage_trash_import(db,ws,[p.name for p in root.iterdir()]);jid=staged['job_id']
    journal=ti.stage_parent(ws)/(jid+'.json');data=json.loads(journal.read_text())
    data.update(status='known_restored',known_paths=[],known_restored_count=0)
    journal.write_text(json.dumps(data))
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='failed',stage='failed',error_message=? WHERE id=?",('Auf dieser SD-Karte wurden keine neuen Dateien gefunden. Alle Dateien wurden bereits erfolgreich gesichert.',jid))
    return db,ws,jid,journal,data


def historical_rename(tmp_path,monkeypatch):
    # Execute the actual two manual workflows using the historical title bug.
    with monkeypatch.context() as old:
        old.setattr(es,'_renamed_display_name',lambda event,new_folder:str(event['name']))
        db,ws,archive,root,change,prepared=archived_change(tmp_path)
        es.verify_archived_structure_change(db,archive,ws,change['id'])
        root=root.rename(root.with_name('07-23 - Final'))
        es.scan_event_inventory(db,archive,'j','e',root_kind='camera_archive',persist=True,fast_refresh=False)
        second=es.detect_event_structure_change(db,'e')
        prepared=es.prepare_archived_structure_change(db,ws,second['id'],input_path='Alle')
        (root/'event.json').write_bytes(Path(prepared['prepared_event_json_path']).read_bytes())
        es.verify_archived_structure_change(db,archive,ws,second['id'])
    with database_connection(db) as c:event=dict(c.execute("SELECT * FROM events WHERE id='e'").fetchone())
    return db,ws,archive,root,[change['id'],second['id']],event


def test_reproduce_failed_restore_still_blocks_entire_trash(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    before=snapshot(fixture[0],fixture[4]/'before.json')
    with pytest.raises(main.HTTPException) as error:main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert error.value.status_code==409 and 'ungeklärt' in error.value.detail and 'Aufträge prüfen' in error.value.detail
    after=snapshot(fixture[0],fixture[4]/'after.json')
    assert after['databases']==before['databases']
    for item in data['files']:
        p=storage_paths(ws)['trash_root']/item['relative_path']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    assert json.loads(journal.read_text())==data


def test_reproduce_two_completed_renames_keep_old_title(tmp_path,monkeypatch):
    db,ws,archive,root,ids,event=historical_rename(tmp_path,monkeypatch)
    doc=json.loads((root/'event.json').read_text());digest=hashlib.sha256((root/'event.json').read_bytes()).hexdigest()
    assert event['name']==doc['event']['name']=='Trip'
    assert event['folder_name']==doc['event']['folder_name']=='07-23 - Final'
    with database_connection(db) as c:
        rows=[dict(c.execute('SELECT * FROM event_structure_changes WHERE id=?',(i,)).fetchone()) for i in ids]
    assert all(r['status']=='completed' for r in rows)
    assert json.loads(rows[-1]['detected_json'])['prepared_event_json_sha256']==digest


def test_historical_title_can_use_existing_manual_archive_workflow(tmp_path,monkeypatch):
    """No new product mutation path: explicit normal editor change, then verify."""
    from app.event_change_request import propose_event_change
    from app.event_change_apply import confirm_event_change,verify_event_change,finish_event_change,EventChangeApplyError
    from app.archive_staging import required_event_document_for_request
    from app.workspace_layout import shared_work_root
    from app.archive_staging import staging_directory_name
    from tests.backend.test_0271_archive_assistant import _preview
    db,ws,archive,root,ids,event=historical_rename(tmp_path,monkeypatch)
    with database_connection(db) as c:
        family=c.execute('SELECT family_id FROM files WHERE job_id=?',(event['job_id'],)).fetchone()[0]
        old=[dict(c.execute('SELECT * FROM event_structure_changes WHERE id=?',(i,)).fetchone()) for i in ids]
        originals=[tuple(r) for r in c.execute('SELECT id,family_id,job_id,size_bytes,sha256_original,sha256_current,current_relative_path,current_root_kind FROM files ORDER BY id')]
        families=[tuple(r) for r in c.execute('SELECT id,job_id,family_key FROM file_families ORDER BY id')]
    original=(root/'Alle/A.JPG').read_bytes();old_document=(root/'event.json').read_bytes()
    preview=_preview(root.name,family,None)
    preview.update(start_date=event['start_datetime'][:10],end_date=event['end_datetime'][:10],event_name='Final')
    proposed=propose_event_change(db,event['job_id'],'e',preview,event_name='Final',archive_root=archive,workspace_path=ws)
    change=proposed['change_request_id']
    confirm_event_change(db,change,archive,ws)
    assert (root/'event.json').read_bytes()==old_document
    assert not verify_event_change(db,change,archive,ws)['complete']
    with pytest.raises(EventChangeApplyError):finish_event_change(db,change,archive,ws)
    with database_connection(db) as c:assert c.execute("SELECT name FROM events WHERE id='e'").fetchone()[0]=='Trip'
    spec=required_event_document_for_request(db,change);assert spec
    staged=shared_work_root(ws)/staging_directory_name(shared_work_root(ws))/spec['target_relative_path']
    prepared=staged.read_bytes();doc=json.loads(prepared)
    assert doc['event']['name']=='Final' and doc['event']['id']=='e'
    # This is the explicit manual archive replacement; the application never writes it.
    (root/'event.json').write_bytes(prepared)
    assert finish_event_change(db,change,archive,ws)['status']=='archiviert'
    with database_connection(db) as c:
        row=c.execute("SELECT * FROM events WHERE id='e'").fetchone()
        assert row['name']=='Final' and row['folder_name']==root.name
        assert old==[dict(c.execute('SELECT * FROM event_structure_changes WHERE id=?',(i,)).fetchone()) for i in ids]
        assert originals==[tuple(r) for r in c.execute('SELECT id,family_id,job_id,size_bytes,sha256_original,sha256_current,current_relative_path,current_root_kind FROM files ORDER BY id')]
        assert families==[tuple(r) for r in c.execute('SELECT id,job_id,family_key FROM file_families ORDER BY id')]
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert (root/'Alle/A.JPG').read_bytes()==original
    from app.database import list_job_events
    from app.archive_transfer import list_archive_candidates
    assert next(e for e in list_job_events(db,'j') if e['id']=='e')['name']=='Final'
    candidates=list_archive_candidates(db,archive,observe_current=True)['candidates']
    assert any(e['event_id']=='e' and e['name']=='Final' for e in candidates)


def manual_title_request(tmp_path,monkeypatch):
    from app.event_change_request import propose_event_change
    from app.event_change_apply import confirm_event_change
    from app.archive_staging import required_event_document_for_request,staging_directory_name
    from app.workspace_layout import shared_work_root
    from tests.backend.test_0271_archive_assistant import _preview
    db,ws,archive,root,ids,event=historical_rename(tmp_path,monkeypatch)
    with database_connection(db) as c:family=c.execute("SELECT family_id FROM files WHERE job_id='j'").fetchone()[0]
    preview=_preview(root.name,family,None);preview.update(start_date=event['start_datetime'][:10],end_date=event['end_datetime'][:10],event_name='Final')
    cr=propose_event_change(db,'j','e',preview,event_name='Final',archive_root=archive,workspace_path=ws)['change_request_id']
    confirm_event_change(db,cr,archive,ws)
    spec=required_event_document_for_request(db,cr)
    staged=shared_work_root(ws)/staging_directory_name(shared_work_root(ws))/spec['target_relative_path']
    return db,ws,archive,root,cr,staged


@pytest.mark.parametrize('conflict',['old-document','wrong-id','wrong-title','changed-photo','missing-document'])
def test_existing_manual_title_rejects_unverified_state(tmp_path,monkeypatch,conflict):
    from app.event_change_apply import finish_event_change,EventChangeApplyError
    db,ws,archive,root,cr,staged=manual_title_request(tmp_path,monkeypatch)
    target=root/'event.json';original=(root/'Alle/A.JPG').read_bytes()
    if conflict=='missing-document':target.unlink()
    elif conflict!='old-document':
        document=json.loads(staged.read_text())
        if conflict=='wrong-id':document['event']['id']='foreign'
        elif conflict=='wrong-title':document['event']['name']='foreign'
        target.write_text(json.dumps(document))
        if conflict=='changed-photo':(root/'Alle/A.JPG').write_bytes(b'foreign bytes')
    before=target.read_bytes() if target.exists() else None
    with pytest.raises(EventChangeApplyError):finish_event_change(db,cr,archive,ws)
    assert (target.read_bytes() if target.exists() else None)==before
    with database_connection(db) as c:
        assert c.execute("SELECT name FROM events WHERE id='e'").fetchone()[0]=='Trip'
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    if conflict!='changed-photo':assert (root/'Alle/A.JPG').read_bytes()==original


@pytest.mark.parametrize('state',['failed','interrupted','copying','completed'])
def test_unresolved_restore_never_released_from_job_status_alone(fixture,state):
    db,ws,jid,journal,data=failed_restore(fixture)
    with database_connection(db) as c:c.execute('UPDATE jobs SET state=? WHERE id=?',(state,jid))
    raw=journal.read_bytes()
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    assert ti.resume_safe_queued_trash_restores(db,ws)==(1 if state=='interrupted' else 0)
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    assert journal.read_bytes()==raw
    for item in data['files']:
        assert hashlib.sha256((storage_paths(ws)['trash_root']/item['relative_path']).read_bytes()).hexdigest()==item['sha256']


def test_missing_legacy_startup_guard_preserves_existing_files(tmp_path):
    from app.safe_transfer import reconcile_migrated_file,SafeTransferError
    source=tmp_path/'old/A.JPG';dest=tmp_path/'new/A.JPG';raw=b'original'
    with pytest.raises(SafeTransferError,match='Quelle und Ziel fehlen'):
        reconcile_migrated_file(source,dest,expected_size=len(raw),expected_sha256=hashlib.sha256(raw).hexdigest())
    assert not source.exists() and not dest.exists()
    dest.parent.mkdir();dest.write_bytes(raw)
    assert reconcile_migrated_file(source,dest,expected_size=len(raw),expected_sha256=hashlib.sha256(raw).hexdigest())['status']=='already_migrated'
    assert dest.read_bytes()==raw


@pytest.mark.parametrize('boundary',['before-commit','after-commit'])
def test_existing_title_workflow_sigkill_and_three_new_processes(tmp_path,monkeypatch,boundary):
    import subprocess,sys,time,signal
    db,ws,archive,root,cr,staged=manual_title_request(tmp_path,monkeypatch)
    (root/'event.json').write_bytes(staged.read_bytes());original=(root/'Alle/A.JPG').read_bytes()
    case=tmp_path/'title-case.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'archive':str(archive),'change':cr}))
    worker=Path(__file__).parents[2]/'qa/rc4/legacy_title_worker.py';marker=tmp_path/'checkpoint.json'
    command=[sys.executable,'-B',str(worker),str(case),boundary,str(marker)]
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+20
    while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not marker.exists():
        p.kill();stdout,stderr=p.communicate(timeout=5);pytest.fail('Checkpoint absent: '+stdout+stderr)
    p.kill();stdout,stderr=p.communicate(timeout=5);assert p.returncode==-signal.SIGKILL
    (tmp_path/'killed.log').write_text(stdout+stderr)
    snapshot(tmp_path,tmp_path.parent/(tmp_path.name+'-killed.json'))
    with database_connection(db) as c:
        assert c.execute("SELECT name FROM events WHERE id='e'").fetchone()[0]==('Trip' if boundary=='before-commit' else 'Final')
    values=[]
    for n in range(3):
        r=subprocess.run([sys.executable,'-B',str(worker),str(case),'none',str(marker)],capture_output=True,text=True,timeout=25)
        (tmp_path/f'restart{n}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
        values.append(json.loads(r.stdout));assert (root/'Alle/A.JPG').read_bytes()==original
        snapshot(tmp_path,tmp_path.parent/(tmp_path.name+f'-restart{n}.json'))
    assert values[0]==values[1]==values[2]


def test_unresolved_notice_is_localized_without_hiding_the_cause(tmp_path):
    from app.ui_i18n import I18N_UI_JS
    from app.trash_ui import TRASH_HTML
    from tests.backend.test_rc3_mobile import node
    start=TRASH_HTML.index('  const localError=');end=TRASH_HTML.index('  function updateControls',start)
    prefix="""globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Trash',readyState:'loading',documentElement:{dataset:{}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
"""
    raw='Papierkorb konnte nicht sicher geleert werden: Eine Wiederherstellung läuft oder ist ungeklärt. Bitte fehlgeschlagene oder unterbrochene Aufträge prüfen; der Papierkorb bleibt gesperrt.'
    node(tmp_path,prefix+I18N_UI_JS+TRASH_HTML[start:end]+'\nconst raw='+json.dumps(raw)+";\n"+"""
if(localError(raw)!=='Could not empty trash safely: A restore is active or unresolved. Please review failed or interrupted tasks; trash remains protected.')throw Error(localError(raw));
window.BibliothekarI18n.setLocale('de');if(localError(raw)!==raw)throw Error('German cause lost');
""")
