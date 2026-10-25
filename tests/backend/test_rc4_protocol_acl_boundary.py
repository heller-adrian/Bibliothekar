"""Observed NAS modes: preserve the boundary until effective ACLs are proven.

Real chmod is restricted to synthetic temporary artifacts. UID/GID 568:0 are
an explicitly labelled fstat model on macOS, not a native Linux/chown test.
"""
from contextlib import contextmanager
import hashlib,json,os,stat
from types import SimpleNamespace
from pathlib import Path
import pytest
from app import main,trash_failure as tf,trash_import as ti
from app.database import database_connection
from app.storage_config import storage_paths
from app.trash import TrashError
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc4_practice import protocol_failure


@pytest.mark.parametrize('directory_mode,file_mode,opened_status',[
    (0o770,0o770,False),(0o770,0o700,False),(0o700,0o770,True),
])
def test_observed_568_0_mode_boundary(tmp_path,monkeypatch,directory_mode,file_mode,opened_status):
    jid='TRASH_IMPORT_20261023_205446_538D89094806'
    incoming=tmp_path/jid;protocol=incoming/'Protocol';protocol.mkdir(parents=True)
    stage=Path('/workspace/Metadata Correction/.trash-import')/jid
    status=protocol/'status.json'
    document={'schema_version':3,'job_id':jid,'state':'failed','stage':'failed','simulation':False,'import_mode':'folder',
              'source_path':str(stage),'lifecycle':{'temporary_backup':'/workspace/SD Card Backups/.incoming/'+jid+'/Original','central_stock':'/workspace/SD Card Backups'}}
    encoded=json.dumps(document).encode();assert len(encoded)<=808
    status.write_bytes(encoded+b' '*(808-len(encoded)))
    incoming.chmod(0o700);protocol.chmod(directory_mode);status.chmod(file_mode)
    assert stat.S_IMODE(protocol.stat().st_mode)==directory_mode
    assert stat.S_IMODE(status.stat().st_mode)==file_mode
    assert status.stat().st_nlink==1 and status.stat().st_size==808
    raw=status.read_bytes();real_fstat=os.fstat;real_file_at=tf.trash_fd.file_at;opened=[]
    targets={(p.stat().st_dev,p.stat().st_ino):p for p in [incoming,protocol,status]}
    def observed(fd):
        info=real_fstat(fd)
        if (info.st_dev,info.st_ino) not in targets:return info
        values={key:getattr(info,key) for key in dir(info) if key.startswith('st_')}
        values.update(st_uid=568,st_gid=0)
        if stat.S_ISDIR(info.st_mode):values['st_nlink']=2
        return SimpleNamespace(**values)
    @contextmanager
    def trace_file(*args,**kwargs):
        opened.append(True)
        with real_file_at(*args,**kwargs) as value:yield value
    with monkeypatch.context() as mapped:
        mapped.setattr(tf.os,'fstat',observed);mapped.setattr(tf.os,'geteuid',lambda:568)
        mapped.setattr(tf.trash_fd,'file_at',trace_file)
        with pytest.raises(TrashError,match='Ungeklärter Import-Zwischenbestand bleibt erhalten'):
            tf._protocol_only_failure(incoming,stage,jid)
    assert bool(opened) is opened_status
    assert status.read_bytes()==raw
    assert stat.S_IMODE(protocol.stat().st_mode)==directory_mode
    assert stat.S_IMODE(status.stat().st_mode)==file_mode
    (tmp_path/'observed-proof.json').write_text(json.dumps({'uid_gid_model':[568,0],
        'actual_host_uid_gid':[os.geteuid(),os.getegid()],'directory_mode':oct(directory_mode),
        'file_mode':oct(file_mode),'status_size':808,'status_opened':bool(opened),
        'write_mask':oct((directory_mode|file_mode)&0o022),'sha256':hashlib.sha256(raw).hexdigest()},indent=2))


@pytest.mark.parametrize('mode',[0o770,0o777,0o775])
def test_no_failed_job_release_or_empty_for_writable_protocol(fixture,mode):
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    status.parent.chmod(mode);status.chmod(mode)
    original_status=status.read_bytes();original_journal=journal.read_bytes()
    before=snapshot(fixture[0],fixture[4]/'before.json')
    result=tf.recover_failed_restores(db,ws)
    assert result==[{'job_id':jid,'status':'blocked','message':'Ungeklärter Import-Zwischenbestand bleibt erhalten: '+str(incoming)}]
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    with pytest.raises(main.HTTPException) as error:main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert error.value.status_code==409
    assert journal.read_bytes()==original_journal and status.read_bytes()==original_status
    after=snapshot(fixture[0],fixture[4]/'after.json');assert before['databases']==after['databases']
    for item in data['files']:
        for path in [storage_paths(ws)['trash_root']/item['relative_path'],ti.stage_parent(ws)/jid/item['relative_path']]:
            assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
    with database_connection(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        row=c.execute('SELECT state,stage,error_message FROM jobs WHERE id=?',(jid,)).fetchone()
        assert row['state']==row['stage']=='failed' and row['error_message']


def test_qualified_local_protocol_finalizes_and_can_empty(fixture):
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    status.parent.chmod(0o700);status.chmod(0o600)
    original_protocol=status.read_bytes()
    assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
    assert not ti.protected_trash_paths(None,ws)
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert journal.exists() and status.read_bytes()==original_protocol
    for item in data['files']:
        assert not (storage_paths(ws)['trash_root']/item['relative_path']).exists()
        assert hashlib.sha256((ti.stage_parent(ws)/jid/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
    with database_connection(db) as c:
        assert c.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()


def test_sigkill_nonqualified_read_and_three_independent_processes(fixture,tmp_path):
    import subprocess,sys,time,signal
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    status.parent.chmod(0o770);status.chmod(0o770)
    before=snapshot(fixture[0],fixture[4]/'before-kill.json')
    original_journal=journal.read_bytes();original_protocol=status.read_bytes()
    case=tmp_path/'case.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'job_id':jid,'incoming':str(incoming),'paths':data['relative_paths']}))
    worker=Path(__file__).parents[2]/'qa/rc4-practice/protocol_acl_worker.py';marker=tmp_path/'marker'
    cmd=[sys.executable,'-B',str(worker),str(case),str(marker)]
    p=subprocess.Popen(cmd+['pause'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+20
    while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not marker.exists():
        p.kill();out,err=p.communicate(timeout=5);pytest.fail(out+err)
    p.kill();out,err=p.communicate(timeout=5);assert p.returncode==-signal.SIGKILL
    (tmp_path/'killed.log').write_text(out+err)
    for n in range(3):
        r=subprocess.run(cmd+['read'],capture_output=True,text=True,timeout=20)
        (tmp_path/f'restart{n}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
        assert json.loads(r.stdout)['status']=='blocked'
        assert journal.read_bytes()==original_journal and status.read_bytes()==original_protocol
        after=snapshot(fixture[0],fixture[4]/f'after-restart{n}.json')
        assert after['databases']==before['databases']
        for item in data['files']:
            for path in [storage_paths(ws)['trash_root']/item['relative_path'],ti.stage_parent(ws)/jid/item['relative_path']]:
                assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
