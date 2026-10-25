"""Synthetic-only interrupted read proof for a non-qualified protocol."""
import guards
import json,os,sys,time
from pathlib import Path
from app import trash_failure as tf,trash_import as ti
from app.database import database_connection
from app.trash import TrashError
case=json.loads(Path(sys.argv[1]).read_text());marker=Path(sys.argv[2]);pause=sys.argv[3]=='pause'
db=Path(case['db']);ws=Path(case['workspace']);jid=case['job_id']
incoming=Path(case['incoming']);wanted=incoming/'Protocol'
identity=(wanted.stat().st_dev,wanted.stat().st_ino);real=os.fstat
if pause:
    def measured(fd):
        info=real(fd)
        if (info.st_dev,info.st_ino)==identity:
            marker.write_text('open directory FD before permission decision')
            while True:time.sleep(.02)
        return info
    tf.os.fstat=measured
try:tf.inspect_failure(db,ws,jid)
except TrashError as error:
    assert str(error)=='Ungeklärter Import-Zwischenbestand bleibt erhalten: '+str(incoming)
else:raise AssertionError('Writable protocol was accepted')
assert ti.protected_trash_paths(None,ws)==set(case['paths'])
with database_connection(db) as c:
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert c.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
print(json.dumps({'status':'blocked','journal_unchanged':True}))
