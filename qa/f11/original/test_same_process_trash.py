from pathlib import Path
import threading
import pytest
from test_interleavings import seed,thread_call
from test_more import end
from test_process_crashes import snapshot
from app import main


def test_same_process_restore_inventory_vs_delete(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P401-thread-restore-inventory-delete',monkeypatch)
    from app import trash_selective as ts
    from fastapi import HTTPException
    reached=threading.Event();resume=threading.Event();real=ts._move_checked;once=[True]
    def move(*a,**kw):
        value=real(*a,**kw)
        if once[0]:once[0]=False;reached.set();assert resume.wait(15)
        return value
    monkeypatch.setattr(ts,'_move_checked',move)
    t,result=thread_call(lambda:ts.delete_selected_trash_files([Path(p) for p in data['databases']],ws,['A.JPG','B.JPG']))
    assert reached.wait(10)
    try:
        with pytest.raises(HTTPException) as error:main.api_restore_trash({'relative_paths':['A.JPG']})
        assert error.value.status_code==409
        snapshot(case,ev/'restore-reconciled-catalog-before-delete-resume.json')
    finally:resume.set();t.join(15)
    assert not t.is_alive()
    restarts=end(case,ev,{'order':['same-process selective deletion holds operation RLock, stages A','restore API directly reconciles trash rows while A is staged','restore rejects missing A','deletion detects changed catalogue and rollback conflicts'],'delete':result,'restore_error':str(error.value)})
    assert all(r['returncode']==0 for r in restarts),restarts
