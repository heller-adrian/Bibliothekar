"""User-authorized B01 regressions; synthetic registered libraries only."""
import json
import os
import threading
from fastapi.testclient import TestClient
from app import main, root_operations as ro, trash
from app.database import database_connection
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_0263_event_inventory import seed_job, seed_event, seed_family


def seed(fixture):
    case, ws, reg, dbs, ev = fixture
    with database_connection(dbs[0]) as c:
        seed_job(c)
        seed_event(c, status='planned')
        seed_family(c, content=b'synthetic-main', current_path='original.JPG')
    return case, ws, reg, dbs, ev


def test_b01_idle_event_inspection(fixture):
    seed(fixture)
    client = TestClient(main.app, raise_server_exceptions=False)
    try:
        for endpoint in ('edit', 'structure'):
            response = client.get('/api/jobs/j/events/e/' + endpoint)
            assert response.status_code == 200, response.text
    finally:
        client.close()


def test_b01_parallel_edit_structure(fixture, monkeypatch):
    case, ws, reg, dbs, ev = seed(fixture)
    entered = threading.Event()
    release = threading.Event()
    results = {}
    holders = []
    original = trash._physical_entries

    def paused(*args, **kwargs):
        if not entered.is_set():
            record = ro._ACTIVE.get()[-1]
            holders.append({'pid': os.getpid(), 'thread': threading.get_ident(),
                            'record': {k: v for k, v in record.items() if not k.startswith('_')},
                            'lock': str(record['_path'].with_suffix('.lock'))})
            entered.set()
            assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(trash, '_physical_entries', paused)

    def request(endpoint):
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            results[endpoint] = client.get('/api/jobs/j/events/e/' + endpoint)
        finally:
            client.close()

    first = threading.Thread(target=request, args=('structure',))
    first.start()
    assert entered.wait(5)
    timer = threading.Timer(.2, release.set)
    timer.start()
    try:
        request('edit')
    finally:
        release.set()
        first.join(5)
        timer.join()
    (ev / 'b01-lock-holder.json').write_text(json.dumps(holders, indent=2))
    assert results['structure'].status_code == 200, results['structure'].text
    assert results['edit'].status_code == 200, results['edit'].text
    assert not list(ro._control_location(ws).glob('operation-*.json'))


import pytest
import time
from pathlib import Path


def assert_open():
    client=TestClient(main.app,raise_server_exceptions=False)
    try:
        for endpoint in ('edit','structure'):
            response=client.get('/api/jobs/j/events/e/'+endpoint)
            assert response.status_code==200,response.text
    finally:client.close()


@pytest.mark.parametrize('state',['completed','failed','interrupted'])
def test_b01_terminal_hidden_task_is_not_a_kernel_lock(fixture,state):
    from app.database import create_job
    from app.background_activity import clear_finished_activity
    case,ws,reg,dbs,ev=seed(fixture)
    create_job(dbs[0],job_id='OLD_RESTORE',kind='sd_import',trigger_type='manual',operation='trash_import')
    with database_connection(dbs[0]) as c:c.execute('update jobs set state=? where id=?',(state,'OLD_RESTORE'))
    clear_finished_activity(dbs[0],dbs[0])
    # A failed operation keeps durable evidence, but the exited context must
    # not keep a kernel descriptor/lock. No journal is erased for this test.
    with pytest.raises(RuntimeError,match='synthetic failure'):
        with ro.reserve(ws,library_id='main',database=dbs[0],kind='trash',ids={'operation_id':'OLD_RESTORE'}) as record:
            lock=record['_path'].with_suffix('.lock')
            journal=record['_path']
            raise RuntimeError('synthetic failure')
    before=journal.read_bytes()
    with ro._lock(lock,exclusive=True):pass
    assert_open()
    assert journal.read_bytes()==before
    with database_connection(dbs[0]) as c:
        assert c.execute('select state from jobs where id=?',('OLD_RESTORE',)).fetchone()[0]==state
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not c.execute('pragma foreign_key_check').fetchall()


def test_b01_live_inventory_conflict_is_bounded_and_visible(fixture):
    # GET requests are observational; holding a distinct active inventory
    # reservation must neither turn a safe read into a writer nor let it
    # silently rewrite private F14 receipts or stored media.
    case,ws,reg,dbs,ev=seed(fixture)
    entered=threading.Event();release=threading.Event();errors=[]
    def holder():
        try:
            with ro.reserve(ws,library_id='main',database=dbs[0],kind='inventory',ids={'function':'app.trash.reconcile_trash_inventory'}):
                entered.set();assert release.wait(5)
        except BaseException as e:errors.append(repr(e))
    thread=threading.Thread(target=holder);thread.start();assert entered.wait(5)
    parent=ro._control_location(ws)
    evidence_before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    with database_connection(dbs[0]) as c:
        business_before=(c.execute('SELECT state FROM jobs WHERE id=?',('j',)).fetchone()[0],
                         c.execute('SELECT status FROM events WHERE id=?',('e',)).fetchone()[0])
    client=TestClient(main.app,raise_server_exceptions=False)
    try:
        start=time.monotonic();response=client.get('/api/jobs/j/events/e/edit')
        assert response.status_code==200,response.text
        assert response.json()['event']['id']=='e'
        assert time.monotonic()-start<3
        assert {p.name:p.read_bytes() for p in parent.glob('*.json')}==evidence_before
        assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
        with database_connection(dbs[0]) as c:
            assert (c.execute('SELECT state FROM jobs WHERE id=?',('j',)).fetchone()[0],
                    c.execute('SELECT status FROM events WHERE id=?',('e',)).fetchone()[0])==business_before
    finally:release.set();thread.join(5);client.close()
    assert not errors and not thread.is_alive()
    assert_open()


def test_b01_live_trash_operation_is_not_waited_on_indefinitely(fixture):
    from app.trash_selective import _operation_lock
    case,ws,reg,dbs,ev=seed(fixture)
    entered=threading.Event();release=threading.Event()
    def holder():
        with _operation_lock(ws):entered.set();assert release.wait(5)
    thread=threading.Thread(target=holder);thread.start();assert entered.wait(5)
    client=TestClient(main.app,raise_server_exceptions=False)
    try:
        response=client.get('/api/jobs/j/events/e/edit')
        assert response.status_code==409,response.text
        assert 'Papierkorboperation' in response.json()['detail']
    finally:release.set();thread.join(5);client.close()
    assert_open()


def test_b01_process_death_releases_kernel_lock_but_keeps_evidence(fixture):
    import subprocess,sys,signal
    case,ws,reg,dbs,ev=seed(fixture)
    marker=ev/'child-ready.json'
    script='''import sys,os,json,time
from pathlib import Path
from app import root_operations as ro
with ro.reserve(Path(sys.argv[1]),library_id='main',database=Path(sys.argv[2]),kind='trash',ids={'operation_id':'killed'} ) as r:
 Path(sys.argv[3]).write_text(json.dumps({'pid':os.getpid(),'journal':str(r['_path'])}))
 time.sleep(15)
'''
    child=subprocess.Popen([sys.executable,'-c',script,str(ws),str(dbs[0]),str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert marker.exists()
        data=json.loads(marker.read_text());assert data['pid']==child.pid
        journal=Path(data['journal']);before=journal.read_bytes()
        with pytest.raises(ro.RootOperationError):
            with ro._lock(journal.with_suffix('.lock'),exclusive=True):pass
        child.kill();child.wait(timeout=5);assert child.returncode==-signal.SIGKILL
        with ro._lock(journal.with_suffix('.lock'),exclusive=True):pass
        assert_open();assert journal.read_bytes()==before
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        child.communicate()


def test_b01_compatibility_request_collision(fixture,monkeypatch):
    # The former hook on _ensure_compatibility_link was a mutation-side
    # implementation detail. Concurrent GETs must instead be safe, complete
    # and free of new durable F14 records without requiring that hook.
    monkeypatch.setenv("BIBLIOTHEKAR_AUTH_TEST_BYPASS","pytest-isolated")
    case,ws,reg,dbs,ev=seed(fixture)
    entered=threading.Event();release=threading.Event();result={}
    original=main.get_event_edit_context
    def paused(*args,**kwargs):
        if not entered.is_set():
            entered.set();assert release.wait(5)
        return original(*args,**kwargs)
    monkeypatch.setattr(main,'get_event_edit_context',paused)
    parent=ro._control_location(ws)
    evidence_before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    def request(endpoint):
        client=TestClient(main.app,raise_server_exceptions=False)
        try:result[endpoint]=client.get('/api/jobs/j/events/e/'+endpoint)
        finally:client.close()
    first=threading.Thread(target=request,args=('structure',));first.start()
    try:
        assert entered.wait(5),'read-only event context was never consulted'
        timer=threading.Timer(.2,release.set);timer.start()
        try:request('edit')
        finally:timer.join()
    finally:release.set();first.join(5)
    assert not first.is_alive()
    assert result['structure'].status_code==200,result['structure'].text
    assert result['edit'].status_code==200,result['edit'].text
    assert result['structure'].json()['event']['id']=='e'
    assert result['edit'].json()['event']['id']=='e'
    assert {p.name:p.read_bytes() for p in parent.glob('*.json')}==evidence_before
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'


def test_b01_nested_inventory_reuses_its_own_reservation(fixture):
    case,ws,reg,dbs,ev=seed(fixture)
    with ro.reserve(ws,library_id='main',database=dbs[0],kind='inventory',ids={'function':'app.trash.reconcile_trash_inventory'}) as outer:
        trash.reconcile_trash_inventory(dbs[0],ws)
        assert ro._ACTIVE.get()[-1] is outer
    assert_open()
