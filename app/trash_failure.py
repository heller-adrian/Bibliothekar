"""Verified terminal failures retain their independent staging copies.

A receipt is not a deletion permission: every use revalidates the retained bytes,
path identities and catalogue state under the existing trash operation lock.
There is deliberately no unlink/rmtree or media-copy operation in this module.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import sqlite3
import uuid

from app.database import database_connection,utc_now_iso
from app.library_registry import list_libraries
from app.root_operations import protect,validate_active_roots
from app.storage_config import storage_paths
from app.trash import TrashError,serialized_trash_operation
from app import trash_fd

KEY='failure_finalization'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def journal_path(workspace,job_id):
    from app.trash_import import _manifest
    return _manifest(storage_paths(workspace)['metadata_root']/'.trash-import',job_id)


def read_journal(workspace,job_id):
    path=journal_path(workspace,job_id)
    with trash_fd.parent(path) as (directory,name,check):
        with trash_fd.file_at(directory,name) as (fd,info):
            if info.st_nlink!=1 or info.st_size>16*1024*1024:
                raise TrashError('Restore-Journal ist nicht eindeutig oder zu groß: '+job_id)
            with os.fdopen(os.dup(fd),'rb') as stream:raw=stream.read()
            after=os.fstat(fd)
            fields=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_nlink)
            if fields(info)!=fields(after):raise TrashError('Restore-Journal während der Prüfung verändert: '+job_id)
            check();trash_fd.verify_entry(directory,name,info)
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('job_id')!=job_id:raise TrashError('Restore-Journal gehört nicht zum Auftrag: '+job_id)
    return data


def scopes(database,workspace):
    registry=Path(os.environ.get('KAMERA_REGISTRY_DATABASE',str(Path(os.environ.get('KAMERA_DATABASE_DIR','/database'))/'bibliothekar-global.sqlite3')))
    if not registry.is_file():raise TrashError('Registry fehlt; Fehlerabschluss bleibt gesperrt.')
    paths={Path(r['database_path']).absolute() for r in list_libraries(registry,active_only=False,registered_only=True)
           if Path(r['workspace_root']).absolute()==Path(workspace).absolute()}
    if not paths or (database is not None and Path(database).absolute() not in paths):raise TrashError('Restore-Datenbank ist nicht eindeutig registriert.')
    if any(not p.is_file() or p.is_symlink() for p in paths):raise TrashError('Registrierte Restore-Datenbank fehlt oder wurde ersetzt.')
    return sorted(paths)


def _jobs(connections,job_id,stage):
    owner=None;identities={}
    for db,c in connections:
        identities[str(db)]=list(trash_fd.identity(db.stat()))
        row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is not None:
            if owner is not None or row['operation']!='trash_import' or row['state']!='failed' or row['source_path']!=str(stage):
                raise TrashError('Restore-Auftrag ist aktiv, mehrfach oder nicht eindeutig fehlgeschlagen: '+job_id)
            owner=(db,dict(row))
        if (c.execute('SELECT 1 FROM files WHERE job_id=? LIMIT 1',(job_id,)).fetchone()
            or c.execute('SELECT 1 FROM file_families WHERE job_id=? LIMIT 1',(job_id,)).fetchone()):
            raise TrashError('Teilweise übernommene Katalogdaten benötigen normale Import-Recovery: '+job_id)
    if owner is None:raise TrashError('Fehlgeschlagener Restore-Auftrag fehlt: '+job_id)
    return owner,identities


def _protocol_only_failure(incoming,stage,job_id):
    """Retain and bind a failed pre-publication protocol; never clean it up."""
    if not incoming.exists() and not incoming.is_symlink():return None
    error='Ungeklärter Import-Zwischenbestand bleibt erhalten: '+str(incoming)
    with trash_fd.parent(incoming/'probe') as (root,_,check):
        owner=os.fstat(root)
        if owner.st_uid!=os.geteuid() or stat.S_IMODE(owner.st_mode)&0o022:raise TrashError(error)
        names=os.listdir(root)
        if len(names)!=1 or names[0] not in {'Protocol','Protokoll'}:raise TrashError(error)
        protocol=incoming/names[0]
        with trash_fd.parent(protocol/'status.json') as (directory,name,binding):
            info=os.fstat(directory)
            if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)&0o022 or os.listdir(directory)!=['status.json']:raise TrashError(error)
            with trash_fd.file_at(directory,name) as (fd,before):
                if before.st_uid!=os.geteuid() or before.st_nlink!=1 or stat.S_IMODE(before.st_mode)&0o022 or before.st_size>1024*1024:raise TrashError(error)
                raw=os.read(fd,1024*1024+1);data=json.loads(raw)
                if not isinstance(data,dict) or not isinstance(data.get('lifecycle'),dict):raise TrashError(error)
                after=os.fstat(fd)
                fields=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_nlink)
                if fields(before)!=fields(after):raise TrashError(error)
                if (data.get('job_id')!=job_id or data.get('schema_version')!=3
                    or data.get('state')!='failed' or data.get('stage')!='failed'
                    or data.get('simulation') is not False or data.get('import_mode')!='folder'
                    or data.get('source_path')!=str(stage)
                    or data.get('lifecycle',{}).get('temporary_backup')!=str(incoming/'Original')
                    or data.get('lifecycle',{}).get('central_stock')!=str(incoming.parent.parent)
                    or any(k in data for k in ('organization','source','snapshot','outputs'))):raise TrashError(error)
                trash_fd.verify_entry(directory,name,before);binding();check()
                if os.listdir(root)!=names or os.listdir(directory)!=['status.json']:raise TrashError(error)
                os.fsync(fd);os.fsync(directory);os.fsync(root)
                return {'root_identity':list(trash_fd.identity(owner)),
                        'protocol_identity':list(trash_fd.identity(info)),
                        'status_identity':list(trash_fd.identity(before)),
                        'status_sha256':hashlib.sha256(raw).hexdigest()}


def _inspect(database,workspace,job_id,data,*,closed=False):
    """Read-only proof; caller holds the cross-process trash lock."""
    from app.trash_restore import _relative,restore_reservations
    from app.trash_import import stage_parent
    files=data.get('files');paths=data.get('relative_paths')
    if (data.get('status')!='known_restored' or data.get('cleanup_completed')
        or data.get('known_paths')!=[] or not isinstance(files,list) or not files
        or not isinstance(paths,list) or len(paths)!=len(set(paths))
        or len(files)!=len(paths) or {_relative(i['relative_path']).as_posix() for i in files}!=set(paths)):
        raise TrashError('Unvollständiger Restore-Beleg; Originale und vollständigen Stagingnachweis wiederherstellen: '+job_id)
    if any(set(r['relative_paths']) & set(paths) for r in restore_reservations(workspace)):
        raise TrashError('Unvollständige Restore-Recovery reserviert diese Dateien: '+job_id)
    stage=stage_parent(workspace)/job_id
    incoming=storage_paths(workspace)['backup_root']/'.incoming'/job_id
    from app import trash_retention as retention
    with trash_fd.parent(stage/'probe') as (directory,_,binding):
        held=os.fstat(directory)
        if held.st_uid!=os.geteuid() or stat.S_IMODE(held.st_mode)&0o077:
            raise TrashError('Rückfall-Staging ist nicht privat für die App-UID: '+str(stage))
        binding()
    with retention.qualified(stage,{0,os.geteuid()},directory=True) as (_,binding):binding()
    incoming_proof=_protocol_only_failure(incoming,stage,job_id)
    with ExitStack() as stack:
        connections=[(p,stack.enter_context(database_connection(p))) for p in scopes(database,workspace)]
        (owner,job),db_ids=_jobs(connections,job_id,stage)
        receipt=data.get(KEY,{})
        if KEY in data and not isinstance(receipt,dict):raise TrashError('Ungültiger Fehlerabschlussbeleg: '+job_id)
        if not isinstance(json.loads(job['result_json'] or '{}'),dict):raise TrashError('Ungeklärtes Auftragsergebnis: '+job_id)
        base={k:v for k,v in data.items() if k!=KEY}
        copies=[];stage_id=None
        for item in files:
            rel=_relative(item['relative_path']);sha=str(item['sha256']);size=int(item['size_bytes'])
            if len(sha)!=64 or size<0:raise TrashError('Ungültiger Restore-Dateibeleg: '+str(rel))
            try:
                with retention.qualified(stage/rel,{0,os.geteuid()}) as (_,binding):binding()
                with trash_fd.parent(stage/rel) as (directory,name,check):
                    with trash_fd.file_at(directory,name,sha) as (fd,info):
                        if info.st_nlink!=1 or info.st_size!=size:raise TrashError('Stagingkopie ist nicht unabhängig: '+str(rel))
                        os.fsync(fd);os.fsync(directory);check()
                        copy_id=list(trash_fd.identity(info))
                with trash_fd.parent(stage/'probe') as (directory,name,check):
                    held=os.fstat(directory)
                    if held.st_uid!=os.geteuid() or stat.S_IMODE(held.st_mode)&0o077:
                        raise TrashError('Rückfall-Staging ist nicht privat für die App-UID: '+str(stage))
                    stage_id=list(trash_fd.identity(held));check();os.fsync(directory)
                original_id=None
                try:
                    with trash_fd.parent(storage_paths(workspace)['trash_root']/rel) as (directory,name,check):
                        with trash_fd.file_at(directory,name,sha) as (_,info):
                            if info.st_size!=size or list(trash_fd.identity(info))==copy_id:
                                raise TrashError('Original und Rückfallkopie sind nicht unabhängig: '+str(rel))
                            original_id=list(trash_fd.identity(info));check()
                except FileNotFoundError:
                    if not closed:raise
                copies.append({'relative_path':str(rel),'sha256':sha,'size_bytes':size,'copy_identity':copy_id,'original_identity':original_id})
            except (OSError,TrashError) as error:
                raise TrashError('Original/Rückfallkopie prüfen oder aus verifiziertem Backup wiederherstellen: '+str(rel)+' – '+str(error)) from error
        proof={'job_id':job_id,'job_error':job['error_message'],'job_stage':job['stage'],
               'source_path':str(stage),'journal_digest':digest(base),'databases':db_ids,'stage_identity':stage_id,'files':copies}
        if incoming_proof is not None:proof['retained_incoming_protocol']=incoming_proof
        if closed:
            saved=receipt.get('proof',{})
            if len(saved.get('files',[]))!=len(copies):raise TrashError('Unvollständiger Rückfallkopienbeleg: '+job_id)
            current=dict(proof);current['files']=[{**r,'original_identity':s['original_identity'] if r['original_identity'] is None else r['original_identity']} for r,s in zip(copies,saved.get('files',[]))]
            if current!=saved:raise TrashError('Nachweis oder Dateiidentität seit Fehlerabschluss geändert: '+job_id)
        return proof,owner,job


@serialized_trash_operation('workspace')
def inspect_failure(database,workspace,job_id):
    data=read_journal(workspace,job_id)
    return _inspect(database,workspace,job_id,data)[0]


def checkpoint(boundary):
    """Named journal/SQLite boundaries for deterministic process QA."""


@serialized_trash_operation('workspace')
def validate_finalized(database,workspace,job_id,data=None):
    data=read_journal(workspace,job_id) if data is None else data
    from app import trash_failure_private as private
    if private.recorded(database,workspace,job_id):
        private.validate(database,workspace,job_id,data)
        return True
    receipt=data.get(KEY,{})
    if not isinstance(receipt,dict) or receipt.get('phase')!='committed':raise TrashError('Fehlerabschluss noch nicht vollständig bestätigt: '+job_id)
    proof,owner,job=_inspect(database,workspace,job_id,data,closed=True)
    recorded=json.loads(job['result_json'] or '{}').get(KEY)
    if recorded!=receipt or receipt.get('proof_digest')!=digest(receipt.get('proof')):
        raise TrashError('Journal und fehlgeschlagener Katalogauftrag widersprechen sich: '+job_id)
    return True


@protect(workspace_arg='workspace',database_arg='database',kind='trash',error_type=TrashError)
@serialized_trash_operation('workspace')
def finalize_failure(database,workspace,job_id):
    """Persist verified failure completion; retain all media, error and journal."""
    from app.trash_selective import _atomic_json
    from app import trash_failure_private as private
    with database_connection(database) as c:
        row=c.execute('SELECT source_fingerprint FROM jobs WHERE id=?',(job_id,)).fetchone()
    if private.recorded(database,workspace,job_id) or (row and row[0]):
        return private.finalize(database,workspace,job_id)
    data=read_journal(workspace,job_id)
    prior=data.get(KEY)
    if KEY in data and (not isinstance(prior,dict) or prior.get('phase') not in {'prepared','committed'}):
        raise TrashError('Ungültiger Fehlerabschlussbeleg: '+job_id)
    if prior and prior.get('phase')=='committed':
        validate_finalized(database,workspace,job_id,data)
        return {'job_id':job_id,'status':'finalized','recovery_path':prior['proof']['source_path']}
    proof,owner,job=_inspect(database,workspace,job_id,data)
    if prior:
        if prior.get('phase')!='prepared' or prior.get('proof')!=proof or prior.get('proof_digest')!=digest(proof):
            raise TrashError('Ungeklärter oder inzwischen geänderter Fehlerabschluss: '+job_id)
        receipt=prior
    else:
        receipt={'phase':'prepared','receipt_id':uuid.uuid4().hex,'proof':proof,'proof_digest':digest(proof),'created_at':utc_now_iso()}
        data={**data,KEY:receipt}
        if len(json.dumps(data,ensure_ascii=False).encode())>16*1024*1024:raise TrashError('Fehlerabschlussbeleg zu groß; Dateien bleiben geschützt.')
        _atomic_json(journal_path(workspace,job_id),data)
    checkpoint('journal_prepared')
    committed={**receipt,'phase':'committed'}
    with ExitStack() as stack:
        connections=[]
        for path in scopes(database,workspace):
            c=stack.enter_context(database_connection(path));c.execute('BEGIN IMMEDIATE');connections.append((path,c))
        (current_owner,current_job),ids=_jobs(connections,job_id,Path(proof['source_path']))
        if ids!=proof['databases'] or current_owner!=owner or read_journal(workspace,job_id)!=data:
            raise TrashError('Datenbank- oder Journalidentität während Fehlerabschluss geändert.')
        checked,_,_=_inspect(database,workspace,job_id,data)
        if checked!=proof:raise TrashError('Rückfallkopien während Fehlerabschluss verändert.')
        result=json.loads(current_job['result_json'] or '{}')
        if KEY in result and result[KEY]!=committed:raise TrashError('Widersprüchlicher Fehlerabschluss im Katalog.')
        result[KEY]=committed
        c=next(c for path,c in connections if path==owner)
        # State/stage/error/history intentionally stay failed and untouched.
        c.execute('UPDATE jobs SET result_json=? WHERE id=? AND state=\'failed\'',(json.dumps(result,ensure_ascii=False),job_id))
        c.execute("""INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
            SELECT ?,'trash_restore_failed_finalized','restore_failure',?,?,?
            WHERE NOT EXISTS(SELECT 1 FROM audit_log WHERE action='trash_restore_failed_finalized' AND entity_id=?)""",
            (job_id,receipt['receipt_id'],json.dumps({'job_id':job_id,'proof_digest':receipt['proof_digest'],'retained_copies':proof['source_path']}),receipt['created_at'],receipt['receipt_id']))
        checkpoint('before_db_commit')
    checkpoint('db_committed')
    _atomic_json(journal_path(workspace,job_id),{**data,KEY:committed})
    checkpoint('journal_committed')
    return {'job_id':job_id,'status':'finalized','recovery_path':proof['source_path']}



@protect(workspace_arg='workspace',database_arg='database',kind='trash',error_type=TrashError)
@serialized_trash_operation('workspace')
def rescue_failure(database,workspace,job_id):
    """Only the separate explicit API confirmation can call this path."""
    from app.trash_failure_private import finalize
    return finalize(database,workspace,job_id,rescue=True)


def describe_failures(database,workspace):
    """Report only. Opening the trash never persists a new failure receipt."""
    from app.trash_failure_private import has_anchor
    with database_connection(database) as c:
        rows=list(c.execute("SELECT id,source_fingerprint FROM jobs WHERE operation='trash_import' AND state='failed' ORDER BY created_at,id"))
    ids=[str(r['id']) for r in rows];fingerprints={str(r['id']):r['source_fingerprint'] for r in rows}
    result=[]
    for jid in ids:
        data=None
        try:
            data=read_journal(workspace,jid)
            from app import trash_failure_private as private
            retained=private.recorded(database,workspace,jid)
            if retained:
                private.validate(database,workspace,jid,data)
                result.append({'job_id':jid,'status':'finalized','recovery_path':retained['proof']['retention_path'],
                               'rescued_variants':retained['proof']['mode']=='confirmed-current-variants'})
            elif KEY in data:
                validate_finalized(database,workspace,jid,data)
                result.append({'job_id':jid,'status':'finalized','recovery_path':data[KEY]['proof']['source_path']})
            elif data.get('status')=='known_restored' and data.get('files')==[] and set(data.get('known_paths',[]))==set(data.get('relative_paths',[])):
                result.append({'job_id':jid,'status':'known_restored'})
            else:
                proof=inspect_failure(database,workspace,jid)
                result.append({'job_id':jid,'status':'ready','recovery_path':proof['source_path']})
        except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,TrashError) as error:
            paths=data.get('relative_paths',[]) if isinstance(data,dict) else []
            result.append({'job_id':jid,'status':'blocked','message':str(error),'paths':paths if isinstance(paths,list) else [],
                           'rescue_available':not has_anchor(fingerprints.get(jid))})
    return result


def assert_no_active_restore(workspace,databases=None):
    """Read-only strengthening of deletion guards; never closes an operation."""
    if databases is None:
        registry=Path(os.environ.get('KAMERA_REGISTRY_DATABASE',str(Path(os.environ.get('KAMERA_DATABASE_DIR','/database'))/'bibliothekar-global.sqlite3')))
        databases=[] if not registry.is_file() else [Path(r['database_path']) for r in list_libraries(registry,active_only=False,registered_only=True)
                    if Path(r['workspace_root']).absolute()==Path(workspace).absolute()]
    for db in sorted(map(Path,databases)):
        if not db.is_file():raise TrashError('Restore-Datenbank nicht erreichbar; Löschen gesperrt: '+str(db))
        with database_connection(db) as c:
            row=c.execute("SELECT id FROM jobs WHERE operation='trash_import' AND state IN ('queued','copying','verifying','backup_verified','analyzing_metadata','organizing') LIMIT 1").fetchone()
            if row:raise TrashError('Aktive Wiederherstellung schützt den gesamten Papierkorb: '+str(row['id']))


def recover_failed_restores(database,workspace):
    """Worker/startup only. No state-only release and no media cleanup."""
    with database_connection(database) as c:
        ids=[str(r['id']) for r in c.execute("SELECT id FROM jobs WHERE operation='trash_import' AND state='failed' ORDER BY created_at,id")]
    results=[]
    for jid in ids:
        try:results.append(finalize_failure(database,workspace,jid))
        except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,TrashError) as error:
            results.append({'job_id':jid,'status':'blocked','message':str(error)})
    return results
