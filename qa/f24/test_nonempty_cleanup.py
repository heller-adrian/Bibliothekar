import hashlib,json,os
from pathlib import Path
from app import trash_selective as ts
from app.database import database_connection
from tests.backend.test_f11_trash_reservation import fixture
from tests.backend.test_0562_process_recovery import isolated_process_environment,snapshot


def test_normal_partial_deletion_keeps_nonempty_parent(tmp_path,monkeypatch):
    case,evidence,data,db,ws=fixture(tmp_path,monkeypatch)
    root=ws/'Papierkorb';nested=root/'day';nested.mkdir()
    for name in ['A.JPG','B.JPG']:(root/name).rename(nested/name)
    for database in data['databases']:
        with database_connection(Path(database)) as c:
            c.execute("UPDATE files SET current_relative_path='day/'||current_relative_path WHERE current_root_kind='trash'")
    original_b=(nested/'B.JPG').read_bytes()
    snapshot(case,evidence/'partial-before.json')
    error=None;result=None
    try:result=ts.delete_selected_trash_files([Path(p) for p in data['databases']],ws,['day/A.JPG'])
    except Exception as e:error=repr(e)
    snapshot(case,evidence/'partial-after.json')
    record={'error':error,'result':result,'A_exists':(nested/'A.JPG').exists(),'B_exists':(nested/'B.JPG').exists(),'B_sha256':hashlib.sha256((nested/'B.JPG').read_bytes()).hexdigest(),'journal_paths':[str(p) for p in ws.rglob('DELETE_*.json')],'databases':{}}
    for database in data['databases']:
        with database_connection(Path(database)) as c:
            record['databases'][database]={'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':[tuple(r) for r in c.execute('PRAGMA foreign_key_check')],'trash_paths':[r[0] for r in c.execute("SELECT current_relative_path FROM files WHERE current_root_kind='trash'")]}
    (Path(os.environ['AUDIT_OUTPUT'])/'partial-delete-evidence.json').write_text(json.dumps(record,indent=2))
    assert (nested/'B.JPG').read_bytes()==original_b
    assert not (nested/'A.JPG').exists()
    assert error is None,record
    assert result['deleted_file_count']==1


import errno
import pytest
from app import trash_fd

@pytest.mark.parametrize('number', [errno.ENOTEMPTY, errno.EEXIST, errno.EACCES])
def test_optional_cleanup_handles_only_nonempty(tmp_path, monkeypatch, number):
    directory=tmp_path/'parent'; directory.mkdir()
    child=directory/'retained.JPG'; child.write_bytes(b'synthetic-original')
    def fail(*args, **kwargs):
        raise OSError(number, 'synthetic rmdir outcome')
    with monkeypatch.context() as patch:
        patch.setattr(trash_fd.os, 'rmdir', fail)
        if number in {errno.ENOTEMPTY, errno.EEXIST}:
            assert trash_fd.rmdir(directory, ignore_nonempty=True) is False
            with pytest.raises(ts.TrashError):
                trash_fd.rmdir(directory)
        else:
            with pytest.raises(ts.TrashError):
                trash_fd.rmdir(directory, ignore_nonempty=True)
    assert child.read_bytes()==b'synthetic-original'
