"""Read-only SD checks on the existing jobs queue; atomic import handoff.

No hash evidence survives a restart. Only source binding and request identity
are persisted; interrupted checks start over. A child import and completion of
its parent are one SQLite transaction. A check never publishes or deletes media.
"""
from pathlib import Path
import json
import os
import stat
import time
import uuid

from app.database import database_connection, get_job, utc_now_iso, update_job_progress
from app.pipeline import PipelineError, source_manifest
from app.source_reimport import retained_origins
from app.root_operations import validate_active_roots

OPERATION = 'sd_recheck'
ACTIVE = ('queued','copying','verifying','backup_verified','analyzing_metadata','organizing','interrupted')


def identity(path):
    info = Path(path).stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise PipelineError('SD-Quellordner ist nicht eindeutig gebunden.')
    return [info.st_dev, info.st_ino]


def read_only(path):
    return bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def _insert(connection, *, ident, operation, source, device, working, label, now,
            prior=None, signature=None, result=None):
    connection.execute('''INSERT INTO jobs
        (id,kind,trigger_type,state,stage,source_path,working_path,source_device_id,
         source_volume_label,operation,source_signature,duplicate_of_job_id,
         progress_current,progress_total,progress_message,result_json,created_at,updated_at)
        VALUES (?,?, 'approved_sd','queued','queued',?,?,?,?,?,?,?,0,1000,?,?,?,?)''',
        (ident, 'archive_verification' if operation == OPERATION else 'sd_import',
         str(source), str(working), device, label, operation, signature, prior,
         'SD-Sicherungsprüfung wartet auf Verarbeitung.' if operation == OPERATION else 'Auftrag wartet auf Verarbeitung.',
         json.dumps(result,ensure_ascii=False) if result is not None else None,now,now))


def _active(connection, source, device):
    return connection.execute('''SELECT * FROM jobs WHERE operation IN ('sd_recheck','folder_import')
        AND (source_device_id=? OR source_path=?) AND state IN ('''+','.join('?' for _ in ACTIVE)+''')
        ORDER BY created_at,id LIMIT 1''',(device,str(source),*ACTIVE)).fetchone()


def enqueue(database, *, source, source_root, device, working, label, request_id=None):
    ident='SD_RECHECK_'+uuid.UUID(str(request_id)).hex if request_id else 'SD_RECHECK_'+uuid.uuid4().hex
    bound={'source_identity':identity(source),'root_identity':identity(source_root),'source_root':str(source_root)}
    if not read_only(source):
        raise PipelineError('SD-Karte ist nicht nachweislich ausschließlich lesend eingebunden.')
    with database_connection(database) as connection:
        connection.execute('BEGIN IMMEDIATE')
        existing=connection.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
        if existing:
            if (existing['operation']!=OPERATION or existing['source_device_id']!=device
                    or existing['source_path']!=str(source)):
                raise PipelineError('Prüfkennung gehört zu einer anderen Quelle.')
        else:
            existing=_active(connection,source,device)
        if existing:
            if existing['operation']=='folder_import' and existing['state']=='interrupted':
                raise PipelineError('Ein Import dieser Quelle ist unterbrochen; vorhandenen Wiederanlauf zuerst klären.')
            ident=existing['id']
        else:
            _insert(connection,ident=ident,operation=OPERATION,source=source,device=device,
                    working=working,label=label,now=utc_now_iso(),result=bound)
    return get_job(database,ident)


def initial_import(database, **values):
    """Share the admission fence with confirmed checks, including direct API callers."""
    with database_connection(database) as connection:
        connection.execute('BEGIN IMMEDIATE')
        existing=_active(connection,values['source'],values['device'])
        if existing:
            if existing['state']=='interrupted':
                raise PipelineError('Ein Import dieser Quelle ist unterbrochen; vorhandenen Wiederanlauf zuerst klären.')
            ident=existing['id']
        else:
            ident=values.pop('ident')
            _insert(connection,ident=ident,operation='folder_import',now=utc_now_iso(),**values)
    return get_job(database,ident)


def resume(database):
    """Startup-only: old read-only attempts have no reusable hash evidence."""
    with database_connection(database) as connection:
        return connection.execute("UPDATE jobs SET state='queued',stage='queued',error_message=NULL,"
            "finished_at=NULL,progress_current=0,progress_total=1000,"
            "progress_message='SD-Sicherungsprüfung wird nach Neustart vollständig wiederholt.',updated_at=? "
            "WHERE operation='sd_recheck' AND state='interrupted'",(utc_now_iso(),)).rowcount


def run(database, registry, job, *, source_root, origins, signature, stop=lambda:False):
    jid=job['id'];source=Path(job['source_path']);bound=job['result']
    def check():
        validate_active_roots()
        if stop(): raise InterruptedError('SD-Sicherungsprüfung unterbrochen; Neustart prüft vollständig neu.')
        if (str(source_root)!=bound['source_root'] or identity(source_root)!=bound['root_identity']
                or identity(source)!=bound['source_identity'] or not read_only(source)):
            raise PipelineError('SD-Quelle ist nicht mehr eindeutig und ausschließlich lesend gebunden.')
    last=[0.0];copied=[0];source_bytes=[0]
    def progress(stage,current,message,force=False):
        now=time.monotonic()
        if force or now-last[0]>=1:
            update_job_progress(database,jid,state='verifying',stage=stage,current=current,total=1000,message=message)
            last[0]=now
    check();progress('source_manifest',0,'SD-Quelle wird vollständig geprüft.',True)
    def source_progress(current,total):
        source_bytes[0]=total
        progress('source_manifest',round(500*current/max(1,total)),'SD-Quelle wird vollständig geprüft.')
    entries=source_manifest(source,cancellation_callback=check,bytes_progress_callback=source_progress)
    # Same media classification as the normal importer; do not drop XMP/RAW families.
    from app.folder_import import MEDIA_TYPES
    entries=[item for item in entries if item['media_type'] in MEDIA_TYPES]
    if not entries: raise PipelineError('SD-Quelle enthält keine unterstützten Mediendateien.')
    wanted={item['sha256'] for item in entries}
    origin_rows=origins(database)
    relevant=[row for row in origin_rows if row['sha256'] in wanted]
    progress('verifying_backups',500,'Vorhandene Sicherungskopien werden vollständig geprüft.',True)
    def archive_progress(amount):
        check();copied[0]+=amount
        progress('verifying_backups',min(990,500+int(490*copied[0]/max(1,source_bytes[0]))),
                 'Vorhandene Sicherungskopien werden vollständig geprüft.')
    retained=retained_origins(registry,relevant,progress_callback=archive_progress) if relevant else []
    needs_import=bool(wanted-{row['sha256'] for row in retained})
    check();fresh_signature=signature(source)
    check();now=utc_now_iso();child='FOLDER_IMPORT_'+jid
    result={**bound,'status':'import_queued' if needs_import else 'already_backed_up',
            'integrity_verified':True,'media_file_count':len(entries),
            'source_size_bytes':sum(item['size_bytes'] for item in entries)}
    with database_connection(database) as connection:
        connection.execute('BEGIN IMMEDIATE')
        current=connection.execute('SELECT state,operation FROM jobs WHERE id=?',(jid,)).fetchone()
        if not current or current['operation']!=OPERATION or current['state']!='verifying':
            raise PipelineError('SD-Prüfauftrag ist nicht mehr Eigentümer der Übergabe.')
        if needs_import:
            active=_active(connection,source,job['source_device_id'])
            if active and active['id']!=jid:
                raise PipelineError('Ein anderer Auftrag hat diese SD-Quelle übernommen.')
            prior=connection.execute("SELECT id FROM jobs WHERE state='completed' AND operation='folder_import' "
                "AND source_device_id=? ORDER BY created_at DESC LIMIT 1",(job['source_device_id'],)).fetchone()
            _insert(connection,ident=child,operation='folder_import',source=source,
                    device=job['source_device_id'],working=job['working_path'],label=job['source_volume_label'],
                    now=now,prior=prior['id'] if prior else (origin_rows[0]['job_id'] if origin_rows else None),signature=fresh_signature)
            result['import_job_id']=child
        connection.execute("UPDATE jobs SET state='completed',stage='checked',progress_current=1000,progress_total=1000,"
            "progress_message=?,result_json=?,finished_at=?,updated_at=?,error_message=NULL WHERE id=?",
            ('Ergänzungsimport wurde sicher vorgemerkt.' if needs_import else 'Alle Aufnahmen sind bereits gesichert. Kein neuer Importauftrag erforderlich.',
             json.dumps(result,ensure_ascii=False),now,now,jid))
    return result
