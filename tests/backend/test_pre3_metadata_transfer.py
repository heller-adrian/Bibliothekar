"""Completed General correction -> proven import; no filename/hash searching."""
from pathlib import Path
import hashlib,json,os,sqlite3,subprocess,sys,io,tarfile,signal
import pytest
from PIL import Image
from app import main,metadata_correction as mc,root_operations as ro
from app import metadata_abort_recovery as recovery
from app.database import database_connection,get_job
from app.library_context import resolve_library_context
from tests.backend.test_f14_root_operations import fixture

NAME='20260719_175150_Fuji-X-E5.JPG'
STAMP='2026-07-19T17:51:50+02:00'


def completed(fixture,monkeypatch,*,stale=False):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/NAME;Image.new('RGB',(12,12),'green').save(source)
    before=source.read_bytes();real=ro._write
    def write(path,data):
        if stale and path.name.startswith('finished-') and data.get('reservation',{}).get('kind')=='metadata':
            raise OSError('injected F14 completion I/O failure after completed SQL commit')
        return real(path,data)
    monkeypatch.setattr(ro,'_write',write)
    try:
        mc.execute_metadata_correction(db,area='general',relative_path=NAME,proposed_datetime=STAMP,workspace_root=ws,library_id='main')
    except OSError:
        assert stale
    finally:monkeypatch.setattr(ro,'_write',real)
    task=mc.list_metadata_corrections(db,include_completed=True)[0]
    assert task['status']=='completed' and task['source_sha256']==hashlib.sha256(before).hexdigest()
    assert task['output_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    return case,ws,reg,db,source,task


def transfer(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    context=resolve_library_context(reg,'main')
    monkeypatch.setattr(main,'current_library_context',lambda:context)
    monkeypatch.setattr(main,'LOG_PATH',case/'logs')
    monkeypatch.setenv('KAMERA_LOG_DIR',str(case/'logs'))
    monkeypatch.setattr(main,'load_settings',lambda:{'storage':{'safety_reserve_gib':0,'processing_buffer_percent':0}})
    response=main.api_reintegrate_general_metadata.__wrapped__({'items':[{'relative_path':NAME}]})
    queued=main.claim_next_job(db,operation='metadata_general_import');assert queued and queued['id']==response['job']['id']
    main.process_claimed_job(queued,library_context=context)
    job=get_job(db,queued['id']);assert job['state']=='completed',job
    assert not (mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']/NAME).exists()
    return job


def historical(fixture,monkeypatch,*,move=True,prior_receipt=False,release="v1.0.0-pre.2"):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/NAME;Image.new('RGB',(12,12),'blue').save(source)
    for _ in range(2):
        with ro.mutate(ws):pass
    old=case/'published-pre2';old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',release,'app']))) as t:t.extractall(old,filter='data')
    code=r"""
import os,sys,signal,json
from pathlib import Path
from app import main,metadata_correction as m,root_operations as ro
from app.library_context import resolve_library_context
from app.database import get_job
ws,reg,db,case=map(Path,sys.argv[1:5]);phase=sys.argv[5]
context=resolve_library_context(reg,'main')
main.WORKSPACE_PATH=ws;main.DATABASE_FILE=db;main.REGISTRY_DATABASE_FILE=reg;main.LOG_PATH=case/'logs'
main.current_library_context=lambda:context
main.load_settings=lambda:{'storage':{'safety_reserve_gib':0,'processing_buffer_percent':0}}
if phase=='correct':
 real=ro._write
 def write(path,data):
  if path.name.startswith('finished-') and data.get('reservation',{}).get('kind')=='metadata':os.kill(os.getpid(),signal.SIGKILL)
  real(path,data)
 ro._write=write
 m.execute_metadata_correction(db,area='general',relative_path='20260719_175150_Fuji-X-E5.JPG',proposed_datetime='2026-07-19T17:51:50+02:00',workspace_root=ws,library_id='main')
else:
 response=main.api_reintegrate_general_metadata.__wrapped__({'items':[{'relative_path':'20260719_175150_Fuji-X-E5.JPG'}]})
 job=main.claim_next_job(db,operation='metadata_general_import');assert job
 main.process_claimed_job(job,library_context=context)
 final=get_job(db,job['id']);assert final['state']=='completed',final
 print(json.dumps(final))
"""
    env=dict(os.environ,PYTHONPATH=str(old),PYTHONDONTWRITEBYTECODE='1',KAMERA_LOG_DIR=str(case/'logs'))
    args=[sys.executable,'-c',code,str(ws),str(reg),str(db),str(case)]
    process=subprocess.run([*args,'correct'],env=env,cwd=old,capture_output=True,text=True,timeout=30)
    assert process.returncode==-signal.SIGKILL,process.stdout+process.stderr
    record=ro._read(next(ro._control_location(ws).glob('operation-*.json')))
    assert record['generation']==[2,0]
    assert not list(ro._control_location(ws).glob('metadata-outcome-*.json'))
    with database_connection(db) as c:task=dict(c.execute('SELECT * FROM metadata_corrections').fetchone())
    assert task['status']=='completed'
    if prior_receipt:
        with pytest.raises(RuntimeError):
            with ro.reserve(ws,library_id=record['library'],database=db,paths=list(record['bindings']),
                            kind='metadata',ids=record['ids'],expected_generation=tuple(record['generation']),
                            shared=False,_recovery_record=record) as active:
                recovery._finish(active,ro._registered(db))
                raise RuntimeError('simulated interruption before F14 acknowledgement')
    job=None
    if move:
        process=subprocess.run([*args,'transfer'],env=env,cwd=old,capture_output=True,text=True,timeout=45)
        assert process.returncode==0,process.stdout+process.stderr
        job=json.loads(process.stdout.splitlines()[-1]);assert not source.exists()
    monkeypatch.setenv('KAMERA_LOG_DIR',str(case/'logs'))
    monkeypatch.setattr(main,'LOG_PATH',case/'logs')
    return case,ws,reg,db,source,task,record,job


def test_pre2_completed_missing_source_after_real_transfer_reproduces_block(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch)
    parent=ro._control_location(ws)
    assert recovery.recover_general_outcomes(ws,reg)[0]['reservation_id']==record['reservation_id']
    assert not list(parent.glob('operation-*.json'))
    receipt=ro._read(next(parent.glob('metadata-outcome-*.json')))
    assert receipt['source']['transfer']['job']['id']==job['id']
    assert receipt['reservation']==record and receipt['source']['sha256']==task['output_sha256']
    with database_connection(db) as c:assert dict(c.execute('SELECT * FROM metadata_corrections').fetchone())==task


def receipt(ws):return ro._read(next(ro._control_location(ws).glob('metadata-outcome-*.json')))


def test_new_success_receipt_then_transfer_and_two_restarts(fixture,monkeypatch):
    case,ws,reg,db,source,task=completed(fixture,monkeypatch)
    parent=ro._control_location(ws)
    assert not list(parent.glob('operation-*.json')) and receipt(ws)['disposition']=='completed'
    old=receipt(ws)
    for _ in range(1):
        assert recovery.recover_general_outcomes(ws,reg)==[]
    transfer(fixture,monkeypatch)
    seen=[];monkeypatch.setattr(main,'_start_runtime_workers',lambda:seen.append(True))
    for _ in range(2):
        main.startup_database();assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert len(seen)==2 and receipt(ws)==old and not source.exists()


def test_transfer_closes_verified_predecessor_before_source_cleanup(fixture,monkeypatch):
    case,ws,reg,db,source,task=completed(fixture,monkeypatch,stale=True)
    record=ro._read(next(ro._control_location(ws).glob('operation-*.json')))
    transfer(fixture,monkeypatch)
    assert receipt(ws)['reservation']==record and not list(ro._control_location(ws).glob('operation-*.json'))
    assert recovery.recover_general_outcomes(ws,reg)==[]


@pytest.mark.parametrize('fault',['target_missing','target_bytes','target_symlink','target_inode','manifest_missing','manifest_source',
 'manifest_hash','journal_inode','journal_root','job_state','catalogue_path','catalogue_hash','origin_missing','origin_hash','extra_job','protocol_incomplete'])
def test_historical_transfer_counterevidence_preserves_operation(fixture,monkeypatch,fault):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch)
    protocol=case/'logs/backups'/job['id'];journal=json.loads((protocol/'move-journal.json').read_text())
    target=Path(journal['root'])/journal['files'][0]['destination_relative_path'];original=target.read_bytes()
    if fault=='target_missing':target.unlink()
    if fault=='target_bytes':target.write_bytes(b'foreign bytes')
    if fault=='target_inode':
        other=target.with_name('original-preserved.JPG');target.rename(other);target.write_bytes(original)
    if fault=='target_symlink':
        other=target.with_name('original-preserved.JPG');target.rename(other);target.symlink_to(other)
    if fault=='manifest_missing':(protocol/'manifest.json').unlink()
    if fault.startswith('manifest_') and fault!='manifest_missing':
        p=protocol/'manifest.json';v=json.loads(p.read_text())
        if fault=='manifest_source':v['source_path']='/somewhere/else'
        if fault=='manifest_hash':v['files'][0]['sha256']='f'*64
        p.write_text(json.dumps(v))
    if fault.startswith('journal_'):
        if fault=='journal_inode':journal['files'][0]['inode']=[0,0]
        if fault=='journal_root':journal['root']='/somewhere/else'
        (protocol/'move-journal.json').write_text(json.dumps(journal))
    if fault in ('job_state','catalogue_path','catalogue_hash','extra_job'):
        with sqlite3.connect(db) as c:
            c.row_factory=sqlite3.Row
            if fault=='job_state':c.execute("UPDATE jobs SET state='interrupted' WHERE id=?",(job['id'],))
            if fault=='catalogue_path':c.execute("UPDATE files SET current_relative_path='foreign/location.JPG' WHERE job_id=?",(job['id'],))
            if fault=='catalogue_hash':c.execute("UPDATE files SET sha256_current=? WHERE job_id=?",('f'*64,job['id']))
            if fault=='extra_job':
                row=dict(c.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone());row['id']='GENERAL_IMPORT_foreign'
                c.execute('INSERT INTO jobs ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
    if fault.startswith('origin_'):
        with sqlite3.connect(reg) as c:
            if fault=='origin_missing':c.execute('DELETE FROM source_family_members')
            if fault=='origin_hash':c.execute("UPDATE source_media SET sha256=?",('f'*64,))
    if fault=='protocol_incomplete':
        p=protocol/'status.json';v=json.loads(p.read_text());v['state']='running';p.write_text(json.dumps(v))
    with pytest.raises(Exception):recovery.recover_general_outcomes(ws,reg)
    assert ro._read(next(ro._control_location(ws).glob('operation-*.json')))==record
    assert not list(ro._control_location(ws).glob('metadata-outcome-*.json'))
    with database_connection(db) as c:assert dict(c.execute('SELECT * FROM metadata_corrections').fetchone())==task
    if target.exists() and fault not in ('target_bytes','target_symlink'):assert target.read_bytes()==original


def test_missing_general_without_transfer_never_uses_matching_copy(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,_=historical(fixture,monkeypatch,move=False)
    payload=source.read_bytes();source.unlink()
    for directory in (case/'archive-second',case/'workspace/Arbeitsbereiche/second'):
        (directory/NAME).write_bytes(payload)
    with pytest.raises(ro.RootOperationError,match='admission_missing_or_ambiguous'):recovery.recover_general_outcomes(ws,reg)
    assert list(ro._control_location(ws).glob('operation-*.json'))


@pytest.mark.parametrize('intent',[True,False])
def test_historical_completed_source_still_present_has_durable_outcome(fixture,monkeypatch,intent):
    case,ws,reg,db,source,task,record,_=historical(fixture,monkeypatch,move=False)
    if not intent:
        for p in ro._control_location(ws).glob('metadata-intent-*.json'):p.unlink()
    recovery.recover_general_outcomes(ws,reg)
    assert receipt(ws)['reservation']==record and receipt(ws)['disposition']=='completed'
    assert source.is_file()


def test_three_open_operations_are_classified_without_blanket_release(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch)
    # Construct a historical concurrent state directly in the isolated fixture.
    # Current admission must NOT be used to create new writes past an orphan.
    import uuid
    from app.storage_bootstrap import key_for
    parent=ro._control_location(ws)
    for kind in ('trash','import'):
        extra=dict(record,kind=kind,reservation_id=uuid.uuid4().hex,ids={'function':'unknown_domain','job_id':kind})
        ro._write(parent/('operation-'+key_for(extra)+'.json'),extra)
    from app.metadata_recovery_status import inspect
    before=inspect(ws,reg)
    assert len(before['operations'])==3 and sum(x['scope']=='single_file_requires_qualification' for x in before['operations'])==1
    preserved={p:p.read_bytes() for p in parent.glob('operation-*.json')}
    seen=[];monkeypatch.setattr(main,'_start_runtime_workers',lambda:seen.append(True))
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None and seen==[]
    assert main.api_storage_health()['state']=='READY'
    from app.operation_health import inspect as operation_status
    assert not operation_status(ws)['writes_allowed']
    assert preserved=={p:p.read_bytes() for p in parent.glob('operation-*.json')}
    with pytest.raises(mc.MetadataCorrectionError):recovery.settle_before_transfer(ws,reg,logs=case/'logs')


def test_general_handoff_lock_precedes_new_metadata_reservation(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture
    from app.metadata_general_handoff import transition
    from app.metadata_swap_recovery import metadata_write_guard
    import threading
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/NAME;Image.new('RGB',(12,12),'blue').save(source)
    failures=[]
    def other_thread():
        try:mc.execute_metadata_correction(dbs[0],area='general',relative_path=NAME,proposed_datetime=STAMP,workspace_root=ws,library_id='main')
        except mc.MetadataCorrectionError as error:failures.append(str(error))
    with transition(ws):
        t=threading.Thread(target=other_thread);t.start();t.join(5);assert not t.is_alive()
        assert failures and not list(ro._control_location(ws).glob('operation-*.json'))
    with database_connection(dbs[0]) as c:assert c.execute('SELECT COUNT(*) FROM metadata_corrections').fetchone()[0]==0


def test_cleanup_with_unknown_predecessor_preserves_general_and_stage(fixture,monkeypatch):
    case,ws,reg,db,source,task=completed(fixture,monkeypatch)
    from app.metadata_general_handoff import cleanup
    stage=source.parent.parent/'.general-import/J';stage.mkdir(parents=True);copy=stage/NAME;copy.write_bytes(source.read_bytes())
    with pytest.raises(RuntimeError):
        with ro.reserve(ws,library_id='main',database=db,kind='metadata',ids={'function':'unknown_domain'}):raise RuntimeError('interrupted')
    with ro.reserve(ws,library_id='main',database=db,kind='import',ids={'job_id':'J'},shared=True):
        result=cleanup(ws,stage,[{'relative_path':NAME,'size_bytes':source.stat().st_size,'sha256':task['output_sha256']}],'J')
    assert result['removed_file_count']==0 and 'unresolved_predecessor' in result['errors'][0] and source.is_file() and copy.is_file()


def test_successful_outcome_sigkill_is_idempotently_recovered(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture;db=dbs[0]
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/NAME;Image.new('RGB',(12,12),'yellow').save(source)
    code=r'''
import os,sys,signal
from pathlib import Path
from app import metadata_correction as m,root_operations as ro
ws,db=map(Path,sys.argv[1:3]);real=ro._write
def write(path,data):
 real(path,data)
 if path.name.startswith('metadata-outcome-'):os.kill(os.getpid(),signal.SIGKILL)
ro._write=write
m.execute_metadata_correction(db,area='general',relative_path='20260719_175150_Fuji-X-E5.JPG',proposed_datetime='2026-07-19T17:51:50+02:00',workspace_root=ws,library_id='main')
'''
    process=subprocess.run([sys.executable,'-c',code,str(ws),str(db)],capture_output=True,text=True,timeout=30)
    assert process.returncode==-signal.SIGKILL,process.stderr
    old=receipt(ws);record=ro._read(next(ro._control_location(ws).glob('operation-*.json')))
    assert old['disposition']=='completed'
    recovery.recover_general_outcomes(ws,reg)
    assert receipt(ws)==old and old['reservation']==record
    assert not list(ro._control_location(ws).glob('operation-*.json'))


def test_later_location_receipt_preserves_original_completed_outcome(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch,prior_receipt=True)
    previous=receipt(ws)
    recovery.recover_general_outcomes(ws,reg)
    assert receipt(ws)==previous
    continuation=ro._read(next(ro._control_location(ws).glob('metadata-location-*.json')))
    assert continuation['previous_outcome']==previous
    assert continuation['outcome']['source']['transfer']['job']['id']==job['id']
    assert continuation['outcome']['reservation']==record
    assert recovery.recover_general_outcomes(ws,reg)==[]


def test_same_name_elsewhere_does_not_change_documented_destination(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch)
    other=case/'workspace/Arbeitsbereiche/second'/NAME;other.write_bytes(b'an unrelated photograph')
    recovery.recover_general_outcomes(ws,reg)
    assert receipt(ws)['source']['path']!=str(other) and other.read_bytes()==b'an unrelated photograph'


def test_diagnostic_script_opens_only_snapshot_sqlite_and_preserves_sources(fixture,monkeypatch):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch)
    watched=[p for root in (db,reg) for p in (root,Path(str(root)+'-wal'),Path(str(root)+'-shm')) if p.is_file()]
    before={str(p):p.read_bytes() for p in watched}
    result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[2]/'qa/pre3/read_only_diagnosis.py')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    assert value['errors']==[] and value['authorization'] is False and len(value['operations'])==1
    assert value['operations'][0]['record']==record
    assert value['general_imports'][0]['candidate_destination_files'][0]['sha256']==task['output_sha256']
    assert {str(p):p.read_bytes() for p in watched}==before


@pytest.mark.parametrize('fault',['none','journal_inode','manifest_hash','job_time'])
def test_actual_rc14_timestamp_admission_requires_complete_legacy_chain(fixture,monkeypatch,fault):
    case,ws,reg,db,source,task,record,job=historical(fixture,monkeypatch,release='v1.0.0-rc.14')
    assert job['id'].startswith('GENERAL_IMPORT_') and not list(ro._control_location(ws).glob('metadata-intent-*.json'))
    protocol=case/'logs/backups'/job['id']
    if fault in ('journal_inode','manifest_hash'):
        p=protocol/('move-journal.json' if fault=='journal_inode' else 'manifest.json');v=json.loads(p.read_text())
        if fault=='journal_inode':v['files'][0]['inode']=[0,0]
        else:v['files'][0]['sha256']='f'*64
        p.write_text(json.dumps(v))
    if fault=='job_time':
        with sqlite3.connect(db) as c:c.execute('UPDATE jobs SET created_at=? WHERE id=?',('2000-01-01T00:00:00+01:00',job['id']))
    if fault=='none':
        recovery.recover_general_outcomes(ws,reg)
        assert receipt(ws)['source']['transfer']['admission_kind']=='legacy_verified_copy_chain'
        assert receipt(ws)['reservation']==record
    else:
        with pytest.raises(ro.RootOperationError):recovery.recover_general_outcomes(ws,reg)
        assert ro._read(next(ro._control_location(ws).glob('operation-*.json')))==record
