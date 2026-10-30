"""General-metadata failure outcome: exact F14 lease, original bytes and history.

Synthetic RAW bytes stand in for a refused DNG write. This is NOT a real DNG
1.7 media acceptance test. Published pre.1 code reproduces the historical lease.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import io

import pytest

from app import metadata_correction as mc,metadata_abort_recovery as recovery,root_operations as ro
from app.database import database_connection
from app.metadata_swap_recovery import recover_metadata_swaps
from tests.backend.test_f14_root_operations import fixture

STAMP='2024-06-23T10:20:21'
ERROR='ExifTool konnte die Metadaten nicht schreiben: Error: [minor] DNG Version 1.7.0.0 not yet tested'


def prepare(fixture):
    case,ws,reg,dbs,ev=fixture
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/'_DSC7386.dng';source.write_bytes(b'synthetic camera bytes; NOT a real DNG')
    return case,ws,reg,dbs[0],source


def execute(db,ws,source):
    return mc.execute_metadata_correction(db,area='general',relative_path=source.name,
        proposed_datetime=STAMP,workspace_root=ws,library_id='main',
        _prevalidated_row={'relative_path':source.name,'filename':source.name,'media_type':'raw'},
        _prevalidated_source=source)


def pending(ws):return list(ro._control_location(ws).glob('operation-*.json'))


def published_failure(case,ws,db,source,*,boundary='error'):
    old=case/'published-pre1';old.mkdir()
    archive=subprocess.check_output(['git','archive','v1.0.0-pre.1','app'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(old,filter='data')
    script=r'''
import os,sys
from pathlib import Path
import app.metadata_correction as m
import app.metadata_swap_recovery as swap
root,db,source=map(Path,sys.argv[1:4]);mode=sys.argv[4]
def write(path,*args):
 if mode=='error':
  Path(path).write_bytes(b'partly written ExifTool staging output')
  raise m.MetadataCorrectionError('ExifTool konnte die Metadaten nicht schreiben: Error: [minor] DNG Version 1.7.0.0 not yet tested')
 Path(path).write_bytes(b'synthetic corrected staging bytes')
 if mode=='during-write':os._exit(42)
m.write_metadata_datetime=write
m.verify_metadata_datetime=lambda *args:{'expected_datetime':'2024-06-23T10:20:21','matching_tags':[{'tag':'test'}]}
if mode in {'after-backup','after-swap'}:
 real=m.os.replace
 def exchange(src,dst,**kw):
  result=real(src,dst,**kw)
  if (mode=='after-backup' and '.metadata-before-' in str(dst)) or (mode=='after-swap' and Path(dst)==source):os._exit(42)
  return result
 m.os.replace=exchange
if mode=='after-db':swap.mark_swap_committed=lambda *args:os._exit(42)
try:
 m.execute_metadata_correction(db,area='general',relative_path=source.name,
  proposed_datetime='2024-06-23T10:20:21',workspace_root=root,library_id='main',
  _prevalidated_row={'relative_path':source.name,'filename':source.name,'media_type':'raw'},_prevalidated_source=source)
except m.MetadataCorrectionError:raise SystemExit(43)
'''
    env=dict(os.environ,PYTHONPATH=str(old),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-c',script,str(ws),str(db),str(source),boundary],env=env,cwd=old,capture_output=True,text=True,timeout=30)
    assert result.returncode==(43 if boundary=='error' else 42),(result.stdout,result.stderr)


def test_refused_write_finishes_only_verified_rollback(fixture,monkeypatch):
    case,ws,reg,db,source=prepare(fixture);before=source.read_bytes()
    def refuse(path,*_):Path(path).write_bytes(b'partial staging output');raise mc.MetadataCorrectionError(ERROR)
    monkeypatch.setattr(mc,'write_metadata_datetime',refuse)
    with pytest.raises(mc.MetadataCorrectionError,match='DNG Version'):execute(db,ws,source)
    assert source.read_bytes()==before and pending(ws)==[]
    assert not list(source.parent.glob('.*metadata-*'))
    assert not list((mc.storage_paths(ws)['metadata_root']/'.swap-journals').glob('*.json'))
    task=mc.list_metadata_corrections(db,include_completed=True)[0]
    assert task['status']=='blocked' and task['error_message']==ERROR and task['completed_at'] is None
    receipt=ro._read(next(ro._control_location(ws).glob('metadata-outcome-*.json')))
    assert receipt['disposition']=='rolled_back' and receipt['task_after']['id']==task['id']
    assert receipt['reservation']['ids']=={'function':recovery.EXECUTE,'area':'general','relative_path':source.name}
    assert receipt['source']['sha256']==hashlib.sha256(before).hexdigest()


def test_published_pre1_historical_block_is_recoverable(fixture):
    case,ws,reg,db,source=prepare(fixture);original=source.read_bytes()
    for _ in range(2):
        with ro.mutate(ws):pass
    published_failure(case,ws,db,source)
    operation=pending(ws)[0];record=ro._read(operation);assert record['generation']==[2,0]
    with database_connection(db) as c:before=dict(c.execute('SELECT * FROM metadata_corrections').fetchone())
    assert before['status']=='blocked' and not list(ro._control_location(ws).glob('metadata-intent-*.json'))
    result=recovery.recover_general_outcomes(ws,reg)
    assert result==[{'task_id':before['id'],'disposition':'rolled_back','reservation_id':record['reservation_id']}]
    assert pending(ws)==[] and source.read_bytes()==original
    with database_connection(db) as c:assert dict(c.execute('SELECT * FROM metadata_corrections').fetchone())==before
    receipt=ro._read(ro._control_location(ws)/('metadata-outcome-'+record['reservation_id']+'.json'))
    assert receipt['reservation']==record and receipt['task_before']==before and receipt['task_after']==before
    assert recovery.recover_general_outcomes(ws,reg)==[]


@pytest.mark.parametrize('fault',['hash','missing','symlink','hardlink','temporary','backup','journal','task','library','generation','binding','nonce','duplicate','output','completed_at','verification'])
def test_historical_ambiguity_keeps_reservation_and_all_bytes(fixture,fault):
    case,ws,reg,db,source=prepare(fixture);published_failure(case,ws,db,source)
    operation=pending(ws)[0];record=ro._read(operation)
    if fault=='hash':source.write_bytes(b'foreign contents')
    if fault=='missing':source.unlink()
    if fault=='symlink':
        target=source.with_name('external.dng');source.rename(target);source.symlink_to(target)
    if fault=='hardlink':os.link(source,source.with_name('external.dng'))
    if fault=='temporary':source.with_name('.'+source.name+'.metadata-unknown.dng').write_bytes(b'unknown staging')
    if fault=='backup':source.with_name('.'+source.name+'.metadata-before-unknown').write_bytes(b'unknown backup')
    if fault=='journal':
        directory=mc.storage_paths(ws)['metadata_root']/'.swap-journals';directory.mkdir(exist_ok=True);(directory/'unknown.json').write_text('{}')
    if fault in {'generation','binding','nonce'}:
        if fault=='generation':record['generation'][0]+=1
        if fault=='binding':record['bindings'][str(ws)]=[0,0]
        if fault=='nonce':record['reservation_id']='wrong'
        ro._write(operation,record)
    # Controlled corrupt historical fixture; application writes are fenced.
    import sqlite3
    with sqlite3.connect(db) as c:
        if fault=='task':c.execute('DELETE FROM metadata_corrections')
        if fault=='library':c.execute('UPDATE metadata_corrections SET detected_json=?',(json.dumps({'library_id':'other'}),))
        if fault=='duplicate':
            columns=[r[1] for r in c.execute('PRAGMA table_info(metadata_corrections)')]
            row=list(c.execute('SELECT * FROM metadata_corrections').fetchone());row[columns.index('id')]='META_OTHER'
            c.execute('INSERT INTO metadata_corrections('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',row)
        if fault=='output':c.execute("UPDATE metadata_corrections SET output_sha256=?",('f'*64,))
        if fault=='completed_at':c.execute("UPDATE metadata_corrections SET completed_at='unknown'")
        if fault=='verification':c.execute("UPDATE metadata_corrections SET verification_json='{}'".replace("'{}'","'{\"unknown\":true}'"))
    before=source.read_bytes() if source.exists() else None
    with pytest.raises(Exception):recovery.recover_general_outcomes(ws,reg)
    assert operation.exists() and ro._read(operation)==record
    assert (source.read_bytes() if source.exists() else None)==before
    assert not list(ro._control_location(ws).glob('metadata-outcome-*.json'))


@pytest.mark.parametrize('boundary',['during-write','after-backup','after-swap','after-db'])
def test_interrupted_general_swap_and_exact_reservation_recover(fixture,boundary):
    case,ws,reg,db,source=prepare(fixture);before=source.read_bytes()
    published_failure(case,ws,db,source,boundary=boundary)
    record=ro._read(pending(ws)[0])
    with ro.reserve(ws,library_id=record['library'],database=db,paths=list(record['bindings']),kind='metadata',ids=record['ids'],expected_generation=tuple(record['generation']),shared=False,_recovery_record=record):
        swaps=recover_metadata_swaps(mc.storage_paths(ws)['metadata_root'],allowed_databases={db})
        assert swaps['blocked']==0,swaps
        result=recovery.recover_general_outcomes(ws,reg)
    assert result[0]['reservation_id']==record['reservation_id'] and pending(ws)==[]
    if boundary=='after-db':assert result[0]['disposition']=='completed' and source.read_bytes()==b'synthetic corrected staging bytes'
    else:assert result[0]['disposition']=='rolled_back' and source.read_bytes()==before


@pytest.mark.parametrize('returncode,message',[(1,'Error: [minor] DNG Version 1.7.0.0 not yet tested'),(0,'Warning: DNG Version 1.7.0.0 not yet tested'),(1,'write permission denied')])
def test_native_write_diagnostics_are_not_ignored(tmp_path,monkeypatch,returncode,message):
    from types import SimpleNamespace
    commands=[]
    def native(command,**kwargs):commands.append(command);return SimpleNamespace(returncode=returncode,stdout='',stderr=message)
    monkeypatch.setattr(mc.subprocess,'run',native)
    with pytest.raises(mc.MetadataCorrectionError,match='ExifTool konnte'):mc.write_metadata_datetime(tmp_path/'staged.dng','raw',STAMP)
    assert '-m' not in commands[0] and '-ignoreMinorErrors' not in commands[0]


def test_new_failed_attempt_keeps_prior_error_history(fixture,monkeypatch):
    case,ws,reg,db,source=prepare(fixture)
    monkeypatch.setattr(mc,'write_metadata_datetime',lambda *_:(_ for _ in ()).throw(mc.MetadataCorrectionError(ERROR)))
    for _ in range(2):
        with pytest.raises(mc.MetadataCorrectionError):execute(db,ws,source)
    rows=mc.list_metadata_corrections(db,include_completed=True)
    assert len(rows)==2 and all(t['status']=='blocked' and t['error_message']==ERROR for t in rows)
    assert pending(ws)==[] and len(list(ro._control_location(ws).glob('metadata-outcome-*.json')))==2


@pytest.mark.parametrize('boundary',['outcome','f14-finished'])
def test_sigkill_after_verified_outcome_resumes_same_reservation(fixture,boundary):
    case,ws,reg,db,source=prepare(fixture)
    code=r'''
import os,signal,sys
from pathlib import Path
from app import metadata_correction as m,root_operations as ro
root,db,source=map(Path,sys.argv[1:4]);boundary=sys.argv[4]
real=ro._write
def write(path,data):
 real(path,data)
 if (boundary=='outcome' and path.name.startswith('metadata-outcome-')) or (boundary=='f14-finished' and path.name.startswith('finished-') and data.get('reservation',{}).get('kind')=='metadata'):
  os.kill(os.getpid(),signal.SIGKILL)
ro._write=write
m.write_metadata_datetime=lambda *_:(_ for _ in ()).throw(m.MetadataCorrectionError('native refused write'))
m.execute_metadata_correction(db,area='general',relative_path=source.name,proposed_datetime='2024-06-23T10:20:21',workspace_root=root,library_id='main',_prevalidated_row={'relative_path':source.name,'filename':source.name,'media_type':'raw'},_prevalidated_source=source)
'''
    process=subprocess.run([sys.executable,'-c',code,str(ws),str(db),str(source),boundary],capture_output=True,text=True,timeout=30)
    assert process.returncode==-signal.SIGKILL,process.stderr
    record=ro._read(pending(ws)[0]);receipt=ro._read(next(ro._control_location(ws).glob('metadata-outcome-*.json')))
    result=recovery.recover_general_outcomes(ws,reg)
    assert result[0]['reservation_id']==record['reservation_id'] and pending(ws)==[]
    assert ro._read(ro._control_location(ws)/('metadata-outcome-'+record['reservation_id']+'.json'))==receipt


def test_startup_recovers_historical_failure_before_workers(fixture,monkeypatch):
    from app import main
    case,ws,reg,db,source=prepare(fixture);published_failure(case,ws,db,source)
    seen=[];monkeypatch.setattr(main,'_start_runtime_workers',lambda:seen.append('workers may start'))
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert seen==['workers may start'] and pending(ws)==[]


def test_uncertain_startup_does_not_release_workers(fixture,monkeypatch):
    from app import main
    case,ws,reg,db,source=prepare(fixture);published_failure(case,ws,db,source);source.write_bytes(b'foreign')
    seen=[];monkeypatch.setattr(main,'_start_runtime_workers',lambda:seen.append('unsafe'))
    main.startup_database()
    from app.operation_health import inspect as operation_status
    assert main.DATABASE_INITIALIZATION_ERROR is None
    status=operation_status(ws)
    assert not status['writes_allowed'] and 'metadata_outcome_' in str(status['issues'])
    assert main.api_storage_health()['state']=='READY'
    assert seen==[] and pending(ws)


def test_missing_backup_after_swap_stays_blocked(fixture):
    case,ws,reg,db,source=prepare(fixture);published_failure(case,ws,db,source,boundary='after-swap')
    backup=next(source.parent.glob('.*.metadata-before-*'));backup.unlink()
    record=ro._read(pending(ws)[0]);after=source.read_bytes()
    result=recover_metadata_swaps(mc.storage_paths(ws)['metadata_root'],allowed_databases={db})
    assert result['blocked']==1
    with pytest.raises(Exception):recovery.recover_general_outcomes(ws,reg)
    assert ro._read(pending(ws)[0])==record and source.read_bytes()==after


def test_change_after_receipt_does_not_become_a_release_bypass(fixture,monkeypatch):
    case,ws,reg,db,source=prepare(fixture)
    monkeypatch.setattr(mc,'write_metadata_datetime',lambda *_:(_ for _ in ()).throw(mc.MetadataCorrectionError(ERROR)))
    original=ro._write
    def corrupt(path,data):
        original(path,data)
        if path.name.startswith('metadata-outcome-'):source.write_bytes(b'foreign changed after receipt')
    monkeypatch.setattr(ro,'_write',corrupt)
    with pytest.raises(mc.MetadataCorrectionError):execute(db,ws,source)
    assert pending(ws) and source.read_bytes()==b'foreign changed after receipt'
    with pytest.raises(Exception):recovery.recover_general_outcomes(ws,reg)
    assert pending(ws)
