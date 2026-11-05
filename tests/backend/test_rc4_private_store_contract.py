"""Private-store decision/diagnostic checks; no new product trust assertion."""
import importlib.util,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import trash_failure as tf,trash_import as ti,main
from app.database import database_connection
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc4_nas_legacy import failed_restore

path=Path(__file__).parents[2]/'qa/rc4-practice/private_store_diagnose.py'
spec=importlib.util.spec_from_file_location('private_store_diagnose',path)
diagnostic=importlib.util.module_from_spec(spec);spec.loader.exec_module(diagnostic)


def container():
    return {'Config':{'User':'0:0','Env':['SECRET=must-not-be-printed']},
            'HostConfig':{'UsernsMode':'','Privileged':True},
            'Mounts':[{'Type':'bind','Destination':d,'Source':s,'RW':True} for d,s in
                      [('/database','/mnt/apps/bibliothekar-db'),('/config','/mnt/apps/bibliothekar-config'),('/workspace','/mnt/apps/kamera-arbeitsbereich')]]}


def test_diagnostic_is_scoped_read_only_and_does_not_assert_trust():
    calls=[]
    # Only the permissions supplied by the user are modeled; not a claimed
    # reconstruction of the unavailable full ACE order/flags/rights document.
    acl={'acltype':'NFS4','trivial':False,'uid':568,'gid':0,'acl':[
        {'tag':tag,'id':identity,'type':'ALLOW',
         'perms':{'WRITE_DATA':True,'DELETE':True,'DELETE_CHILD':True,
                  **({'WRITE_ACL':True,'WRITE_OWNER':True} if identity==544 else {})},
         'flags':{'INHERITED':True}}
        for tag,identity in [('owner@',568),('group@',0),('GROUP',545),('GROUP',544),('USER',3001),('USER',3000)]]}
    def run(argv):
        calls.append(argv)
        if argv[:2]==['docker','inspect']:return [container()]
        if argv[:2]==['docker','exec']:return [{'Uid':'568 568 568 568','Gid':'568 568 568 568','Groups':''}]
        assert argv[:3]==['midclt','call','filesystem.getacl'] and argv[-2:]==['false','true'];return acl
    info=SimpleNamespace(st_uid=568,st_gid=0,st_mode=0o40770,st_dev=1,st_ino=2,st_nlink=2)
    data=diagnostic.collect(run=run,inspect_path=lambda p:info)
    assert data['qualification']=='NOT_PERFORMED'
    assert data['web_credentials'][0]['Uid'].startswith('568')
    assert all(p['acl']==acl for p in data['paths'])
    assert 'SECRET' not in json.dumps(data)
    assert all('/kamera-arbeitsbereich' not in c[3] for c in calls if c[0]=='midclt')
    assert any(c[3].endswith('kamera.sqlite3-wal') for c in calls if c[0]=='midclt')
    assert any('.bibliothekar-root-control' in c[3] for c in calls if c[0]=='midclt')


@pytest.mark.parametrize('bad',['/','relative','/mnt/../etc'])
def test_unbounded_diagnostic_sources_are_rejected(bad):
    data=container();data['Mounts'][0]['Source']=bad
    with pytest.raises(ValueError):diagnostic.plan(data)


def test_overlap_with_workspace_is_explicitly_reported():
    data=container();data['Mounts'][0]['Source']='/mnt/apps/kamera-arbeitsbereich/database'
    roots,paths=diagnostic.plan(data)
    assert roots['/database']['inside_shared_workspace']
    assert not roots['/config']['inside_shared_workspace']


def test_symlink_ancestor_is_not_followed_by_diagnosis(tmp_path):
    target=tmp_path/'outside';target.mkdir();alias=tmp_path/'alias';alias.symlink_to(target)
    with pytest.raises(ValueError,match='Symlink'):diagnostic.plain_existing(alias/'file')


def test_missing_or_denied_paths_never_qualify_a_store():
    def run(argv):return [container()] if argv[:2]==['docker','inspect'] else []
    def denied(p):raise PermissionError('synthetic denied')
    data=diagnostic.collect(run=run,inspect_path=denied)
    assert data['qualification']=='NOT_PERFORMED'
    assert all('unqualified_reason' in p and 'acl' not in p for p in data['paths'])


def test_shared_stage_is_not_a_private_independent_security_domain(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    stage=ti.stage_parent(ws)/jid;stage.chmod(0o770)
    before=snapshot(fixture[0],fixture[4]/'before.json');raw=journal.read_bytes()
    result=tf.recover_failed_restores(db,ws)
    assert result[0]['status']=='blocked' and 'nicht privat' in result[0]['message']
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    with pytest.raises(main.HTTPException):main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert journal.read_bytes()==raw
    assert snapshot(fixture[0],fixture[4]/'after.json')['databases']==before['databases']


@pytest.mark.parametrize('attack',['copy-write','copy-remove','symlink','hardlink','rename-parent'])
def test_an_independent_permitted_writer_cannot_make_a_stale_copy_proof_safe(fixture,attack):
    # Separate process models a writer granted access by the reported ACEs.
    # It uses this host UID: it is NOT a native UID3001/NFSv4 kernel test.
    db,ws,jid,journal,data=failed_restore(fixture);stage=ti.stage_parent(ws)/jid
    rel=data['files'][0]['relative_path'];copy=stage/rel
    code={
      'copy-write':"from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b'foreign write')",
      'copy-remove':"import os,sys;os.unlink(sys.argv[1])",
      'symlink':"import os,sys;os.rename(sys.argv[1],sys.argv[1]+'.kept');os.symlink(sys.argv[1]+'.kept',sys.argv[1])",
      'hardlink':"import os,sys;os.link(sys.argv[1],sys.argv[1]+'.alias')",
      'rename-parent':"import os,sys;from pathlib import Path;p=Path(sys.argv[1]).parent;os.rename(p,str(p)+'.kept');p.mkdir()",
    }[attack]
    subprocess.run([sys.executable,'-I','-c',code,str(copy)],check=True,timeout=10)
    raw=journal.read_bytes();before=snapshot(fixture[0],fixture[4]/'after-attacker.json')
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    assert journal.read_bytes()==raw
    assert snapshot(fixture[0],fixture[4]/'after-attempt.json')['databases']==before['databases']


def test_existing_sqlite_fingerprint_can_bind_media_without_status_json(fixture,tmp_path):
    from app.folder_import import manifest_fingerprint
    from app.database import set_job_source_identity
    db,ws,jid,journal,data=failed_restore(fixture)
    expected=manifest_fingerprint(data['files'])
    set_job_source_identity(db,jid,source_signature='synthetic-signature',source_fingerprint=expected)
    for n in range(3):
        code="import sqlite3,sys,json;from pathlib import Path;c=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True);print(json.dumps(c.execute('SELECT state,source_fingerprint FROM jobs WHERE id=?',(sys.argv[2],)).fetchone()));c.close()"
        r=subprocess.run([sys.executable,'-I','-c',code,str(db),jid],check=True,capture_output=True,text=True,timeout=10)
        (tmp_path/f'fingerprint-reopen{n}.log').write_text(r.stdout)
        assert json.loads(r.stdout)==['failed',expected]
    forged=[dict(r) for r in data['files']];forged[0]['sha256']='0'*64
    assert manifest_fingerprint(forged)!=expected
    forged=[dict(r) for r in data['files']];forged[0]['relative_path']='foreign.JPG'
    assert manifest_fingerprint(forged)!=expected
    forged=[dict(r) for r in data['files']];forged[0]['size_bytes']+=1
    assert manifest_fingerprint(forged)!=expected
    # Fingerprint is a candidate anchor only if the database is actually private.
    # This test does not qualify the real NAS mount or release any reservation.
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])


def test_quick_signature_is_not_a_substitute_for_the_sha_fingerprint(tmp_path):
    from app.folder_import import quick_source_signature,manifest_fingerprint
    p=tmp_path/'A.JPG';p.write_bytes(b'AAAA');before=p.stat()
    signature=quick_source_signature(tmp_path)
    p.write_bytes(b'BBBB');os.utime(p,ns=(before.st_atime_ns,before.st_mtime_ns))
    assert quick_source_signature(tmp_path)==signature
    assert manifest_fingerprint([{'relative_path':'A.JPG','size_bytes':4,'sha256':'a'*64}])!=manifest_fingerprint([{'relative_path':'A.JPG','size_bytes':4,'sha256':'b'*64}])
