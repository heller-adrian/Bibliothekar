"""RC11 isolated evidence/security tests. Native ACL byte fixtures are synthetic;
real RO mounts, Linux HTTP and UID 568 are exercised by qa/rc11/container.py.
"""
from contextlib import closing
import base64
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import struct
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from app import root_operations as ro
from app import private_storage_security as security
from app import storage_bootstrap as bootstrap
from app import storage_admin
from app.managed_storage_health import inspect_storage
from app.storage_config import ENGLISH_STORAGE_DEFAULTS as NAMES
from app.database import initialize_database, create_job
from app.library_registry import initialize_library_registry


@pytest.fixture
def case(tmp_path, monkeypatch):
    for name in ('workspace','database','config','archive','logs'):
        (tmp_path/name).mkdir()
    paths = {'KAMERA_WORKSPACE':'workspace','KAMERA_DATABASE_DIR':'database',
             'KAMERA_REGISTRY_DATABASE':'database/bibliothekar-global.sqlite3',
             'KAMERA_CONFIG':'config/settings.json','KAMERA_ARCHIVE_ROOT':'archive','KAMERA_LOG_DIR':'logs'}
    for key, value in paths.items(): monkeypatch.setenv(key, str(tmp_path/value))
    monkeypatch.setenv('KAMERA_SOURCE_HELPER_ENABLED','false')
    (tmp_path/'workspace/.DS_Store').write_bytes(b'Finder metadata')
    (tmp_path/'archive/photo.JPG').write_bytes(b'original independent archive')
    return tmp_path


def legacy(case, *, completed=False):
    template = json.loads((Path(__file__).parents[1]/'fixtures/rc11/truenas-rc10.json').read_text())
    assert template['operation_name'] == 'operation-'+bootstrap.key_for(template['operation'])+'.json'
    root=case/'workspace'; db=case/'database/kamera.sqlite3'
    for name in NAMES.values(): (root/name).mkdir(exist_ok=True)
    meta=root/'Metadata Correction'; (meta/'.trash-deletions').mkdir(exist_ok=True)
    lock=meta/'.trash-deletions/.lock'; lock.write_bytes(b''); lock.chmod(0o770)
    for name in ('General','Batch Correction'): (meta/name).mkdir(exist_ok=True)
    state, operation = copy.deepcopy(template['state']), copy.deepcopy(template['operation'])
    bindings={str(root):ro._identity(root), **{str(root/n):ro._identity(root/n) for n in NAMES.values()}}
    state.update(workspace=bindings[str(root)],bindings=bindings)
    state['storage_initialization']['database']=str(db)
    if completed: state['storage_initialization']['phase']='completed'
    operation.update(workspace=str(root),database=str(db),bindings=bindings)
    _, parent=ro._control(root)
    ro._write(parent/'state.json',state)
    op=parent/('operation-'+bootstrap.key_for(operation)+'.json');ro._write(op,operation)
    (case/'config/settings.json').write_text('{}')
    initialize_database(db);initialize_library_registry(case/'database/bibliothekar-global.sqlite3')
    return root,db,parent,state,operation,lock


def adopt(root,db):
    check=storage_admin.inspect(root,db)
    return storage_admin.adopt(root,db,check['token'],bootstrap.CONFIRMATION,'synthetic consistent backup')


def xdr(entries):
    return struct.pack('!II',2,len(entries))+b''.join(struct.pack('!IIIII',*row) for row in entries)


@pytest.mark.parametrize('entry',[
    (0,0,0,security.WRITE,3000),(0,0,0,security.WRITE,3001),
    (0,0x40,0,security.WRITE,568),(0,0,1,security.WRITE,3),
    (0,0x09,0,security.WRITE,3000),(0,0x80,0,security.WRITE,3000),
    (0,0,0,0x40,3000),(0,0,0,0x40000,3000),(0,0,0,0x80000,3000),
])
def test_native_acl_rejects_foreign_writes_despite_0700(case,entry):
    p=case/'database/state.json';p.write_text('{}');p.chmod(0o700)
    fd=os.open(p,os.O_RDONLY)
    try:
        with pytest.raises(security.PrivateStorageError,match='private_acl_untrusted_write') as error:
            security.check_acl(fd,{0,os.geteuid()},path=p,reader=lambda fd:{security.NFS4[0]:xdr([entry])})
        assert str(p) in str(error.value) and 'ACE 0' in str(error.value)
    finally:os.close(fd)


def test_native_acl_owner_admin_and_read_only_foreign_entries(case):
    p=case/'database/state.json';p.write_text('{}')
    fd=os.open(p,os.O_RDONLY)
    try:
        entries=[(0,0,1,security.WRITE,1),(0,0x40,0,security.WRITE,544),(0,0,0,1,3000)]
        assert security.check_acl(fd,{0,os.geteuid()},reader=lambda fd:{security.NFS4[0]:xdr(entries)})['acl_sha256']
    finally:os.close(fd)


@pytest.mark.parametrize('raw',[b'',struct.pack('!II',2,0),xdr([(99,0,0,2,3000)]),xdr([(0,0,1,2,99)]),xdr([(0,0x100,0,2,3000)])])
def test_unknown_native_acl_is_never_posix_success(case,raw):
    p=case/'database/state';p.write_text('{}');fd=os.open(p,os.O_RDONLY)
    try:
        with pytest.raises(security.PrivateStorageError):security.check_acl(fd,{0,os.geteuid()},reader=lambda fd:{security.NFS4[0]:raw})
    finally:os.close(fd)


def test_unreadable_zfs_acl_cannot_fall_back_to_mode(case,monkeypatch):
    monkeypatch.setattr(security,'sys',SimpleNamespace(platform='linux'))
    monkeypatch.setattr(security,'filesystem',lambda fd:'zfs')
    monkeypatch.setattr(os,'listxattr',lambda fd:[],raising=False)
    def absent(*a,**kw):raise OSError(errno.ENODATA,'native ACL absent')
    monkeypatch.setattr(os,'getxattr',absent,raising=False)
    fd=os.open(case/'database',os.O_RDONLY)
    try:
        with pytest.raises(security.PrivateStorageError,match='acl_backend_unavailable'):
            security.check_acl(fd,{0,os.geteuid()},path=case/'database')
    finally:os.close(fd)


def test_private_parent_replacement_and_foreign_write_rejected(case):
    parent=case/'database/private';parent.mkdir();p=parent/'state';p.write_text('{}')
    with pytest.raises(security.PrivateStorageError,match='private_identity_changed'):
        with security.qualified(p) as (_,check):
            parent.rename(case/'database/old-private');parent.mkdir();p.write_text('{}');check()
    parent.chmod(0o777)
    with pytest.raises(security.PrivateStorageError,match='private_acl_untrusted_write'):
        with security.qualified(p):pass


def test_real_template_requires_explicit_review_and_preserves_original_bytes(case):
    root,db,parent,state,operation,lock=legacy(case)
    before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    health=inspect_storage(root,database=db)
    assert not health['can_initialize']
    assert any(i['code']=='bootstrap_administrative_review_required' for i in health['issues'])
    accepted=adopt(root,db)
    for name,data in before.items():assert (parent/name).read_bytes()==data
    receipt=ro._read(Path(accepted['receipt']))
    assert base64.b64decode(receipt['material']['state'])==before['state.json']
    assert receipt['material']['operation']==base64.b64encode(before['operation-'+bootstrap.key_for(operation)+'.json']).decode()
    assert receipt['legacy_lock']['mode']==0o770
    assert inspect_storage(root,database=db)['can_initialize']
    bootstrap.prepare_control(root,db)
    migrated=ro._read(parent/'state.json')
    assert migrated['format']==2 and migrated['bindings']==state['bindings']
    assert migrated['generation']==0
    assert migrated['storage_initialization']['reservation_id']==operation['reservation_id']
    assert lock.stat().st_mode & 0o777 == 0o770 and lock.read_bytes()==b''
    bootstrap.prepare_control(root,db)
    assert ro._read(parent/'state.json')==migrated


@pytest.mark.parametrize('conflict',['library_generation','extra_operation','retention','job','media_sequence','registry_history','changed_inode','changed_key','changed_reservation','unknown_file','symlink','config_library','journal'])
def test_history_blocks_resume_even_after_adoption(case,conflict):
    root,db,parent,state,operation,lock=legacy(case);adopt(root,db)
    if conflict=='library_generation':state['libraries']['retired']=3;ro._write(parent/'state.json',state)
    elif conflict=='extra_operation':ro._write(parent/'operation-other.json',{'kind':'import','preserve':True})
    elif conflict=='retention':
        p=db.parent/'.bibliothekar-restore-retention';p.mkdir();(p/'original.JPG').write_bytes(b'protected')
    elif conflict=='job':create_job(db,job_id='PRESERVE',source_path='synthetic',working_path=str(root),kind='sd_import',trigger_type='manual',operation='folder_import')
    elif conflict=='media_sequence':
        with sqlite3.connect(db) as c:c.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('files',7)")
    elif conflict=='registry_history':
        with sqlite3.connect(case/'database/bibliothekar-global.sqlite3') as c:c.execute("INSERT INTO canonical_families VALUES ('used','fingerprint','now','now')")
    elif conflict=='changed_inode':(root/'Trash').rename(case/'preserved-trash');(root/'Trash').mkdir()
    elif conflict=='changed_key':(parent/('operation-'+bootstrap.key_for(operation)+'.json')).rename(parent/'operation-wrong.json')
    elif conflict=='changed_reservation':operation['reservation_id']='f'*32;ro._write(parent/('operation-'+bootstrap.key_for(operation)+'.json'),operation)
    elif conflict=='unknown_file':(root/'unknown.JPG').write_bytes(b'protected')
    elif conflict=='symlink':(root/'unknown').symlink_to(case/'archive',target_is_directory=True)
    elif conflict=='config_library':(case/'config/settings.json').write_text('{"library":{"name":"prior"}}')
    elif conflict=='journal':(root/'Metadata Correction/.trash-deletions/DELETE_unknown.json').write_text('{"preserve":true}')
    before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    health=inspect_storage(root,database=db);assert not health['can_initialize'],health
    assert before=={p.name:p.read_bytes() for p in parent.glob('*.json')}
    with pytest.raises(ro.RootOperationError):bootstrap.prepare_control(root,db)


def test_token_rechecks_catalogue_changes_and_backup_confirmation(case):
    root,db,*_=legacy(case);checked=storage_admin.inspect(root,db)
    with pytest.raises(ro.RootOperationError):storage_admin.adopt(root,db,checked['token'],'wrong','backup')
    with pytest.raises(ro.RootOperationError):storage_admin.adopt(root,db,checked['token'],bootstrap.CONFIRMATION,'')
    create_job(db,job_id='PRESERVE',source_path='synthetic',working_path=str(root),kind='sd_import',trigger_type='manual',operation='folder_import')
    with pytest.raises(ro.RootOperationError):storage_admin.adopt(root,db,checked['token'],bootstrap.CONFIRMATION,'backup')


def child(case,output,boundary='none',*,paused=False):
    output.mkdir();log=(output/'process.log').open('w')
    proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('rc11_bootstrap_worker.py')),str(case),str(output),boundary],env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    if paused:
        until=time.monotonic()+40
        while proc.poll() is None and time.monotonic()<until:
            if (output/'checkpoint.json').exists():return proc,log
            time.sleep(.02)
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close();raise AssertionError((output/'process.log').read_text())
    try:assert proc.wait(timeout=50)==0,(output/'process.log').read_text()
    finally:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close()
    return json.loads((output/'result.json').read_text())


@pytest.mark.parametrize('boundary',['reservation','folders','config','database','registry','recovery','private-lock','prepared','completion-receipt','completed','operation-archive','finished-receipt','operation-unlink','uncommitted-state'])
def test_sigkill_same_reservation_and_following_mutation(case,boundary):
    proc,log=child(case,case/'killed',boundary,paused=True)
    try:os.killpg(proc.pid,signal.SIGKILL);assert proc.wait(timeout=10)==-9
    finally:log.close()
    parent=ro._control_location(case/'workspace');state=ro._read(parent/'state.json')
    nonce=state['storage_initialization']['reservation_id'];bindings=dict(state['bindings'])
    result=child(case,case/'resumed')
    assert result['ready'] and result['onboarding'] and result['error'] is None,result
    assert result['reservation_id']==nonce and result['mutation_succeeded']
    assert not result['active_operations'] and result['archive_unchanged'] and not result['workspace_lock_created']
    for path,identity in bindings.items():assert result['bindings'][path]==identity
    again=child(case,case/'again');assert again['ready'] and again['reservation_id']==nonce and again['mutation_succeeded'],again


@pytest.mark.parametrize('boundary',['adoption-receipt','control-format','completed'])
def test_legacy_migration_crash_preserves_source_and_can_finish(case,boundary):
    root,db,parent,state,operation,lock=legacy(case,completed=boundary=='completed')
    if boundary!='adoption-receipt':adopt(root,db)
    original_state=raw=bootstrap.raw_file(parent/'state.json')
    proc,log=child(case,case/'killed',boundary,paused=True)
    try:os.killpg(proc.pid,signal.SIGKILL);assert proc.wait(timeout=10)==-9
    finally:log.close()
    result=child(case,case/'resumed')
    assert result['ready'] and result['mutation_succeeded'] and result['reservation_id']==operation['reservation_id'],result
    assert result['bindings']==state['bindings'] and lock.stat().st_mode & 0o777==0o770
    receipts=[ro._read(p) for p in parent.glob('rc11-adoption-*.json')]
    assert any(r['material']['state']==original_state for r in receipts)


def test_synthetic_security_namespace_is_not_kernel_authority(case,monkeypatch):
    monkeypatch.setattr(security,'sys',SimpleNamespace(platform='linux'))
    monkeypatch.setattr(security,'filesystem',lambda fd:'ext4')
    monkeypatch.setattr(os,'listxattr',lambda fd:[security.NFS4[1]],raising=False)
    def attrs(fd,name):
        if name==security.NFS4[1]:return xdr([(0,0,1,security.WRITE,1)])
        raise OSError(errno.ENODATA,'absent')
    monkeypatch.setattr(os,'getxattr',attrs,raising=False)
    fd=os.open(case/'database',os.O_RDONLY)
    try:
        with pytest.raises(security.PrivateStorageError,match='acl_backend_unavailable'):
            security.check_acl(fd,{0,os.geteuid()})
    finally:os.close(fd)


def test_completion_requires_actual_schemas_and_version_identity(case):
    from app import main, __version__
    assert main.APP_VERSION==main.RELEASE_VERSION==main.DEPLOYMENT_VERSION==__version__=='1.0.0-rc.11'
    root=case/'workspace';db=case/'database/kamera.sqlite3'
    for n in NAMES.values():(root/n).mkdir()
    (case/'config/settings.json').write_text('{}')
    with pytest.raises(ro.RootOperationError,match='bootstrap_database_not_prepared'):
        with ro.reserve(root,library_id='main',paths=[root,*(root/n for n in NAMES.values())],database=db,kind='startup',ids={'initialize_storage':True}) as record:
            bootstrap.complete(root,record)
    state=ro._read(ro._control_location(root)/'state.json')
    assert state['storage_initialization']['phase']=='initializing'


def test_established_format1_requires_control_adoption_without_workspace_lock(case):
    root=case/'workspace';db=case/'database/kamera.sqlite3'
    for n in NAMES.values():(root/n).mkdir()
    _,parent=ro._control(root)
    state={'format':1,'workspace':ro._identity(root),'generation':3,'libraries':{'historic':2},'bindings':{str(root):ro._identity(root)},'storage_names':dict(NAMES)}
    ro._write(parent/'state.json',state);initialize_database(db);initialize_library_registry(case/'database/bibliothekar-global.sqlite3')
    with pytest.raises(ro.RootOperationError,match='control_administrative_review_required'):bootstrap.prepare_control(root,db)
    checked=storage_admin.inspect(root,db,scope='control')
    storage_admin.adopt(root,db,checked['token'],bootstrap.CONFIRMATION,'synthetic complete established backup',scope='control')
    bootstrap.prepare_control(root,db)
    migrated=ro._read(parent/'state.json')
    assert migrated['generation']==3 and migrated['libraries']=={'historic':2} and migrated['bindings']==state['bindings']
    assert migrated['format']==2


def test_missing_control_state_never_switches_legacy_lock_authority(case):
    root=case/'workspace';db=case/'database/kamera.sqlite3'
    lock=root/'Metadata Correction/.trash-deletions/.lock'
    lock.parent.mkdir(parents=True);lock.write_bytes(b'');lock.chmod(0o770)
    _,parent=ro._control(root)
    with pytest.raises(ro.RootOperationError,match='legacy_lock_without_control_state'):
        bootstrap.prepare_control(root,db)
    with pytest.raises(ro.RootOperationError,match='legacy_lock_without_control_state'):
        ro._state(parent,root)
    from app.trash_selective import _operation_lock
    with pytest.raises(ro.RootOperationError,match='legacy_lock_without_control_state'):
        with _operation_lock(root):pass
    assert not (parent/'state.json').exists() and not (parent/'trash-recovery.lock').exists()
    assert lock.read_bytes()==b'' and lock.stat().st_mode & 0o777==0o770


def test_missing_configuration_cannot_complete_bootstrap(case):
    root=case/'workspace';db=case/'database/kamera.sqlite3'
    initialize_database(db);initialize_library_registry(case/'database/bibliothekar-global.sqlite3')
    state={'storage_initialization':{'registry':str(case/'database/bibliothekar-global.sqlite3'),'names':dict(NAMES)},'bindings':{}}
    with pytest.raises(ro.RootOperationError,match='bootstrap_configuration_not_prepared'):
        bootstrap.technical_postconditions(root,db,state)


def test_workspace_scan_error_reports_actual_subdirectory(case,monkeypatch):
    target=case/'workspace/Metadata Correction';target.mkdir()
    real_listdir=os.listdir
    def failed(fd):
        if isinstance(fd,int) and os.fstat(fd).st_ino==target.stat().st_ino:
            raise PermissionError(errno.EACCES,'synthetic scan refusal')
        return real_listdir(fd)
    monkeypatch.setattr(os,'listdir',failed)
    result=bootstrap.tree(case/'workspace',NAMES)
    assert result['issues']==[{'code':'workspace_scan_error','path':str(target),'detail':'[Errno 13] synthetic scan refusal'}]


def test_malformed_configuration_reports_actual_path(case):
    root,db,parent,state,_,_=legacy(case)
    (case/'config/settings.json').write_text('{broken')
    with pytest.raises(ro.RootOperationError,match='configuration_invalid: '+str(case/'config/settings.json')):
        bootstrap.evidence(root,db,state,require_adoption=False)
    health=inspect_storage(root,database=db)
    assert health['issues'][0]['code']=='configuration_invalid'
    assert health['issues'][0]['path']==str(case/'config/settings.json')
