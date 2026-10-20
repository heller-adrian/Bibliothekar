from pathlib import Path
from contextlib import contextmanager
import threading,json
import pytest
from test_interleavings import seed,thread_call
from test_more import end
from test_process_crashes import snapshot
from app.database import database_connection


def fixture(case):
    from tests.backend.test_0500_reassignment_atomic import _applied_source
    extra=case/'relational';extra.mkdir()
    return _applied_source(extra)

@pytest.mark.parametrize('mode',['new_event','new_no_event'])
def test_competing_reassignments(tmp_path,monkeypatch,mode):
    case,ev,data,main_db,ws=seed(tmp_path,'trash','P404-reassign-'+mode,monkeypatch)
    db,ids,segments=fixture(case)
    from app import event_reassignment as er
    real=er.database_connection;barrier=threading.Barrier(2);local=threading.local()
    @contextmanager
    def connect(path):
        local.n=getattr(local,'n',0)+1;first=local.n==1
        with real(path) as c:yield c
        if first:barrier.wait(timeout=10)
    monkeypatch.setattr(er,'database_connection',connect)
    def assign():return er.assign_event_reassignments(db,'j','b',ids,target_mode=mode,new_event_name='Synthetic target',segments=segments)
    a,x=thread_call(assign);b,y=thread_call(assign);a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    restarts=end(case,ev,{'order':['standalone synthetic relational fixture, no physical reassignment simulated','both read no existing receipt','barrier before writer transactions','one assignment commits, competing request rejects'],'results':x+y,'scope':'SQLite reassignment component; extra DB not registered, global claims/physical recovery not claimed'})
    assert sum(r['ok'] for r in x+y)==1,x+y
    with database_connection(db) as c:
        for fid in ids:
            roots=c.execute('SELECT DISTINCT COALESCE(e.parent_event_id,e.id) FROM event_assignments a JOIN events e ON e.id=a.event_id WHERE a.family_id=?',(fid,)).fetchall();assert len(roots)==1
    assert all(r['returncode']==0 for r in restarts)


def test_cancel_serializes_after_reassignment(tmp_path,monkeypatch):
    case,ev,data,main_db,ws=seed(tmp_path,'trash','P404-cancel-after-reassignment',monkeypatch)
    db,ids,segments=fixture(case)
    from app import event_reassignment as er,event_mutation as em
    actual=er._root_event;reached=threading.Event();resume=threading.Event();cancel_attempt=threading.Event();first=[True]
    def root(*a,**kw):
        result=actual(*a,**kw)
        if first[0]:first[0]=False;reached.set();assert resume.wait(10)
        return result
    monkeypatch.setattr(er,'_root_event',root)
    a,x=thread_call(lambda:er.assign_event_reassignments(db,'j','b',ids,target_mode='new_no_event',segments=segments));assert reached.wait(10)
    with database_connection(db) as c:mutation=c.execute("SELECT id FROM event_mutations WHERE anchor_event_id='b'").fetchone()[0]
    def cancel():
        with database_connection(db) as c:
            cancel_attempt.set();c.execute('BEGIN IMMEDIATE')
            return em.cancel_mutation(c,mutation,'j')
    b,y=thread_call(cancel);assert cancel_attempt.wait(10);resume.set();a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    restarts=end(case,ev,{'order':['reassignment holds BEGIN IMMEDIATE and reads source','cancel attempts BEGIN IMMEDIATE','assignment commits','cancel restores original graph'],'assign':x,'cancel':y,'scope':'SQLite relation-only component; no physical files or global claims for the extra DB'})
    assert x[0]['ok'] and y[0]['ok'],x+y
    with database_connection(db) as c:
        for fid in ids:
            roots=[r[0] for r in c.execute('SELECT DISTINCT COALESCE(e.parent_event_id,e.id) FROM event_assignments a JOIN events e ON e.id=a.event_id WHERE a.family_id=?',(fid,))];assert roots==['b'],roots
        assert c.execute('SELECT status FROM event_mutations WHERE id=?',(mutation,)).fetchone()[0]=='cancelled'
    assert all(r['returncode']==0 for r in restarts)
