"""Synthetic F14 backup completion process; no host devices or networking."""
from pathlib import Path
import json,os,signal,sys
from app import backup_management as backup,root_operations as ro
case=Path(sys.argv[1]);control=Path(sys.argv[2]);action=sys.argv[3];boundary=sys.argv[4]
data=json.loads((case/'backup-case.json').read_text())
db,registry,central=map(Path,(data['db'],data['registry'],data['central']))

def stop(label):
    with (control/'checkpoint.json').open('w') as f:
        json.dump({'pid':os.getpid(),'boundary':label},f);f.flush();os.fsync(f.fileno())
    os.kill(os.getpid(),signal.SIGSTOP)
    raise AssertionError('probe resumed')

actual_finish=backup.finish_backup_reservation

def finish(*a,**kw):
    if boundary=='before-receipt':stop(boundary)
    result=actual_finish(*a,**kw)
    if boundary=='receipt':stop(boundary)
    return result
backup.finish_backup_reservation=finish
actual_sync=backup._sync_dir

def sync(path):
    actual_sync(path)
    journal=central/'.deleting-journals'/(data['job']+'.json')
    if boundary=='journal-removed' and path==journal.parent and not journal.exists():stop(boundary)
backup._sync_dir=sync
if action=='delete':
    def fail(*args):raise RuntimeError('synthetic failure before main commit')
    backup._delete_job_row=fail
    try:backup.delete_backup(db,registry,central,data['job'])
    except backup.BackupDeletionError:pass
else:
    result=backup.recover_backup_deletions(db,registry,central)
    print(json.dumps(result));assert result['blocked']==0,result
