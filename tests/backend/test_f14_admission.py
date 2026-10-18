"""F14 admission before SQL claims and HTTP queue planning."""
import hashlib,json,threading
import pytest
from app import main,root_operations as ro
from app.library_context import resolve_library_context
from app.storage_config import storage_paths,load_storage_settings
from app.database import database_connection
from tests.backend.test_f14_root_operations import fixture,snapshot,settings_change


def test_f14_idle_claims_do_not_create_operation_journals(fixture):
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main')
    for n in range(5):assert main._claim_context_job(ctx) is None
    parent=ro._control_location(ws)
    assert not list(parent.glob('*.json'))
    snapshot(case,ev/'idle-claims.json')


def test_f14_claim_before_root_decision_holds_admission(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main');entered=threading.Event();release=threading.Event();errors=[]
    actual=main.claim_next_job
    def barrier(*args,**kwargs):
        entered.set();assert release.wait(10);return actual(*args,**kwargs)
    monkeypatch.setattr(main,'claim_next_job',barrier)
    def claim():
        try:assert main._claim_context_job(ctx) is None
        except BaseException as e:errors.append(repr(e))
    thread=threading.Thread(target=claim);thread.start();assert entered.wait(10)
    try:
        with pytest.raises(main.HTTPException) as exc:main.api_set_storage_paths(settings_change())
        assert exc.value.status_code==410
        assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    finally:release.set();thread.join(10)
    assert not thread.is_alive() and not errors
    with pytest.raises(main.HTTPException) as exc:main.api_set_storage_paths(settings_change())
    assert exc.value.status_code==410
    snapshot(case,ev/'claim-complete.json')


def test_f14_root_decision_prevents_new_claim_before_sql(fixture,monkeypatch):
    from app.library_registry import update_library_paths
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main');called=[]
    monkeypatch.setattr(main,'claim_next_job',lambda *a,**k:called.append('sql'))
    with ro.mutate(ws,library_id='main'):
        with pytest.raises(ro.RootOperationError):main._claim_context_job(ctx)
        assert not called
    target=case/'new-archive';target.mkdir();update_library_paths(reg,'main',archive_root=target)
    with pytest.raises(ro.RootOperationError):main._claim_context_job(ctx)
    assert not called
    snapshot(case,ev/'root-then-claim.json')


def test_f14_duplicate_actual_http_root_requests_are_serialized(fixture,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,reg,dbs,ev=fixture;barrier=threading.Barrier(3);responses=[]
    snapshot(case,ev/'reader-warmup.json')
    before=snapshot(case,ev/'before-http.json')
    # Avoid lifespan: these fixtures intentionally contain no queued application jobs.
    def request():
        client=TestClient(main.app)
        try:
            barrier.wait(timeout=10)
            responses.append(client.put('/api/settings/storage-paths',json=settings_change()))
        finally:client.close()
    threads=[threading.Thread(target=request) for _ in range(2)]
    for t in threads:t.start()
    barrier.wait(timeout=10)
    for t in threads:t.join(15);assert not t.is_alive()
    assert len(responses)==2 and all(r.status_code==410 for r in responses)
    assert snapshot(case,ev/'after-http.json')==before
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'


def test_f14_missing_registered_workspace_never_claims_sql(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main');called=[]
    retained=case/'retained-workspace';ws.rename(retained)
    monkeypatch.setattr(main,'claim_next_job',lambda *a,**k:called.append('unexpected SQL'))
    with pytest.raises(ro.RootOperationError):main._claim_context_job(ctx)
    assert not called
    assert (retained/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'unavailable-registered-root.json')
