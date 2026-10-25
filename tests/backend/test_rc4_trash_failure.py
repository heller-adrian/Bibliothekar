"""Failed restore finalization: synthetic originals, independent retained copies."""
import hashlib,json
from pathlib import Path
import pytest
from app import main,trash_import as ti
from app.database import database_connection
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc4_nas_legacy import failed_restore


def test_legacy_failed_restore_safely_finishes_without_losing_copy(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    before=journal.read_bytes()
    state=main.api_trash_inventory()
    resolutions=state.get('restore_failures',[])
    assert any(r['job_id']==jid and r['status']=='ready' for r in resolutions)
    assert journal.read_bytes()==before  # GET does not finalize historical failures.
    response=main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})
    assert response['status']=='finalized'
    state=response['inventory']
    assert not state['deletion_blocked']
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert journal.exists()
    for item in data['files']:
        recovery=ti.stage_parent(ws)/jid/item['relative_path']
        assert hashlib.sha256(recovery.read_bytes()).hexdigest()==item['sha256']
    with database_connection(db) as c:
        row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        assert row['state']==row['stage']=='failed'
        assert row['error_message']=='Auf dieser SD-Karte wurden keine neuen Dateien gefunden. Alle Dateien wurden bereits erfolgreich gesichert.'
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()


def test_read_only_proof_requires_real_independent_complete_copies(fixture):
    from app.trash_failure import inspect_failure
    db,ws,jid,journal,data=failed_restore(fixture)
    before=snapshot(fixture[0],fixture[4]/'before.json')
    proof=inspect_failure(db,ws,jid)
    assert len(proof['files'])==2
    assert all(r['copy_identity']!=r['original_identity'] for r in proof['files'])
    after=snapshot(fixture[0],fixture[4]/'after.json')
    assert before['databases']==after['databases']
    assert json.loads(journal.read_text())==data


@pytest.mark.parametrize('conflict',['missing-copy','corrupt-copy','missing-original','corrupt-original','hardlink','symlink','incomplete-partition','partial-catalogue','partial-incoming','active','interrupted'])
def test_read_only_proof_rejects_uncertainty(fixture,conflict):
    from app.trash_failure import inspect_failure
    from app.trash import TrashError
    db,ws,jid,journal,data=failed_restore(fixture)
    rel=data['files'][0]['relative_path'];copy=ti.stage_parent(ws)/jid/rel;original=storage_paths(ws)['trash_root']/rel
    if conflict=='missing-copy':copy.unlink()
    if conflict=='corrupt-copy':copy.write_bytes(b'changed')
    if conflict=='missing-original':original.unlink()
    if conflict=='corrupt-original':original.write_bytes(b'changed')
    if conflict=='hardlink':
        import os
        copy.unlink();os.link(original,copy)
    if conflict=='symlink':copy.unlink();copy.symlink_to(original)
    if conflict=='incomplete-partition':data['files'].pop();journal.write_text(json.dumps(data))
    if conflict=='partial-incoming':(storage_paths(ws)['backup_root']/'.incoming'/jid).mkdir(parents=True)
    if conflict in ('active','interrupted'):
        with database_connection(db) as c:c.execute('UPDATE jobs SET state=? WHERE id=?',('copying' if conflict=='active' else 'interrupted',jid))
    if conflict=='partial-catalogue':
        with database_connection(db) as c:c.execute("INSERT INTO file_families(job_id,family_key) VALUES (?,?)",(jid,'partial'))
    raw=journal.read_bytes()
    with pytest.raises((TrashError,OSError)):inspect_failure(db,ws,jid)
    assert journal.read_bytes()==raw


def test_direct_finalization_is_durable_and_preserves_all_bytes(fixture):
    from app import trash_failure as tf
    from app.trash import TrashError
    db,ws,jid,journal,data=failed_restore(fixture)
    before=json.loads(journal.read_text())
    result=tf.finalize_failure(db,ws,jid);assert result['status']=='finalized'
    recorded=json.loads(journal.read_text());assert recorded[tf.KEY]['phase']=='committed'
    assert {k:v for k,v in recorded.items() if k!=tf.KEY}==before
    assert not ti.protected_trash_paths(None,ws)
    first=journal.read_bytes()
    assert tf.finalize_failure(db,ws,jid)==result
    assert journal.read_bytes()==first
    with pytest.raises(TrashError):ti.cleanup_successful_trash_import(ws,jid,data['files'])
    with pytest.raises(TrashError):ti.prepare_queued_trash_restore(db,fixture[3],ws,jid)
    assert ti.resume_safe_queued_trash_restores(db,ws)==0
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert tf.validate_finalized(None,ws,jid)
    for item in data['files']:
        assert hashlib.sha256((ti.stage_parent(ws)/jid/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==1
        row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        assert row['state']=='failed' and row['error_message']
        assert not c.execute('SELECT 1 FROM files WHERE job_id=?',(jid,)).fetchall()


@pytest.mark.parametrize('boundary',['journal_prepared','before_db_commit','db_committed','journal_committed'])
def test_sigkill_error_completion_and_three_independent_restarts(fixture,tmp_path,boundary):
    import subprocess,sys,time,signal,os
    from app import trash_failure as tf
    db,ws,jid,journal,data=failed_restore(fixture)
    with database_connection(db) as c:error=c.execute('SELECT error_message FROM jobs WHERE id=?',(jid,)).fetchone()[0]
    case=tmp_path/'failure-case.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'job_id':jid,'error':error}))
    marker=tmp_path/'checkpoint.json';worker=Path(__file__).parents[2]/'qa/rc4/trash_failure_worker.py'
    original={str(storage_paths(ws)['trash_root']/r['relative_path']):r['sha256'] for r in data['files']}
    command=[sys.executable,'-B',str(worker),str(case),boundary,str(marker)]
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+20
    while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not marker.exists():
        p.kill();out,err=p.communicate(timeout=5);pytest.fail('Checkpoint absent: '+out+err)
    p.kill();out,err=p.communicate(timeout=5);assert p.returncode==-signal.SIGKILL
    (tmp_path/'killed.log').write_text(out+err)
    receipt=json.loads(journal.read_text())[tf.KEY]
    expected_committed=boundary=='journal_committed'
    assert (receipt['phase']=='committed')==expected_committed
    assert bool(ti.protected_trash_paths(None,ws)) is (not expected_committed)
    snapshot(fixture[0],fixture[4]/'after-kill.json')
    results=[]
    for n in range(3):
        r=subprocess.run([sys.executable,'-B',str(worker),str(case),'none',str(marker)],capture_output=True,text=True,timeout=25)
        (tmp_path/f'restart{n}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
        value=json.loads(r.stdout);assert value['audit_count']==1;results.append(value)
        for name,sha in original.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha
        snapshot(fixture[0],fixture[4]/f'after-restart{n}.json')
    assert results[0]==results[1]==results[2]
    assert tf.finalize_failure(db,ws,jid)['status']=='finalized'


@pytest.mark.parametrize('change',['missing','corrupt','hardlink','foreign-original','world-accessible','job-requeued','db-receipt','journal-receipt'])
def test_closed_failure_never_acts_as_unchecked_deletion_permission(fixture,change):
    from app import trash_failure as tf
    from app.trash import TrashError
    import os
    db,ws,jid,journal,data=failed_restore(fixture);tf.finalize_failure(db,ws,jid)
    rel=data['files'][0]['relative_path'];copy=ti.stage_parent(ws)/jid/rel;original=storage_paths(ws)['trash_root']/rel
    if change=='missing':copy.unlink()
    if change=='corrupt':copy.write_bytes(b'changed')
    if change=='hardlink':os.link(copy,copy.with_name('alias'))
    if change=='foreign-original':
        raw=original.read_bytes();original.rename(original.with_suffix('.kept'));original.write_bytes(raw)
    if change=='world-accessible':copy.parent.chmod(0o755)
    if change=='job-requeued':
        with database_connection(db) as c:c.execute("UPDATE jobs SET state='queued' WHERE id=?",(jid,))
    if change=='db-receipt':
        with database_connection(db) as c:c.execute("UPDATE jobs SET result_json='{}' WHERE id=?",(jid,))
    if change=='journal-receipt':
        d=json.loads(journal.read_text());d[tf.KEY]['proof']['files']=[];journal.write_text(json.dumps(d))
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    before=original.read_bytes()
    from app.trash import empty_trash_filesystem
    with pytest.raises(TrashError):empty_trash_filesystem(ws)
    assert original.read_bytes()==before


@pytest.mark.parametrize('state',['queued','copying','verifying','interrupted'])
def test_active_or_unresolved_restore_blocks_all_deletes(fixture,state):
    from app.trash_selective import delete_selected_trash_files
    from app.trash import TrashError,empty_trash_filesystem
    db,ws,jid,journal,data=failed_restore(fixture)
    other=storage_paths(ws)['trash_root']/'unrelated.JPG';other.write_bytes(b'independent')
    with database_connection(db) as c:c.execute('UPDATE jobs SET state=? WHERE id=?',(state,jid))
    status=main.api_trash_inventory();assert status['deletion_blocked']
    assert status['restore_active'] is (state!='interrupted')
    if state == 'interrupted':
        assert main.api_empty_trash_selection({'relative_paths':['unrelated.JPG']})['deleted_file_count'] == 1
        assert not other.exists()
        for item in data['files']:
            with pytest.raises(TrashError):delete_selected_trash_files(fixture[3],ws,[item['relative_path']])
    else:
        with pytest.raises(main.HTTPException):main.api_empty_trash_selection({'relative_paths':['unrelated.JPG']})
        with pytest.raises(TrashError):delete_selected_trash_files(fixture[3],ws,['unrelated.JPG'])
    with pytest.raises(TrashError):empty_trash_filesystem(ws)
    if state != 'interrupted':assert other.read_bytes()==b'independent'
    for r in data['files']:assert hashlib.sha256((storage_paths(ws)['trash_root']/r['relative_path']).read_bytes()).hexdigest()==r['sha256']


@pytest.mark.parametrize('state',['original-missing','copy-missing','partial-staging','before-copy','mixed-known'])
def test_unclear_failure_has_explicit_action_but_no_unsafe_release(fixture,state):
    db,ws,jid,journal,data=failed_restore(fixture)
    rel=data['files'][0]['relative_path']
    if state=='original-missing':(storage_paths(ws)['trash_root']/rel).unlink()
    if state=='copy-missing':(ti.stage_parent(ws)/jid/rel).unlink()
    if state=='partial-staging':
        (ti.stage_parent(ws)/jid/rel).write_bytes(b'partial bytes')
    if state=='before-copy':
        import shutil
        shutil.rmtree(ti.stage_parent(ws)/jid)
        data['files']=[];data['status']='queued';journal.write_text(json.dumps(data))
    if state=='mixed-known':
        item=data['files'].pop();data['known_paths']=[item['relative_path']];journal.write_text(json.dumps(data))
    raw=journal.read_bytes();inventory=main.api_trash_inventory()
    assert inventory['deletion_blocked']
    item=next(r for r in inventory['restore_failures'] if r['job_id']==jid)
    assert item['status']=='blocked' and item['message']
    with pytest.raises(main.HTTPException) as error:main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})
    assert error.value.status_code==409
    assert journal.read_bytes()==raw
    assert ti.protected_trash_paths(None,ws)


def test_explicit_action_needs_confirmation_and_is_idempotent(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    before=journal.read_bytes()
    with pytest.raises(main.HTTPException) as error:main.api_finalize_trash_failure(jid,{})
    assert error.value.status_code==422 and journal.read_bytes()==before
    first=main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})
    raw=journal.read_bytes()
    assert first['status']=='finalized'
    assert main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})['status']=='finalized'
    assert journal.read_bytes()==raw
    with database_connection(db) as c:assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==1


def test_other_journals_keep_their_reservations(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    root=storage_paths(ws)['trash_root'];names=[]
    for item in data['files']:
        p=root/('other-'+item['relative_path']);p.write_bytes((root/item['relative_path']).read_bytes());names.append(p.name)
    second=ti.stage_trash_import(db,ws,names)['job_id'];path=ti.stage_parent(ws)/(second+'.json')
    d=json.loads(path.read_text());d.update(status='known_restored',known_paths=[],known_restored_count=0);path.write_text(json.dumps(d))
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='failed',stage='failed',error_message='other failure' WHERE id=?",(second,))
    (ti.stage_parent(ws)/second/names[0]).write_bytes(b'corrupt')
    response=main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})
    assert response['inventory']['deletion_blocked']
    assert ti.protected_trash_paths(None,ws)==set(names)
    with pytest.raises(main.HTTPException):main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert all((root/name).exists() for name in names+data['relative_paths'])


def test_failure_ui_disables_deletes_and_uses_only_confirmed_single_job_post(tmp_path):
    from app.trash_ui import TRASH_HTML
    from tests.backend.test_rc3_mobile import node
    start=TRASH_HTML.index('  function updateControls()');end=TRASH_HTML.index('  const esc=',start)
    controls=TRASH_HTML[start:end]
    start=TRASH_HTML.index('  function renderRestoreFailures(');end=TRASH_HTML.index('  function render(data)',start)
    render=TRASH_HTML[start:end]
    script=r'''
let locale='en',busy=false,lastInventory={deletion_blocked:true,restore_active:true},selectablePaths=['A.JPG'],selected=new Set(),selectMode=false;
const bilingual=(de,en)=>locale==='de'?de:en,localError=x=>x;
function element(){return {children:[],textContent:'',setAttribute(){},appendChild(n){this.children.push(n)},replaceChildren(){this.children=[]},addEventListener(k,f){this[k]=f},querySelectorAll(){return this.children.flatMap(c=>c.children||[]).filter(x=>x.type==='button')}}}
const list=element(),failureNotice=element(),restoreButton={},emptyButton={},selectButton={},selectAllButton={};
const document={createElement:()=>element(),querySelector:()=>({})};let calls=[],confirmed=0;
const window={BibliothekarI18n:{confirmAsync:async()=>{confirmed++;return true}}};
const status={textContent:''};const json=async(url,opts)=>{calls.push({url,opts});return {inventory:{deletion_blocked:false,restore_active:false}}};
function render(data){lastInventory=data;renderRestoreFailures({restore_failures:[{job_id:'J',status:'finalized',recovery_path:'<raw & path>'}]});updateControls()}
''' + controls + render + r'''
(async()=>{
renderRestoreFailures({restore_failures:[{job_id:'TRASH_IMPORT_TEST',status:'ready'}]});updateControls();
if(!emptyButton.disabled||!failureNotice.querySelectorAll('button')[0].disabled)throw Error('active deletion/action not disabled');
lastInventory.restore_active=false;updateControls();
if(!emptyButton.disabled)throw Error('full empty must remain blocked by reservations');
selected.add('A.JPG');updateControls();
if(emptyButton.disabled)throw Error('inactive restore must allow a selected request for server-side validation');
lastInventory.restore_active=true;updateControls();
if(!emptyButton.disabled)throw Error('active restore must block even a selected request');
selected.clear();lastInventory.restore_active=false;updateControls();
const button=failureNotice.querySelectorAll('button')[0];if(button.disabled||button.textContent!=='Safely cancel failed restore')throw Error('explicit action missing');
await button.click();
if(confirmed!==1||calls.length!==1||!calls[0].url.endsWith('/TRASH_IMPORT_TEST/finalize-failure'))throw Error('not one confirmed single job');
if(JSON.parse(calls[0].opts.body).confirmation!=='SAFE_ABORT_FAILED_RESTORE')throw Error('confirmation missing');
if(emptyButton.disabled||!failureNotice.children[0].children[0].textContent.includes('<raw & path>'))throw Error('completion or text rendering missing');
locale='de';renderRestoreFailures({restore_failures:[{job_id:'J',status:'blocked',message:'A.JPG'}]});
if(failureNotice.querySelectorAll('button')[0].textContent!=='Fehlgeschlagene Wiederherstellung sicher abbrechen')throw Error('German action missing');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    node(tmp_path,script)


@pytest.mark.parametrize('marker',[None,[],{},'invalid'])
def test_malformed_receipt_never_releases_or_gets_silently_replaced(fixture,marker):
    from app import trash_failure as tf
    db,ws,jid,journal,data=failed_restore(fixture)
    data[tf.KEY]=marker;journal.write_text(json.dumps(data));raw=journal.read_bytes()
    inventory=main.api_trash_inventory();assert inventory['deletion_blocked']
    assert any(i['status']=='blocked' and i['paths']==data['relative_paths'] for i in inventory['restore_failures'])
    with pytest.raises(main.HTTPException) as error:main.api_finalize_trash_failure(jid,{'confirmation':'SAFE_ABORT_FAILED_RESTORE'})
    assert error.value.status_code==409 and journal.read_bytes()==raw
