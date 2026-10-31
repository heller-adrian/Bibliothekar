"""Synthetic private retention; NFS4 XDR models are not a native NAS test."""
import hashlib,json,os,signal,struct,subprocess,sys,time
from pathlib import Path
import pytest
from app import trash_failure as tf,trash_failure_private as private,trash_retention as rt,trash_import as ti,main
from app.database import database_connection,set_job_source_identity
from app.folder_import import manifest_fingerprint
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import snapshot
from tests.backend.test_rc4_practice import protocol_failure


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    from app.library_registry import initialize_library_registry,register_library,ensure_library_identity
    from app.library_context import resolve_library_context
    from app.database import initialize_database
    from app.storage_config import LEGACY_STORAGE_DEFAULTS
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir()
    private=case/'database';private.mkdir(mode=0o700);reg=private/'registry.sqlite3'
    settings=private/'settings.json';settings.write_text('{}')
    for key,value in {'KAMERA_WORKSPACE':ws,'KAMERA_CONFIG':settings,'KAMERA_REGISTRY_DATABASE':reg}.items():monkeypatch.setenv(key,str(value))
    for name in LEGACY_STORAGE_DEFAULTS.values():(ws/name).mkdir(exist_ok=True)
    # Known complete installation: fixed General/Batch administration anchors
    # already exist before any historical reservation or failure is published.
    from app.managed_directory_names import directory_name
    metadata=storage_paths(ws)['metadata_root']
    for kind in ('metadata_general','metadata_multiple'):
        (metadata/directory_name(metadata,kind)).mkdir(exist_ok=True)
    initialize_library_registry(reg);dbs=[]
    for lid in ['main','second']:
        db=private/(lid+'.sqlite3');initialize_database(db);ensure_library_identity(db,lid);dbs.append(db)
        work=storage_paths(ws)['workspaces_root']/lid;work.mkdir();archive=case/('archive-'+lid);archive.mkdir()
        (work/'original.JPG').write_bytes(b'synthetic-'+lid.encode())
        register_library(reg,library_id=lid,display_name=lid,database_path=db,workspace_root=ws,work_root=work,archive_root=archive,is_main=lid=='main')
    ctx=resolve_library_context(reg,'main')
    for key,value in {'WORKSPACE_PATH':ws,'DATABASE_FILE':dbs[0],'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':settings,'MAIN_LIBRARY_CONTEXT':ctx}.items():monkeypatch.setattr(main,key,value)
    ev=tmp_path/'evidence';ev.mkdir();(case/'case.json').write_text(json.dumps({'db':str(dbs[0]),'workspace':str(ws)}))
    return case,ws,reg,dbs,ev


def anchored(fixture):
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    set_job_source_identity(db,jid,source_signature='synthetic',source_fingerprint=manifest_fingerprint(data['files']))
    for p in [incoming,incoming/'Protocol',status,ti.stage_parent(ws)/jid]:p.chmod(0o770)
    return db,ws,jid,journal,data,incoming,status


def xdr(entries):return struct.pack('!II',0,len(entries))+b''.join(struct.pack('!IIIII',*e) for e in entries)


def test_reported_status_only_is_finalized_into_private_bytes(fixture):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    old=journal.read_bytes();protocol=status.read_bytes();error=tf.describe_failures(db,ws)[0]
    with pytest.raises(tf.TrashError):tf._protocol_only_failure(incoming,ti.stage_parent(ws)/jid,jid)
    result=tf.recover_failed_restores(db,ws)[0]
    assert result['status']=='finalized',result
    assert not ti.protected_trash_paths(db,ws)
    receipt=private.recorded(db,ws,jid);location=Path(result['recovery_path'])
    assert not location.is_relative_to(ws)
    assert journal.read_bytes()==old and status.read_bytes()==protocol and status.stat().st_mode&0o777==0o770
    for item in data['files']:
        copy=location/'media'/item['relative_path'];original=storage_paths(ws)['trash_root']/item['relative_path']
        assert hashlib.sha256(copy.read_bytes()).hexdigest()==item['sha256']
        assert copy.stat().st_nlink==1 and copy.stat().st_ino!=original.stat().st_ino
    with database_connection(db) as c:
        row=c.execute('SELECT state,stage,error_message FROM jobs WHERE id=?',(jid,)).fetchone()
        assert tuple(row)==('failed','failed','Auf dieser SD-Karte wurden keine neuen Dateien gefunden. Alle Dateien wurden bereits erfolgreich gesichert.')
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert tf.validate_finalized(db,ws,jid) and all((location/'media'/r['relative_path']).is_file() for r in data['files'])
    assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'


@pytest.mark.parametrize('attack',['fingerprint','extra-stage','missing-stage','stage-write','original-write','missing-original','protocol','protocol-extra','symlink','hardlink-private','private-write','private-parent'])
def test_inconsistent_or_attacked_states_do_not_release(fixture,attack):
    db,ws,jid,journal,data,incoming,status=anchored(fixture);stage=ti.stage_parent(ws)/jid;first=data['files'][0]['relative_path'];original=storage_paths(ws)['trash_root']/first
    if attack in {'hardlink-private','private-write','private-parent'}:
        assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
        location=Path(private.recorded(db,ws,jid)['proof']['retention_path']);copy=location/'media'/first
        if attack=='hardlink-private':os.link(copy,location/'alias')
        if attack=='private-write':copy.write_bytes(b'bad')
        if attack=='private-parent':location.rename(location.with_name(location.name+'-old'));location.mkdir()
    elif attack=='fingerprint':set_job_source_identity(db,jid,source_signature='x',source_fingerprint='f'*64)
    elif attack=='extra-stage':(stage/'extra.JPG').write_bytes(b'extra')
    elif attack=='missing-stage':(stage/first).unlink()
    elif attack=='stage-write':(stage/first).write_bytes(b'foreign')
    elif attack=='original-write':original.write_bytes(b'foreign')
    elif attack=='missing-original':original.unlink()
    elif attack=='protocol':status.write_text('{}')
    elif attack=='protocol-extra':(incoming/'extra.JPG').write_bytes(b'extra')
    elif attack=='symlink':(stage/first).unlink();(stage/first).symlink_to(original)
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    with pytest.raises(main.HTTPException):main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert journal.exists() and status.exists()


@pytest.mark.parametrize('principal',[('USER',3001),('GROUP',545),('EVERYONE',3)])
def test_nfs4_foreign_writers_rejected_even_with_0700(tmp_path,monkeypatch,principal):
    folder=tmp_path/'private';folder.mkdir(mode=0o700)
    tag,who=principal;flags=0x40 if tag=='GROUP' else 0;special=1 if tag=='EVERYONE' else 0
    monkeypatch.setattr(rt,'_attributes',lambda fd:{rt.NFS4[0]:xdr([(0,flags,special,rt.WRITE,who)])})
    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
    try:
        with pytest.raises(tf.TrashError,match='Fremde'):rt.check_acl(fd,{0,os.geteuid(),3000})
    finally:os.close(fd)


def test_reported_private_nfs4_acl_allows_admins_but_not_shared_workspace(tmp_path,monkeypatch):
    # Explicit model of the reported trust roles; no claim of a kernel NFS4 ACL.
    folder=tmp_path/'private';folder.mkdir(mode=0o770)
    entries=[(0,0,0,rt.WRITE,u) for u in [os.geteuid(),3000]]+[(0,0,0,0x200a0,3001)]
    monkeypatch.setattr(rt,'_attributes',lambda fd:{rt.NFS4[0]:xdr(entries)})
    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
    try:assert rt.check_acl(fd,{0,os.geteuid(),3000})['acl_sha256']
    finally:os.close(fd)


@pytest.mark.parametrize('point',['retention_writing','retention_copied','private_before_db_commit','private_db_committed'])
def test_private_retention_real_sigkill_and_three_independent_restarts(fixture,point):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    if point=='retention_writing':
        rel=data['relative_paths'][0];raw=b'partial-copy-test'*150000
        for root in [ti.stage_parent(ws)/jid,storage_paths(ws)['trash_root']]:(root/rel).write_bytes(raw)
        next(r for r in data['files'] if r['relative_path']==rel).update(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        journal.write_text(json.dumps(data));set_job_source_identity(db,jid,source_signature='synthetic',source_fingerprint=manifest_fingerprint(data['files']))
    case=fixture[0]/'case.json';v=json.loads(case.read_text());v.update(job_id=jid,error='Auf dieser SD-Karte wurden keine neuen Dateien gefunden. Alle Dateien wurden bereits erfolgreich gesichert.');case.write_text(json.dumps(v))
    marker=fixture[4]/'pause';script=Path('qa/rc4-practice/failure_worker.py').absolute()
    p=subprocess.Popen([sys.executable,str(script),str(case),point,str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+25
        while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.03)
        assert marker.exists(),p.communicate(timeout=5)
        if point=='retention_writing':
            private_files=list((db.parent/'.bibliothekar-restore-retention').rglob(data['relative_paths'][0]))
            assert any(0<f.stat().st_size<len(raw) for f in private_files)
            assert not private.recorded(db,ws,jid)
        os.kill(p.pid,signal.SIGKILL);p.communicate(timeout=10);assert p.returncode==-signal.SIGKILL
    finally:
        if p.poll() is None:p.kill();p.communicate()
    for i in range(3):
        r=subprocess.run([sys.executable,str(script),str(case),'none',str(marker)],capture_output=True,text=True,timeout=90)
        (fixture[4]/f'restart-{point}-{i}.log').write_text(r.stdout+r.stderr)
        assert r.returncode==0,r.stdout+r.stderr
    assert tf.validate_finalized(db,ws,jid)
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==1
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


def test_foreign_acl_and_low_capacity_block_before_receipt(fixture,monkeypatch):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    original=rt._attributes
    def broad(fd):
        if os.fstat(fd).st_ino==db.parent.stat().st_ino:return {rt.NFS4[0]:xdr([(0,0,0,rt.WRITE,3001)])}
        return original(fd)
    with monkeypatch.context() as patch:
        patch.setattr(rt,'_attributes',broad)
        assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    from types import SimpleNamespace
    monkeypatch.setattr(os,'fstatvfs',lambda fd:SimpleNamespace(f_bavail=0,f_frsize=4096))
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert not private.recorded(db,ws,jid)


@pytest.mark.parametrize('anchor',[None,manifest_fingerprint([])])
def test_missing_anchor_requires_explicit_rescue_and_preserves_different_variants(fixture,anchor):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    with database_connection(db) as c:c.execute('UPDATE jobs SET source_fingerprint=? WHERE id=?',(anchor,jid))
    rel=data['relative_paths'][0];stage=ti.stage_parent(ws)/jid
    (stage/rel).write_bytes(b'other preserved variant')
    old_journal=journal.read_bytes();old_status=status.read_bytes()
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert tf.describe_failures(db,ws)[0]['rescue_available']
    from app import root_operations as ro
    operation=next(ro._control_location(ws).glob('operation-*.json'));original=ro._read(operation)
    with pytest.raises(main.HTTPException) as e:main.api_finalize_trash_failure(jid,{'confirmation':'yes'})
    assert e.value.status_code==422
    assert ro._read(operation)==original
    result=main.api_finalize_trash_failure(jid,{'confirmation':'RETAIN_ALL_FAILED_RESTORE_VARIANTS'})
    assert not operation.exists()
    parent=operation.parent;nonce=original['reservation_id']
    completed=ro._read(parent/('domain-recovery-'+nonce+'.json'))
    assert completed['reservation']==original and completed['disposition']=='confirmed_all_current_variants_retained_error_preserved'
    decision=ro._read(parent/('domain-rescue-decision-'+nonce+'.json'))
    assert decision=={'format':1,'reservation':original,'confirmation':'RETAIN_ALL_FAILED_RESTORE_VARIANTS'}
    proof=private.recorded(db,ws,jid)['proof'];location=Path(result['recovery_path'])/'media'
    assert proof['mode']=='confirmed-current-variants' and proof['source_fingerprint']==anchor
    assert (location/'staging'/rel).read_bytes()==b'other preserved variant'
    assert (location/'trash'/rel).read_bytes()==(storage_paths(ws)['trash_root']/rel).read_bytes()
    assert journal.read_bytes()==old_journal and status.read_bytes()==old_status
    assert not ti.protected_trash_paths(db,ws)
    main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert tf.validate_finalized(db,ws,jid) and (stage/rel).read_bytes()==b'other preserved variant'


@pytest.mark.parametrize('case',['missing-both','catalogue','anchored-mismatch','shared-private-acl'])
def test_confirmed_rescue_never_bypasses_missing_media_catalogue_or_private_boundary(fixture,monkeypatch,case):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    if case!='anchored-mismatch':
        with database_connection(db) as c:c.execute('UPDATE jobs SET source_fingerprint=NULL WHERE id=?',(jid,))
    if case=='anchored-mismatch':(ti.stage_parent(ws)/jid/data['relative_paths'][0]).write_bytes(b'bad')
    if case=='missing-both':
        (ti.stage_parent(ws)/jid/data['relative_paths'][0]).unlink()
        (storage_paths(ws)['trash_root']/data['relative_paths'][0]).unlink()
    if case=='catalogue':
        with database_connection(db) as c:c.execute('INSERT INTO file_families(job_id,family_key) VALUES (?,?)',(jid,'partial'))
    if case=='shared-private-acl':monkeypatch.setattr(rt,'_attributes',lambda fd:{rt.NFS4[0]:xdr([(0,0,0,rt.WRITE,3001)])})
    with pytest.raises(main.HTTPException):main.api_finalize_trash_failure(jid,{'confirmation':'RETAIN_ALL_FAILED_RESTORE_VARIANTS'})
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    assert not private.recorded(db,ws,jid)


@pytest.mark.parametrize('attack',['stage-write','rename-parent','journal','protocol'])
def test_separate_permitted_writer_between_copy_and_commit_never_releases(fixture,monkeypatch,attack):
    db,ws,jid,journal,data,incoming,status=anchored(fixture);stage=ti.stage_parent(ws)/jid
    target={'stage-write':stage/data['relative_paths'][0],'rename-parent':stage,'journal':journal,'protocol':status}[attack]
    ran=[]
    def checkpoint(point):
        if point!='retention_copied' or ran:return
        ran.append(True)
        code="import sys;from pathlib import Path;p=Path(sys.argv[1]);p.write_bytes(b'foreign mutation')"
        if attack=='rename-parent':code="import sys;from pathlib import Path;p=Path(sys.argv[1]);p.rename(p.with_name(p.name+'-kept'));p.mkdir()"
        subprocess.run([sys.executable,'-I','-c',code,str(target)],check=True,timeout=10)
    monkeypatch.setattr(tf,'checkpoint',checkpoint)
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert ran and not private.recorded(db,ws,jid)
    if attack!='journal':assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    else:
        with pytest.raises(tf.TrashError):ti.protected_trash_paths(db,ws)
    assert all((storage_paths(ws)['trash_root']/r['relative_path']).read_bytes()==('original '+Path(r['relative_path']).suffix[1:]).encode() for r in data['files'])


def test_sqlite_rollback_does_not_release_or_change_failed_history(fixture,monkeypatch):
    import sqlite3
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    def fail(point):
        if point=='private_before_db_commit':raise sqlite3.OperationalError('synthetic commit failure')
    monkeypatch.setattr(tf,'checkpoint',fail)
    result=tf.recover_failed_restores(db,ws)[0];assert result['status']=='blocked' and 'synthetic commit failure' in result['message']
    assert not private.recorded(db,ws,jid) and ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==0
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


def test_malformed_and_unreadable_acls_are_never_posix_permission_proofs(tmp_path,monkeypatch):
    path=tmp_path/'p';path.mkdir(mode=0o700);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        for attrs in [{rt.NFS4[0]:b'bad'},{'system.posix_acl_access':b'unknown'},{rt.NFS4[0]:xdr([(0,0,0,rt.WRITE,3001)])}]:
            monkeypatch.setattr(rt,'_attributes',lambda fd,attrs=attrs:attrs)
            with pytest.raises(tf.TrashError):rt.check_acl(fd,{0,os.geteuid()})
        def deny(fd):raise PermissionError('synthetic ACL read denied')
        monkeypatch.setattr(rt,'_attributes',deny)
        with pytest.raises(PermissionError):rt.check_acl(fd,{0,os.geteuid()})
    finally:os.close(fd)


def test_finalized_failure_cannot_reenter_success_cleanup_or_prepare(fixture):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
    with pytest.raises(tf.TrashError):ti.cleanup_successful_trash_import(ws,jid,data['files'])
    with pytest.raises(tf.TrashError):ti.prepare_queued_trash_restore(db,fixture[3],ws,jid)
    assert all((ti.stage_parent(ws)/jid/r['relative_path']).exists() for r in data['files'])
    assert all((storage_paths(ws)['trash_root']/r['relative_path']).exists() for r in data['files'])


def test_private_parallel_completion_and_concurrent_delete(fixture,tmp_path):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    case=tmp_path/'parallel.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'job_id':jid,'error':'Auf dieser SD-Karte wurden keine neuen Dateien gefunden. Alle Dateien wurden bereits erfolgreich gesichert.'}))
    from app import root_operations as ro
    with ro.reserve(ws,library_id='main',database=db,kind='trash'):pass
    marker=tmp_path/'release';worker=Path('qa/rc4-practice/failure_worker.py').absolute()
    cmd=[sys.executable,str(worker),str(case),'recover',str(marker)]
    processes=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    try:
        deadline=time.monotonic()+20
        while not all(Path(str(marker)+'.'+str(p.pid)).exists() for p in processes) and time.monotonic()<deadline:time.sleep(.02)
        assert all(Path(str(marker)+'.'+str(p.pid)).exists() for p in processes)
        marker.write_text('release');values=[]
        for i,p in enumerate(processes):
            out,err=p.communicate(timeout=45);(fixture[4]/f'parallel-{i}.log').write_text(out+err)
            assert p.returncode==0,out+err;values.append(json.loads(out)['result'])
        assert any(r['status']=='finalized' for r in values)
        with database_connection(db) as c:assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==1
        assert tf.validate_finalized(db,ws,jid)
    finally:
        for p in processes:
            if p.poll() is None:p.kill();p.communicate()


def test_delete_cannot_cross_uncommitted_retention(fixture,monkeypatch):
    db,ws,jid,journal,data,incoming,status=anchored(fixture);seen=[]
    def boundary(point):
        if point=='retention_copied':
            seen.append(point)
            assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
            with pytest.raises(main.HTTPException):main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    monkeypatch.setattr(tf,'checkpoint',boundary)
    assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
    assert seen and not ti.protected_trash_paths(db,ws)


def test_media_called_evidence_json_is_not_overwritten_by_receipt(fixture):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    name='evidence.json';original=b'synthetic nonmedia preserved in full manifest'
    (ti.stage_parent(ws)/jid/name).write_bytes(original);(storage_paths(ws)['trash_root']/name).write_bytes(original)
    data['files'].append({'relative_path':name,'sha256':hashlib.sha256(original).hexdigest(),'size_bytes':len(original)})
    data['relative_paths'].append(name);journal.write_text(json.dumps(data))
    set_job_source_identity(db,jid,source_signature='synthetic',source_fingerprint=manifest_fingerprint(data['files']))
    result=tf.recover_failed_restores(db,ws)[0];assert result['status']=='finalized',result
    assert (Path(result['recovery_path'])/'media'/name).read_bytes()==original
    assert json.loads((Path(result['recovery_path'])/'evidence.json').read_text())['job_id']==jid


@pytest.mark.parametrize('value',[[],{},'invalid',{'lifecycle':[]}])
def test_anchored_malformed_status_is_blocked_without_unhandled_startup_error(fixture,monkeypatch,value):
    db,ws,jid,journal,data,incoming,status=anchored(fixture);status.write_text(json.dumps(value))
    result=tf.recover_failed_restores(db,ws)[0];assert result['status']=='blocked'
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    assert not private.recorded(db,ws,jid)


@pytest.mark.parametrize('kind',['audit-missing','audit-conflict','result-malformed'])
def test_inconsistent_private_sqlite_evidence_cannot_authorize_delete(fixture,kind):
    db,ws,jid,journal,data,incoming,status=anchored(fixture)
    assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
    with database_connection(db) as c:
        if kind=='audit-missing':c.execute("DELETE FROM audit_log WHERE job_id=? AND action='trash_restore_failed_finalized'",(jid,))
        if kind=='audit-conflict':c.execute("UPDATE audit_log SET details_json='{}' WHERE job_id=? AND action='trash_restore_failed_finalized'",(jid,))
        if kind=='result-malformed':c.execute("UPDATE jobs SET result_json='[]' WHERE id=?",(jid,))
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    with pytest.raises((main.HTTPException,tf.TrashError)):main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
    assert all((storage_paths(ws)['trash_root']/r['relative_path']).exists() for r in data['files'])


@pytest.mark.parametrize('confirmation',[None,[],{},True,'YES'])
def test_invalid_confirmation_never_starts_rescue(fixture,monkeypatch,confirmation):
    db,ws,jid,journal,data,incoming,status=anchored(fixture);raw=journal.read_bytes();calls=[]
    monkeypatch.setattr(tf,'rescue_failure',lambda *a:calls.append(a))
    with pytest.raises(main.HTTPException) as e:main.api_finalize_trash_failure(jid,{'confirmation':confirmation})
    assert e.value.status_code==422 and not calls and journal.read_bytes()==raw
    assert not private.recorded(db,ws,jid)


def test_actual_worker_failure_after_persisted_identity_auto_finalizes(fixture,monkeypatch):
    from app.database import claim_next_job,get_job
    import app.folder_import as fi
    case,ws,reg,dbs,ev=fixture;db=dbs[0];root=storage_paths(ws)['trash_root']
    for ext in ['JPG','RAF']:(root/('worker.'+ext)).write_bytes(('worker original '+ext).encode())
    queued=ti.queue_trash_restore(db,ws,['worker.JPG','worker.RAF']);jid=queued['job_id']
    monkeypatch.setattr(main,'LOG_PATH',case/'logs');monkeypatch.setattr(main,'POOL_PROBE_PATH',ws)
    monkeypatch.setattr(main,"load_settings",
                        lambda:{"storage":{"processing_buffer_percent":0,
                                           "safety_reserve_gib":0}})
    def fail(*args,**kwargs):
        job=get_job(db,jid);assert private.has_anchor(job['source_fingerprint'])
        (ti.stage_parent(ws)/jid).chmod(0o770)
        raise fi.PipelineError('Synthetic failure after persisted source identity')
    monkeypatch.setattr(fi,'partition_import_entries',fail)
    job=claim_next_job(db);assert job['id']==jid
    main.process_claimed_job(job,library_context=main.MAIN_LIBRARY_CONTEXT)
    result=get_job(db,jid)
    assert result['state']=='failed' and result['error_message']=='Synthetic failure after persisted source identity'
    assert private.recorded(db,ws,jid) and tf.validate_finalized(db,ws,jid)
    assert not ti.protected_trash_paths(db,ws)
    assert all((root/('worker.'+ext)).read_bytes()==('worker original '+ext).encode() for ext in ['JPG','RAF'])


def test_posix_default_acl_only_on_existing_ancestor_never_qualifies_creation_parent(tmp_path,monkeypatch):
    path=tmp_path/'p';path.mkdir(mode=0o700);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        monkeypatch.setattr(rt,'_attributes',lambda fd:{'system.posix_acl_default':b'existing parent inheritance only'})
        assert rt.check_acl(fd,{0,os.geteuid()},existing_ancestor=True)
        with pytest.raises(tf.TrashError):rt.check_acl(fd,{0,os.geteuid()})
        path.chmod(0o777)
        with pytest.raises(tf.TrashError):rt.check_acl(fd,{0,os.geteuid()},existing_ancestor=True)
        path.chmod(0o700)
        monkeypatch.setattr(rt,'_attributes',lambda fd:{'system.posix_acl_access':b'access must not be ignored'})
        with pytest.raises(tf.TrashError):rt.check_acl(fd,{0,os.geteuid()},existing_ancestor=True)
    finally:os.close(fd)
