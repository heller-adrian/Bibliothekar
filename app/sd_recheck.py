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
            prior=None, signature=None, result=None, trigger="approved_sd"):
    connection.execute('''INSERT INTO jobs
        (id,kind,trigger_type,state,stage,source_path,working_path,source_device_id,
         source_volume_label,operation,source_signature,duplicate_of_job_id,
         progress_current,progress_total,progress_message,result_json,created_at,updated_at)
        VALUES (?,?, ?,'queued','queued',?,?,?,?,?,?,?,0,1000,?,?,?,?)''',
        (ident, 'archive_verification' if operation == OPERATION else 'sd_import', trigger,
         str(source), str(working), device, label, operation, signature, prior,
         ('Quellprüfung wartet auf Verarbeitung.' if result and result.get('source_root_key') else 'SD-Sicherungsprüfung wartet auf Verarbeitung.') if operation == OPERATION else 'Auftrag wartet auf Verarbeitung.',
         json.dumps(result,ensure_ascii=False) if result is not None else None,now,now))


def _active(connection, source, device):
    return connection.execute('''SELECT * FROM jobs WHERE operation IN ('sd_recheck','folder_import')
        AND (source_device_id=? OR source_path=?) AND state IN ('''+','.join('?' for _ in ACTIVE)+''')
        ORDER BY created_at,id LIMIT 1''',(device,str(source),*ACTIVE)).fetchone()


def enqueue(database, *, source, source_root, device, working, label, request_id=None, source_root_key="removable", source_mode="sd_card"):
    ident='SD_RECHECK_'+uuid.UUID(str(request_id)).hex if request_id else 'SD_RECHECK_'+uuid.uuid4().hex
    bound={'source_identity':identity(source),'root_identity':identity(source_root),'source_root':str(source_root)}
    folder=source_mode!='sd_card'
    if folder:bound.update(source_root_key=source_root_key,source_mode=source_mode)
    # Bind every source component before persisting admission, not just its leaf.
    from app.trash_fd import parent
    with parent(Path(source)/'probe') as (_,_,check):check()
    if (not folder or source_root_key=='removable') and not read_only(source):
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
            if folder and (existing['source_path']!=str(source) or existing['source_device_id']!=device):
                raise PipelineError('Ein anderer Quellordner dieses Geräts wird noch geprüft. Bitte zuerst abschließen oder abbrechen.')
            if existing['operation']=='folder_import' and existing['state']=='interrupted':
                raise PipelineError('Ein Import dieser Quelle ist unterbrochen; vorhandenen Wiederanlauf zuerst klären.')
            ident=existing['id']
        else:
            _insert(connection,ident=ident,operation=OPERATION,source=source,device=device,
                    working=working,label=label,now=utc_now_iso(),result=bound,
                    trigger='usb_key' if source_mode=='drive' else 'manual' if folder else 'approved_sd')
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
    jid=job['id'];source=Path(job['source_path']);bound=job['result'];folder=bool(bound.get('source_root_key'))
    def check():
        validate_active_roots()
        if stop(): raise InterruptedError('SD-Sicherungsprüfung unterbrochen; Neustart prüft vollständig neu.')
        if (str(source_root)!=bound['source_root'] or identity(source_root)!=bound['root_identity']
                or identity(source)!=bound['source_identity']
                or ((not folder or bound['source_root_key']=='removable') and not read_only(source))):
            raise PipelineError('SD-Quelle ist nicht mehr eindeutig und ausschließlich lesend gebunden.')
    last=[0.0];copied=[0];source_bytes=[0]
    def progress(stage,current,message,force=False):
        now=time.monotonic()
        if force or now-last[0]>=1:
            update_job_progress(database,jid,state='verifying',stage=stage,current=current,total=1000,message=message)
            last[0]=now
    source_message='Quelle wird vollständig geprüft.' if folder else 'SD-Quelle wird vollständig geprüft.'
    check();progress('source_manifest',0,source_message,True)
    def source_progress(current,total):
        source_bytes[0]=total
        progress('source_manifest',round(500*current/max(1,total)),source_message)
    revalidate=lambda:None
    if folder:entries,revalidate=folder_manifest(source,check,source_progress)
    else:entries=source_manifest(source,cancellation_callback=check,bytes_progress_callback=source_progress)
    # Same media classification as the normal importer; do not drop XMP/RAW families.
    from app.folder_import import MEDIA_TYPES
    entries=[item for item in entries if item['media_type'] in MEDIA_TYPES]
    if not entries: raise PipelineError('SD-Quelle enthält keine unterstützten Mediendateien.')
    wanted={item['sha256'] for item in entries}
    origin_rows=catalog_origins(database,registry) if folder else origins(database)
    relevant=[row for row in origin_rows if row['sha256'] in wanted]
    progress('verifying_backups',500,'Vorhandene Sicherungskopien werden vollständig geprüft.',True)
    def archive_progress(amount):
        check();copied[0]+=amount
        progress('verifying_backups',min(990,500+int(490*copied[0]/max(1,source_bytes[0]))),
                 'Vorhandene Sicherungskopien werden vollständig geprüft.')
    retained=retained_origins(registry,relevant,progress_callback=archive_progress) if relevant else []
    needs_import=bool(wanted-{row['sha256'] for row in retained})
    revalidate();check();fresh_signature=signature(source)
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
                    now=now,prior=prior['id'] if prior else (origin_rows[0]['job_id'] if origin_rows else None),signature=fresh_signature,
                    result={'verified_folder_check':True} if folder else None,
                    trigger='usb_key' if bound.get('source_mode')=='drive' else 'manual' if folder else 'approved_sd')
            result['import_job_id']=child
        connection.execute("UPDATE jobs SET state='completed',stage='checked',progress_current=1000,progress_total=1000,"
            "progress_message=?,result_json=?,finished_at=?,updated_at=?,error_message=NULL WHERE id=?",
            ('Ergänzungsimport wurde sicher vorgemerkt.' if needs_import else 'Alle Aufnahmen sind bereits gesichert. Kein neuer Importauftrag erforderlich.',
             json.dumps(result,ensure_ascii=False),now,now,jid))
    return result


def catalog_origins(database, registry, *, exclude_job_id=None):
    """All registered catalogues, never create a missing catalogue while reading."""
    from app.library_registry import list_libraries
    from app.database import list_imported_media_origins
    paths={Path(database).absolute(),*(Path(r['database_path']).absolute() for r in list_libraries(registry,active_only=False))}
    rows=[]
    for path in sorted(paths):
        if not path.is_file() or path.is_symlink():raise PipelineError('Registrierter Katalog fehlt oder ist nicht eindeutig.')
        rows.extend(list_imported_media_origins(path,exclude_job_id=exclude_job_id))
    return rows


def folder_manifest(source, check, progress):
    """FD-bound full source hash, with a metadata-only revalidation at handoff."""
    import hashlib
    from app.trash_fd import parent
    from app.pipeline import classify
    from app.source_filter import should_ignore_source_path
    versions={};entries=[];total=[0];done=[0]
    version=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    def walk(fd,prefix='',hashing=False):
        start=version(os.fstat(fd))
        for name in sorted(os.listdir(fd)):
            check();relative=prefix+name;path=source/relative
            if should_ignore_source_path(source,path):continue
            before=os.stat(name,dir_fd=fd,follow_symlinks=False)
            flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
            if stat.S_ISDIR(before.st_mode):flags|=os.O_DIRECTORY
            elif not stat.S_ISREG(before.st_mode):raise PipelineError('Importquelle enthält einen Link oder unbekannten Dateityp.')
            child=os.open(name,flags,dir_fd=fd)
            try:
                if version(os.fstat(child))!=version(before):raise PipelineError('Importquelle wurde ausgetauscht.')
                if hashing:
                    if versions.get(relative)!=version(before):raise PipelineError('Importquelle hat sich während der Prüfung geändert.')
                else:versions[relative]=version(before)
                if stat.S_ISDIR(before.st_mode):walk(child,relative+'/',hashing)
                elif hashing:
                    h=hashlib.sha256()
                    while block:=os.read(child,1024*1024):
                        check();h.update(block);done[0]+=len(block);progress(done[0],total[0])
                    entries.append({'relative_path':relative,'filename':name,'extension':path.suffix.lower(),
                        'media_type':classify(path.suffix.lower()),'family_key':str(Path(relative).with_suffix('')),
                        'sha256':h.hexdigest(),'size_bytes':before.st_size})
                else:total[0]+=before.st_size
                if version(os.fstat(child))!=version(before) or version(os.stat(name,dir_fd=fd,follow_symlinks=False))!=version(before):
                    raise PipelineError('Importquelle hat sich während der Prüfung geändert.')
            finally:os.close(child)
        if version(os.fstat(fd))!=start:raise PipelineError('Quellverzeichnis hat sich während der Prüfung geändert.')
    with parent(source/'probe') as (fd,_,binding):
        walk(fd);walk(fd,hashing=True);binding()
    def revalidate():
        with parent(source/'probe') as (fd,_,binding):
            seen=set()
            def scan(fd,prefix=''):
                for name in os.listdir(fd):
                    rel=prefix+name
                    if should_ignore_source_path(source,source/rel):continue
                    st=os.stat(name,dir_fd=fd,follow_symlinks=False);seen.add(rel)
                    if versions.get(rel)!=version(st):raise PipelineError('Importquelle wurde nach der Hashprüfung verändert.')
                    if stat.S_ISDIR(st.st_mode):
                        child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                        try:scan(child,rel+'/')
                        finally:os.close(child)
            scan(fd);binding()
            if seen!=set(versions):raise PipelineError('Importquelle ist nicht mehr vollständig identisch.')
    return entries,revalidate
