"""Combined F14 duplicate admission, R1 collision and F11 deletion reservation."""
from pathlib import Path
import threading
import pytest
from fastapi import HTTPException
from app import main,trash_restore as tr
from app.trash import TrashError
from tests.backend.test_r1_restore_recovery import seed,starts,preserved,journal
from tests.backend.test_0562_process_recovery import isolated_process_environment

@pytest.mark.parametrize('deletion',['full','selective'])
def test_duplicate_restore_denied_before_trash_lock_preserves_conflict(tmp_path,monkeypatch,deletion):
    case,ev,data,ws=seed(tmp_path,monkeypatch)
    reached=threading.Event();release=threading.Event();targets=[];results=[];real=tr.os.link
    source=ws/'Papierkorb/A.JPG';original_identity=tr._identity(source)
    def link(src,dst,*a,**kw):
        if Path(src)==source:
            target=Path(dst);target.write_bytes(b'synthetic-foreign-target');targets.append(target)
            reached.set();assert release.wait(15)
        return real(src,dst,*a,**kw)
    monkeypatch.setattr(tr.os,'link',link)
    def owner():
        try:results.append(tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG']))
        except Exception as error:results.append(error)
    thread=threading.Thread(target=owner);thread.start()
    try:
        assert reached.wait(15)
        target_identity=tr._identity(targets[0])
        with pytest.raises(TrashError):tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG'])
        assert tr._identity(source)==original_identity
        assert tr._identity(targets[0])==target_identity
        preserved(data,ws,targets[0])
    finally:
        release.set();thread.join(20)
    assert not thread.is_alive() and isinstance(results[0],TrashError)
    monkeypatch.setattr(tr.os,'link',real)
    record=journal(case);raw=record.read_bytes()
    with pytest.raises(HTTPException) as error:
        if deletion=='full':main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
        else:main.api_empty_trash_selection({'relative_paths':['A.JPG']})
    assert error.value.status_code==409
    starts(case,ev);preserved(data,ws,targets[0])
    assert tr._identity(source)==original_identity and tr._identity(targets[0])==target_identity
    assert record.read_bytes()==raw
