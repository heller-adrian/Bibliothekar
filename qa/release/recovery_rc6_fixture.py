"""Disposable container only: seed/check failures through existing app functions."""
import hashlib,json,os,sys
from pathlib import Path
from app.database import database_connection,fail_job,set_job_source_identity
from app.folder_import import manifest_fingerprint
from app.library_registry import list_libraries
from app.storage_config import storage_paths
from app import trash_failure as tf,trash_failure_private as private,trash_import as ti,trash_fd

assert sys.platform=='linux' and os.environ.get('RC6_SYNTHETIC_QA')=='1'
assert (os.geteuid(),os.getegid(),os.getgroups())==(568,568,[568]) or (os.geteuid(),os.getegid(),os.getgroups())==(568,568,[])
ws=Path('/workspace');registry=Path('/database/global.sqlite3')
rows=list_libraries(registry,active_only=False,registered_only=True)
assert len(rows)==1 and rows[0]['display_name']=='RC6 Smoke'
db=Path(rows[0]['database_path']);assert db.parent==Path('/database')
mode=sys.argv[1];kind='bad' if 'bad' in mode else 'good';record=Path('/logs')/('rc6-recovery-'+kind+'.json')
root=storage_paths(ws)['trash_root']
if mode.startswith('seed-'):
    assert not record.exists() and not any(p.is_file() or p.is_symlink() for p in root.rglob('*'))
    with database_connection(db) as c:
        assert not c.execute('SELECT 1 FROM files LIMIT 1').fetchone()
        assert not c.execute('SELECT 1 FROM file_families LIMIT 1').fetchone()
    names=['RC6_'+kind.upper()+'.JPG','RC6_'+kind.upper()+'.RAF']
    for name in names:(root/name).write_bytes(('synthetic RC6 original '+name).encode())
    jid=ti.stage_trash_import(db,ws,names)['job_id']
    journal=tf.journal_path(ws,jid);data=tf.read_journal(ws,jid)
    data.update(status='known_restored',known_paths=[],known_restored_count=0)
    trash_fd.atomic_json(journal,data)
    set_job_source_identity(db,jid,source_signature='rc6-container-synthetic',source_fingerprint=manifest_fingerprint(data['files']))
    fail_job(db,jid,error_message='RC6 synthetic failed restore; preserve this diagnostic')
    incoming=storage_paths(ws)['backup_root']/'.incoming'/jid
    protocol=incoming/'Protocol';protocol.mkdir(parents=True)
    status=protocol/'status.json'
    status.write_text(json.dumps({'schema_version':3,'job_id':jid,'state':'failed','stage':'failed','simulation':False,
        'import_mode':'folder','source_path':str(ti.stage_parent(ws)/jid),'lifecycle':{
        'temporary_backup':str(incoming/'Original'),'central_stock':str(incoming.parent.parent)}}))
    for p in [incoming,protocol,status,ti.stage_parent(ws)/jid]:p.chmod(0o770)
    if kind=='bad':(ti.stage_parent(ws)/jid/names[0]).write_bytes(b'synthetic mismatching stage; must remain blocked')
    record.write_text(json.dumps({'job_id':jid,'journal':data,'status_sha256':hashlib.sha256(status.read_bytes()).hexdigest()}))
    print(json.dumps({'seed':kind,'job_id':jid,'uid':os.geteuid(),'gid':os.getegid()}));sys.exit(0)
seed=json.loads(record.read_text());jid=seed['job_id'];data=seed['journal']
assert tf.read_journal(ws,jid)==data
with database_connection(db) as c:
    job=dict(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
    assert job['state']==job['stage']=='failed'
    assert job['error_message']=='RC6 synthetic failed restore; preserve this diagnostic'
    assert not c.execute('SELECT 1 FROM files WHERE job_id=?',(jid,)).fetchone()
    assert not c.execute('SELECT 1 FROM file_families WHERE job_id=?',(jid,)).fetchone()
    audits=c.execute("SELECT COUNT(*) FROM audit_log WHERE job_id=? AND action='trash_restore_failed_finalized'",(jid,)).fetchone()[0]
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
status=storage_paths(ws)['backup_root']/'.incoming'/jid/'Protocol/status.json'
assert hashlib.sha256(status.read_bytes()).hexdigest()==seed['status_sha256'] and status.stat().st_mode&0o777==0o770
if kind=='good':
    assert tf.validate_finalized(db,ws,jid) and audits==1 and not ti.protected_trash_paths(db,ws)
    receipt=private.recorded(db,ws,jid);location=Path(receipt['proof']['retention_path'])/'media'
    for item in data['files']:
        rel=item['relative_path'];copy=location/rel;stage=ti.stage_parent(ws)/jid/rel
        assert hashlib.sha256(copy.read_bytes()).hexdigest()==hashlib.sha256(stage.read_bytes()).hexdigest()==item['sha256']
        assert copy.stat().st_nlink==1 and copy.stat().st_ino!=stage.stat().st_ino
        if mode.endswith('after'):assert not (root/rel).exists()
        else:assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==item['sha256']
else:
    assert not private.recorded(db,ws,jid) and audits==0
    assert ti.protected_trash_paths(db,ws)==set(data['relative_paths'])
    for item in data['files']:
        assert hashlib.sha256((root/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
    assert (ti.stage_parent(ws)/jid/data['relative_paths'][0]).read_bytes()==b'synthetic mismatching stage; must remain blocked'
print(json.dumps({'mode':mode,'job_id':jid,'state':job['state'],'audit_count':audits,'result':'PASS'}))
