"""Deterministic ownership races and genuine SIGKILL/restart evidence for F11."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import signal

import pytest
from fastapi import HTTPException
from app import main
from app.database import database_connection
from app.trash import TrashError
from app import trash_import as ti, trash_selective as ts
from tests.backend import test_0562_process_recovery as recovery
from tests.backend.test_0562_process_recovery import isolated_process_environment


def fixture(tmp_path, monkeypatch):
    case=tmp_path/'case';case.mkdir()
    evidence=tmp_path/'f11-evidence';evidence.mkdir()
    record=recovery.invoke(case,'seed','trash',evidence/'seed')
    assert record['returncode']==0,record
    # Establish the normal startup projection before capturing pre-request state.
    initialized=recovery.invoke(case,'startup','none',evidence/'initial-startup')
    assert initialized['returncode']==0,initialized
    data=json.loads((case/'case.json').read_text());db=Path(data['db']);ws=Path(data['workspace'])
    from app.library_context import resolve_library_context
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'))
    for key,value in dict(DATABASE_FILE=db,REGISTRY_DATABASE_FILE=case/'registry.sqlite3',WORKSPACE_PATH=ws,MAIN_LIBRARY_CONTEXT=resolve_library_context(case/'registry.sqlite3','main'),LOG_PATH=case/'logs').items():
        monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(main,'current_database_file',lambda:db)
    recovery.snapshot(case,evidence/'before.json')
    return case,evidence,data,db,ws


def restart(case,ev):
    states=[]
    for n in range(1,4):
        record=recovery.invoke(case,'startup','none',ev/f'restart{n}')
        state=recovery.snapshot(case,ev/f'after-restart{n}.json')
        recovery.checks_sql(state);assert record['returncode']==0,record
        states.append(state)
    assert recovery.business_rows(states[0])==recovery.business_rows(states[1])==recovery.business_rows(states[2])
    return states[-1]


def run_thread(fn):
    result=[]
    def execute():
        try:result.append(('ok',fn()))
        except Exception as e:result.append(('error',e))
    thread=threading.Thread(target=execute);thread.start();return thread,result


def empty():return main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})


def matching(case,digest):
    return [p for p in case.rglob('*.JPG') if hashlib.sha256(p.read_bytes()).hexdigest()==digest]


@pytest.mark.parametrize('operation',['full','selective','direct-delete','direct-restore'])
def test_f11_reservation_wins(tmp_path,monkeypatch,operation):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    job=main.api_restore_trash({'relative_paths':['A.JPG']})
    actions={'full':empty,'selective':lambda:main.api_empty_trash_selection({'relative_paths':['A.JPG']}),
      'direct-delete':lambda:ts.delete_selected_trash_files([db],ws,['A.JPG']),
      'direct-restore':lambda:__import__('app.trash_restore',fromlist=['restore_trash_files']).restore_trash_files([db],ws,relative_paths=['A.JPG'])}
    with pytest.raises((HTTPException,TrashError)) as caught:actions[operation]()
    if isinstance(caught.value,HTTPException):assert caught.value.status_code==409
    assert ti.protected_trash_paths(db,ws)=={'A.JPG'}
    recovery.snapshot(case,ev/'after-conflict.json')
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    restart(case,ev)
    assert len(matching(case,data['expected']['A.JPG']))==1
    assert not list(case.rglob('DELETE_*.json'))


def test_f11_original_boundary_and_restore(tmp_path,monkeypatch):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    reached=threading.Event();proceed=threading.Event();real=main.empty_trash_filesystem
    def paused(root):
        reached.set();assert proceed.wait(15);return real(root)
    monkeypatch.setattr(main,'empty_trash_filesystem',paused)
    thread,result=run_thread(empty);assert reached.wait(15)
    main.api_restore_trash({'relative_paths':['A.JPG']})
    proceed.set();thread.join(15);assert not thread.is_alive()
    assert result[0][0]=='error' and result[0][1].status_code==409
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    recovery.snapshot(case,ev/'after-conflict.json');restart(case,ev)
    assert len(matching(case,data['expected']['A.JPG']))==1
    assert not (ws/'Papierkorb/A.JPG').exists()  # legitimate completed restore


@pytest.mark.parametrize('operation',['full','selective'])
def test_f11_delete_wins_restore_rejected(tmp_path,monkeypatch,operation):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    reached=threading.Event();proceed=threading.Event();real=ts._move_checked
    def paused(*args,**kwargs):
        result=real(*args,**kwargs);reached.set();assert proceed.wait(15);return result
    monkeypatch.setattr(ts,'_move_checked',paused)
    action=empty if operation=='full' else lambda:main.api_empty_trash_selection({'relative_paths':['A.JPG']})
    thread,result=run_thread(action);assert reached.wait(15)
    before=recovery.snapshot(case,ev/'staged.json')
    try:
        with pytest.raises(HTTPException) as error:main.api_restore_trash({'relative_paths':['B.JPG']})
        assert error.value.status_code==409
        assert recovery.business_rows(before)==recovery.business_rows(recovery.snapshot(case,ev/'rejected.json'))
        assert not list(case.rglob('TRASH_IMPORT_*.json'))
    finally:proceed.set();thread.join(15)
    assert not thread.is_alive() and result[0][0]=='ok',result
    state=restart(case,ev)
    assert not list(case.rglob('DELETE_*.json'))
    assert (ws/'Papierkorb/B.JPG').exists()==(operation=='selective')


@pytest.mark.parametrize('kind',['restore','empty'])
def test_f11_two_concurrent_requests(tmp_path,monkeypatch,kind):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    barrier=threading.Barrier(3)
    def request():
        barrier.wait(15)
        return main.api_restore_trash({'relative_paths':['A.JPG']}) if kind=='restore' else empty()
    a,x=run_thread(request);b,y=run_thread(request);barrier.wait(15);a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    results=x+y;assert any(r[0]=='ok' for r in results)
    for status,result in results:
        if status=='error':assert isinstance(result,HTTPException) and result.status_code==409
    if kind=='restore':
        assert sum(r[0]=='ok' for r in results)==1
        assert len(list(case.rglob('TRASH_IMPORT_*.json')))==1
    recovery.snapshot(case,ev/'after-requests.json');restart(case,ev)
    if kind=='restore':assert len(matching(case,data['expected']['A.JPG']))==1
    else:assert not matching(case,data['expected']['A.JPG']) and not list(case.rglob('DELETE_*.json'))


@pytest.mark.parametrize('terminal',['failed','completed','interrupted','orphan'])
def test_f11_durable_intent_is_not_released_by_job_status(tmp_path,monkeypatch,terminal):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    job=main.api_restore_trash({'relative_paths':['A.JPG']})['job_id']
    with database_connection(db) as c:
        if terminal=='orphan':c.execute('DELETE FROM jobs WHERE id=?',(job,))
        else:c.execute('UPDATE jobs SET state=? WHERE id=?',(terminal,job))
    assert ti.protected_trash_paths(db,ws)=={'A.JPG'}
    with pytest.raises(HTTPException) as error:empty()
    assert error.value.status_code==409
    recovery.snapshot(case,ev/'blocked.json');restart(case,ev)
    assert matching(case,data['expected']['A.JPG'])


@pytest.mark.parametrize('bad',['malformed','symlink','normalized-duplicate'])
def test_f11_unclear_ownership_fails_closed(tmp_path,monkeypatch,bad):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    parent=ti.stage_parent(ws)
    if bad=='normalized-duplicate':
        with pytest.raises(TrashError):ti.queue_trash_restore(db,ws,['A.JPG','./A.JPG'])
        assert not list(parent.glob('TRASH_IMPORT_*.json'))
    else:
        path=parent/'TRASH_IMPORT_BAD.json'
        if bad=='symlink':path.symlink_to(ws/'Papierkorb/A.JPG')
        else:path.write_text('{}')
        with pytest.raises(HTTPException) as error:empty()
        assert error.value.status_code==409
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    recovery.snapshot(case,ev/'after.json')


def assert_restored_catalogue(before, crashed, state):
    # HTTP preflight inventories update the scan timestamp before the durable
    # deletion decision. Compare every restored column to that exact journal,
    # and all business identities/claims to the pre-request snapshot.
    assert recovery.business_rows(before)==recovery.business_rows(state)
    journal=next(v for k,v in crashed['documents'].items() if 'DELETE_' in k)
    for database in journal['databases']:
        name=Path(database['path']).name
        for table in ('files','file_families'):
            expected=[item['row'] for item in database['snapshot']['deleted'] if item['table']==table]
            assert sorted(recovery.db_rows(state,table,name),key=lambda r:r['id'])==sorted(expected,key=lambda r:r['id'])


@pytest.mark.parametrize('boundary',recovery.TRASH)
def test_f11_full_empty_sigkill(tmp_path,monkeypatch,boundary):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    before=recovery.snapshot(case,ev/'catalogue-before.json')
    recovery.invoke(case,'full_empty',boundary,ev/'kill',kill=True)
    crashed=recovery.snapshot(case,ev/'after-kill.json');recovery.checks_sql(crashed)
    assert list(case.rglob('DELETE_*.json'))
    state=restart(case,ev);committed=boundary in {'trash.committed','trash.cleanup1'}
    if committed:
        for database in ('kamera.sqlite3','second1.sqlite3'):
            for table in ('files','file_families'):assert recovery.db_rows(state,table,database)==[]
    else:assert_restored_catalogue(before,crashed,state)
    for name,digest in data['expected'].items():
        if committed:assert not (ws/'Papierkorb'/name).exists()
        else:assert recovery.hash_file(ws/'Papierkorb'/name)==digest
    assert not list(case.rglob('DELETE_*.json'))


@pytest.mark.parametrize('boundary',['f11.reserve_before','f11.reserve_after','f11.reserve_committed'])
def test_f11_reservation_sigkill(tmp_path,monkeypatch,boundary):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    recovery.invoke(case,'queue_restore',boundary,ev/'kill',kill=True)
    recovery.snapshot(case,ev/'after-kill.json')
    if boundary=='f11.reserve_before':
        assert ti.protected_trash_paths(db,ws)==set()
        assert not list(case.rglob('TRASH_IMPORT_*.json'))
    else:
        assert ti.protected_trash_paths(db,ws)=={'A.JPG'}
        with pytest.raises(HTTPException) as error:empty()
        assert error.value.status_code==409
    restart(case,ev);assert matching(case,data['expected']['A.JPG'])
    if boundary=='f11.reserve_after':
        assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
        assert ti.protected_trash_paths(db,ws)=={'A.JPG'}


@pytest.mark.parametrize('boundary',['trash.recover_db1','trash.recover_file1','trash.recover_cleanup'])
def test_f11_full_empty_recovery_killed_twice(tmp_path,monkeypatch,boundary):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    before=recovery.snapshot(case,ev/'catalogue-before.json')
    recovery.invoke(case,'full_empty','trash.db1',ev/'kill',kill=True)
    crashed=recovery.snapshot(case,ev/'after-kill.json')
    for n in (1,2):
        recovery.invoke(case,'startup',boundary,ev/f'recovery-kill{n}',kill=True)
        recovery.snapshot(case,ev/f'after-recovery-kill{n}.json')
    state=restart(case,ev)
    assert_restored_catalogue(before,crashed,state)
    for digest in data['expected'].values():assert len(matching(case,digest))==1
    assert not list(case.rglob('DELETE_*.json'))


def test_f11_two_process_reservations(tmp_path,monkeypatch):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    # Parent owns the real flock; both fresh children contend on the same key.
    program="from app.trash_import import queue_trash_restore; from pathlib import Path; import sys; Path(sys.argv[3]).write_text('ready'); queue_trash_restore(Path(sys.argv[1]),Path(sys.argv[2]),['A.JPG'])"
    env=dict(os.environ)
    children=[]
    with ts._operation_lock(ws):
        for n in (1,2):
            log=(ev/f'child{n}.log').open('w')
            child=subprocess.Popen([sys.executable,'-c',program,str(db),str(ws),str(ev/f'ready{n}')],stdout=log,stderr=subprocess.STDOUT,env=env)
            children.append((child,log))
        deadline=time.monotonic()+15
        while not all((ev/f'ready{n}').exists() for n in (1,2)) and time.monotonic()<deadline:time.sleep(.01)
        assert all((ev/f'ready{n}').exists() for n in (1,2))
        assert not list(case.rglob('TRASH_IMPORT_*.json'))
    try:
        for child,log in children:child.wait(timeout=20);log.close()
    finally:
        for child,log in children:
            if child.poll() is None:child.kill();child.wait()
            log.close()
    assert sorted(c.returncode for c,_ in children)==[0,1]
    assert len(list(case.rglob('TRASH_IMPORT_*.json')))==1
    recovery.snapshot(case,ev/'after-processes.json');restart(case,ev)
    assert len(matching(case,data['expected']['A.JPG']))==1


def test_f11_live_process_delete_blocks_all_http_mutations(tmp_path,monkeypatch):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    control=ev/'live-delete';control.mkdir()
    with (control/'process.log').open('w') as log:
        child=subprocess.Popen([sys.executable,str(recovery.ROOT/'worker.py'),str(case),'full_empty','trash.stage1',str(control)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            deadline=time.monotonic()+20
            while not (control/'checkpoint.json').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            assert (control/'checkpoint.json').exists()
            for fn in (empty,lambda:main.api_restore_trash({'relative_paths':['B.JPG']}),lambda:main.api_empty_trash_selection({'relative_paths':['B.JPG']})):
                with pytest.raises(HTTPException) as error:fn()
                assert error.value.status_code==409
            recovery.snapshot(case,ev/'while-owner-stopped.json')
        finally:
            if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=5)
    assert child.returncode==-signal.SIGKILL
    restart(case,ev)
    for digest in data['expected'].values():assert len(matching(case,digest))==1


@pytest.mark.parametrize('legacy',[False,True])
def test_f11_sqlite_failure_retains_durable_reservation(tmp_path,monkeypatch,legacy):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    def failed(*args,**kwargs):raise RuntimeError('synthetic SQLite commit failure')
    monkeypatch.setattr(ti,'create_job',failed)
    with pytest.raises(TrashError):
        (ti.stage_trash_import if legacy else ti.queue_trash_restore)(db,ws,['A.JPG'])
    assert ti.protected_trash_paths(db,ws)=={'A.JPG'}
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    with pytest.raises(HTTPException) as error:empty()
    assert error.value.status_code==409
    recovery.snapshot(case,ev/'orphaned-intent.json');restart(case,ev)
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'


def test_f11_legacy_delete_reservation_conflict_preserves_evidence(tmp_path,monkeypatch):
    case,ev,data,db,ws=fixture(tmp_path,monkeypatch)
    recovery.invoke(case,'full_empty','trash.db1',ev/'kill',kill=True)
    owner='TRASH_IMPORT_UNCLEAR'
    ts._atomic_json(ti.stage_parent(ws)/(owner+'.json'),{'job_id':owner,'schema_version':2,'status':'queued','relative_paths':['A.JPG'],'files':[]})
    before=recovery.snapshot(case,ev/'legacy-conflict.json')
    assert list(case.rglob('DELETE_*.json'))
    for n in (1,2,3):
        record=recovery.invoke(case,'startup','none',ev/f'blocked-restart{n}')
        assert record['returncode']!=0 and 'Wiederherstellungsreservierung' in str(record.get('result'))
        state=recovery.snapshot(case,ev/f'after-blocked-restart{n}.json');recovery.checks_sql(state)
        assert recovery.business_rows(before)==recovery.business_rows(state)
        assert list(case.rglob('DELETE_*.json')) and list(case.rglob(owner+'.json'))
        for digest in data['expected'].values():assert len(matching(case,digest))==1
