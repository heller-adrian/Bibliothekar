"""Read-only qualification and explicit continuation of the SAME import.

No camera source, catalogue family or journal is deleted. Shared-host writers
remain part of RC12's administrative trust boundary; this is continuity proof.
"""
from pathlib import Path
import json
import os
import stat
from datetime import datetime, timezone

from app.database import database_connection
from app.import_publication import _parent, import_identity
from app.pipeline import PipelineError, atomic_json
from app.storage_config import storage_paths


def read_record(path):
    with _parent(Path(path)) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 32*1024*1024:
                raise PipelineError('import_recovery_invalid_record: '+str(path))
            with os.fdopen(os.dup(fd)) as stream:
                value = json.load(stream)
            after = os.fstat(fd)
            bound = os.stat(name,dir_fd=parent,follow_symlinks=False)
            fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if fields(before)!=fields(after) or fields(after)!=fields(bound):
                raise PipelineError('import_recovery_record_changed: '+str(path))
            return value
        finally:
            os.close(fd)


def relative(value):
    raw=str(value)
    if not raw or '\0' in raw or '\\' in raw or Path(raw).is_absolute() or any(p in ('','.','..') for p in raw.split('/')):
        raise PipelineError('Unsicherer relativer Importpfad: '+raw+' [import_recovery_unsafe_path]')
    return raw


def qualify(database, registry, workspace, logs, job_id):
    relative(job_id)
    central=storage_paths(Path(workspace))['backup_root'].absolute()
    stage=central/'.incoming'/job_id
    journal=stage/'move-journal.json'
    if not journal.exists() and not journal.is_symlink():
        journal=Path(logs)/'backups'/job_id/'move-journal.json'
    try:record=read_record(journal)
    except FileNotFoundError as error:
        raise PipelineError('import_recovery_journal_missing: '+str(journal)+'; copied files and history remain intact. No automatic cleanup or new origin registration is permitted.') from error
    if record.get('format')!=1 or record.get('root')!=str(central.resolve()) or not isinstance(record.get('files'),list):
        raise PipelineError('import_recovery_journal_mismatch: '+str(journal))
    with database_connection(Path(database)) as c:
        job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        rows=[dict(r) for r in c.execute('SELECT * FROM files WHERE job_id=? ORDER BY id',(job_id,))]
    if job is None or job['operation']!='folder_import':
        raise PipelineError('import_recovery_job_mismatch: '+job_id)
    # Require the registered database/library identity, and retain immutable
    # source-family/member checks even for a failed publication.
    from app.library_registry import get_library, read_library_identity
    owner=get_library(Path(registry),'main',active_only=False)
    if owner is None or Path(owner['database_path']).absolute()!=Path(database).absolute() or read_library_identity(Path(database))!='main':
        raise PipelineError('import_recovery_database_identity: '+str(database))
    from app.global_library_inventory import _database_family_rows, family_content_fingerprint
    from app.source_provenance import qualify_origins
    groups={}
    for row in _database_family_rows(Path(database)):
        groups.setdefault((str(row['job_id']),str(row['family_key'])),[]).append(row)
    qualified=qualify_origins(Path(registry),Path(database),'main',groups,family_content_fingerprint)
    if not rows or not {key for key in groups if key[0]==job_id} <= qualified:
        raise PipelineError('import_recovery_origin_missing: '+job_id)
    by_source={str(r['original_relative_path']):r for r in rows}
    items=record['files']
    if len(by_source)!=len(rows) or len(items)!=len(rows) or {str(i.get('source_relative_path')) for i in items}!=set(by_source):
        raise PipelineError('import_recovery_catalogue_mismatch: '+job_id)
    plan=[];staged=published=0;destinations=set()
    for item in items:
        src=relative(item['source_relative_path']);dst=relative(item['destination_relative_path'])
        if dst in destinations:raise PipelineError('import_recovery_duplicate_target: '+dst)
        destinations.add(dst)
        row=by_source[src]
        if (int(row['size_bytes'])!=int(item['size_bytes']) or row['sha256_original']!=item['sha256']
            or row['current_root_kind'] not in ('job_root','shared_workspace')
            or row['current_relative_path'] not in (src,dst)):
            raise PipelineError('import_recovery_media_mismatch: '+src)
        original=stage/'Original'/src;destination=central/dst
        present=[p for p in (original,destination) if p.exists() or p.is_symlink()]
        if len(present)!=1 or import_identity(present[0],item)!=item.get('inode'):
            raise PipelineError('import_recovery_ownership_ambiguous: '+src)
        if present[0]==original:staged+=1
        else:published+=1
        plan.append({**item,'selected_capture_time':row['selected_capture_time'],
                     'capture_time_confidence':row['capture_time_confidence']})
    # Do not silently ignore injected or excluded files in Original.
    original=stage/'Original'
    if original.exists():
        for p in original.rglob('*'):
            if p.is_symlink() or (p.is_file() and p.relative_to(original).as_posix() not in by_source):
                raise PipelineError('import_recovery_unknown_file: '+str(p))
    from app.managed_directory_names import NAME_PAIRS
    if stage.exists():
        allowed={'Original','move-journal.json',*NAME_PAIRS['import_protocol']}
        for child in stage.iterdir():
            if child.name not in allowed or child.is_symlink():
                raise PipelineError('import_recovery_unknown_envelope: '+str(child))
        for name in NAME_PAIRS['import_protocol']:
            protocol=stage/name
            if protocol.exists() and (not protocol.is_dir() or any(p.is_symlink() or not p.is_file() or p.name not in {'status.json','manifest.json','snapshot.json'} for p in protocol.iterdir())):
                raise PipelineError('import_recovery_unknown_protocol: '+str(protocol))
    return {'job_id':job_id,'job':dict(job),'plan':plan,'journal':str(journal),
            'staged_file_count':staged,'published_file_count':published,
            'central':str(central),'stage':str(stage),'qualified':True}


def resume(database, registry, workspace, logs, job_id, *, path_callback, history_callback, progress_callback):
    from app.folder_import import move_import_into_workspace
    proof=qualify(database,registry,workspace,logs,job_id)
    plan=proof['plan'];central=Path(proof['central']);stage=Path(proof['stage'])
    progress_callback('organizing','workspace_moving',0,len(plan),'Geprüfter Import wird mit ursprünglicher Identität fortgesetzt.')
    move_import_into_workspace(stage/'Original',central,plan,post_move_callback=path_callback,
                               ownership_record=read_record(Path(proof['journal'])))
    entries=[{'relative_path':p['source_relative_path'],'sha256':p['sha256'],'size_bytes':p['size_bytes']} for p in plan]
    history_callback(entries)
    protocol=Path(logs)/'backups'/job_id
    protocol.mkdir(parents=True,exist_ok=True)
    atomic_json(protocol/'move-journal.json',read_record(Path(proof['journal'])))
    result={'job_id':job_id,'state':'success','stage':'completed','recovered':True,
            'temporary_backup_removed':False,'source':{'size_bytes':sum(p['size_bytes'] for p in plan)},
            'organization':{'working_root':str(central),'verified':True,'file_count':len(plan),
                            'imported_source_files':entries},
            'outputs':{'protocol':str(protocol)},'snapshot':{'backend':'verification_receipt'}}
    atomic_json(protocol/'recovery-completed.json',{'job_id':job_id,'completed_at':datetime.now(timezone.utc).isoformat(),
                'staged_file_count':proof['staged_file_count'],'published_file_count':proof['published_file_count']})
    return result


def retain_completed_evidence(database, registry, workspace, logs, job_id):
    """Move only a fully published job's technical envelope; delete no files.

    Same-filesystem exclusive directory rename is restart-safe. Historical
    files and their inodes remain intact, outside the active incoming queue.
    """
    central=storage_paths(Path(workspace))['backup_root'].absolute()
    stage=central/'.incoming'/job_id
    if not stage.exists():return
    proof=qualify(database,registry,workspace,logs,job_id)
    if proof['job']['state']!='completed' or proof['staged_file_count']:
        raise PipelineError('import_recovery_not_completed: '+job_id)
    from app.managed_directory_names import NAME_PAIRS
    allowed={'Original','move-journal.json',*NAME_PAIRS['import_protocol']}
    if any(p.name not in allowed or p.is_symlink() for p in stage.iterdir()):
        raise PipelineError('import_recovery_unknown_envelope: '+str(stage))
    for name in NAME_PAIRS['import_protocol']:
        protocol=stage/name
        if protocol.exists():
            if any(p.is_symlink() or not p.is_file() or p.name not in {'status.json','manifest.json','snapshot.json'} for p in protocol.iterdir()):
                raise PipelineError('import_recovery_unknown_protocol: '+str(protocol))
    target=central/'.import-history'/job_id
    from app.import_publication import _native_rename
    from app.root_operations import validate_active_roots
    validate_active_roots()
    before=stage.stat(follow_symlinks=False)
    with _parent(stage) as (src,name), _parent(target,create=True) as (dst,new):
        _native_rename(src,name,dst,new)
        after=os.stat(new,dir_fd=dst,follow_symlinks=False)
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
            raise PipelineError('import_recovery_envelope_changed: '+str(target))
        os.fsync(src);os.fsync(dst)


def retained_staging_is_qualified(database, registry, workspace, logs):
    """Only registry-only library lifecycle changes may use this predicate.

    Storage replacement/root relocation never supplies it and stays strict.
    """
    incoming=storage_paths(Path(workspace))['backup_root']/'.incoming'
    if not incoming.exists():return True
    for child in incoming.iterdir():
        if child.is_symlink() or not child.is_dir():return False
        proof=qualify(database,registry,workspace,logs,child.name)
        result=json.loads(proof['job']['result_json'] or '{}')
        if proof['job']['state']!='failed' or result.get('import_recovery')!='retained':return False
    return True


def finish_published_envelopes(database, registry, workspace, logs):
    """Finish only completed jobs; failed imports always require a user choice."""
    incoming=storage_paths(Path(workspace))['backup_root']/'.incoming'
    if not incoming.exists():return
    with database_connection(Path(database)) as c:
        completed={r[0] for r in c.execute("SELECT id FROM jobs WHERE state='completed' AND operation='folder_import'")}
    for child in incoming.iterdir():
        if child.name in completed and (child/'move-journal.json').is_file():
            retain_completed_evidence(database,registry,workspace,logs,child.name)



def _record_unpublished_interruption(database, parent, path, record):
    """History bookkeeping only; missing publication proof NEVER releases F14.

    Early copy/hash/metadata crashes have no move journal yet. Their exact
    abandoned worker can be labelled interrupted without certifying any copied
    media, adopting a family, granting retry or deleting its original lease.
    """
    from app.operation_health import _RECOVERING,read_connection
    from app import root_operations as ro
    from app.database_diagnostics import inspect as inspect_database
    from contextlib import closing
    if not _RECOVERING.get():return False
    database=Path(database).absolute();diagnosis=inspect_database(database)
    if not diagnosis['consistent'] or not diagnosis['schema_current']:
        raise PipelineError('import_interruption_database_not_qualified')
    identity=ro._identity(database)
    if identity is None:raise PipelineError('import_interruption_database_missing')
    with closing(read_connection(database)) as connection:
        owner=connection.execute('SELECT library_id FROM library_identity WHERE singleton=1').fetchone()
        row=connection.execute('SELECT * FROM jobs WHERE id=?',(record['ids']['job_id'],)).fetchone()
    if owner is None or owner['library_id']!='main' or row is None or row['operation']!='folder_import':
        raise PipelineError('import_interruption_original_job_not_qualified')
    active={'copying','verifying','backup_verified','analyzing_metadata','organizing'}
    receipt=parent/('import-interruption-status-'+record['reservation_id']+'.json')
    planned={'format':1,'reservation':record,'database_identity':identity,
             'disposition':'interrupted_status_only_media_outcome_unknown',
             'media_completion_verified':False,'original_state':row['state']}
    old=ro._read(receipt,None)
    if old is not None:
        comparison={**planned,'original_state':old.get('original_state')}
        if old!=comparison or old.get('original_state') not in active:
            raise PipelineError('import_interruption_status_receipt_changed')
    elif row['state'] not in active:
        raise PipelineError('import_interruption_original_job_not_active')
    if row['state']=='interrupted' and old is not None:return True
    if row['state'] not in active:raise PipelineError('import_interruption_job_state_changed')
    if old is None:ro._write(receipt,planned)
    ro._check(record['bindings'])
    if ro._read(path)!=record or ro._identity(database)!=identity:
        raise PipelineError('import_interruption_original_authority_changed')
    from app.database import utc_now_iso
    now=utc_now_iso()
    with database_connection(database) as connection:
        connection.execute('BEGIN IMMEDIATE')
        if ro._read(path)!=record or ro._identity(database)!=identity:
            raise PipelineError('import_interruption_original_authority_changed')
        changed=connection.execute(
            "UPDATE jobs SET state='interrupted',stage='interrupted_after_restart',"
            "progress_message=?,error_message=?,updated_at=?,finished_at=? "
            "WHERE id=? AND operation='folder_import' AND state=?",
            ('Import interrupted before verifiable publication; retained copies need review.',
             'Publication outcome unverified; original F14 reservation remains protected.',
             now,now,record['ids']['job_id'],row['state'])).rowcount
        if changed!=1:raise PipelineError('import_interruption_job_state_changed')
        connection.execute("INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) "
                           "VALUES (?,'import_interrupted_unverified','operation',?,?,?)",
                           (record['ids']['job_id'],record['reservation_id'],json.dumps(old or planned,sort_keys=True),now))
    return True


def pending_reservations(database, registry, workspace, logs):
    """Recognize only our exact dead worker; leave its reservation untouched.

    This authorizes access to the recovery UI, never a root change or a new
    import. Unknown operations remain startup blockers.
    """
    from app.root_operations import _control_location,_read,_write,_check,_lock,_sync,generation
    from app.storage_bootstrap import key_for
    parent=_control_location(workspace);accepted=set()
    state=_read(parent/'state.json',{})
    for path in parent.glob('operation-*.json'):
        record=_read(path,{})
        ids=record.get('ids',{})
        if (record.get('kind')!='import' or record.get('library')!='main'
            or record.get('database')!=str(Path(database).absolute())
            or record.get('workspace')!=str(Path(workspace).absolute())
            or set(ids)!={'function','job_id'} or ids['function']!='app.main.process_claimed_job'):
            continue
        with _lock(path.with_suffix('.lock'),exclusive=True):
            if _read(path,{})!=record or path.name!='operation-'+key_for(record)+'.json':
                raise PipelineError('import_recovery_reservation_changed: '+str(path))
            if record.get('generation')!=list(generation(workspace,'main')):
                raise PipelineError('import_recovery_generation_changed: '+str(path))
            bindings=record.get('bindings',{})
            from app.library_registry import get_library
            from app.storage_config import load_storage_settings
            owner=get_library(registry,'main',active_only=False)
            if owner is None:raise PipelineError('import_recovery_database_identity: '+str(database))
            required={str(Path(workspace).absolute()),owner['work_root'],owner['archive_root'],
                      *(str(Path(workspace)/n) for n in load_storage_settings(workspace_root=Path(workspace)).values())}
            nonce=str(record.get('reservation_id') or '')
            if (record.get('format')!=1 or record.get('shared') is not True or len(nonce)!=32
                or any(c not in '0123456789abcdef' for c in nonce) or not required<=set(bindings)):
                raise PipelineError('import_recovery_reservation_incomplete: '+str(path))
            if not bindings or any(i is None or state.get('bindings',{}).get(p)!=i for p,i in bindings.items()):
                raise PipelineError('import_recovery_bindings_changed: '+str(path))
            _check(bindings)
            relative(ids['job_id'])
            candidates=[storage_paths(Path(workspace))['backup_root']/'.incoming'/ids['job_id']/'move-journal.json',
                        Path(logs)/'backups'/ids['job_id']/'move-journal.json']
            if not any(os.path.lexists(candidate) for candidate in candidates):
                if _record_unpublished_interruption(database,parent,path,record):
                    # Deliberately NOT accepted as a qualified media retry.
                    continue
            proof=qualify(database,registry,workspace,logs,ids['job_id'])
            if proof['job']['state']=='completed' and proof['staged_file_count']==0:
                _write(parent/('import-completed-'+nonce+'.json'),
                       {'reservation':record,'journal':proof['journal'],'verified_published':proof['published_file_count'],'disposition':'completed'})
                path.unlink();_sync(parent)
                accepted.add(str(path));continue
            if proof['job']['state'] not in {'failed','interrupted'}:
                from app.operation_health import _RECOVERING
                from app.database import utc_now_iso
                # A crashed original import retains its F14 media fence and
                # move journal. Its exact qualified staged bytes allow ONLY a
                # history-state correction, not resumption or cleanup.
                if (not _RECOVERING.get()
                    or proof['job']['state'] not in {'copying','verifying',
                        'backup_verified','analyzing_metadata','organizing'}):
                    raise PipelineError('import_recovery_worker_not_terminal: '+str(path))
                with database_connection(Path(database)) as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    changed=connection.execute(
                        "UPDATE jobs SET state='interrupted',stage='interrupted_after_restart',"
                        "progress_message=?,error_message=?,updated_at=?,finished_at=? "
                        "WHERE id=? AND operation='folder_import' AND state=?",
                        ('Abgebrochener Import benötigt Prüfung des originalen Journals.',
                         'Unvollständige Veröffentlichung; ursprüngliche F14-Reservation bleibt gesperrt.',
                         utc_now_iso(),utc_now_iso(),ids['job_id'],proof['job']['state'])).rowcount
                    if changed!=1:
                        raise PipelineError('import_recovery_job_state_changed: '+str(path))
            accepted.add(str(path))
    return accepted


def retain(database, registry, workspace, logs, job_id):
    """Close execution by explicit decision, preserving its complete receipt."""
    from app.root_operations import reserve,_control_location,_write,generation
    from app.library_registry import get_library
    # Bind only actual registered roots and roles, never guessed children.
    from app.storage_config import load_storage_settings
    owner=get_library(registry,'main',active_only=False)
    if owner is None:raise PipelineError('import_recovery_database_identity: '+str(database))
    paths=[Path(workspace),*[Path(workspace)/n for n in load_storage_settings(workspace_root=Path(workspace)).values()],Path(owner['work_root']),Path(owner['archive_root'])]
    with reserve(workspace,library_id='main',database=database,paths=paths,kind='import',
                 ids={'function':'app.main.process_claimed_job','job_id':job_id},
                 expected_generation=generation(workspace,'main'),shared=True) as reservation:
        proof=qualify(database,registry,workspace,logs,job_id)
        with database_connection(Path(database)) as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute("SELECT result_json FROM jobs WHERE id=? AND state IN ('failed','interrupted')",(job_id,)).fetchone()
            if row is None:raise PipelineError('import_recovery_job_changed: '+job_id)
            result=json.loads(row[0] or '{}');result['import_recovery']='retained'
            c.execute("UPDATE jobs SET state='failed',stage='staging_retained',result_json=? WHERE id=?",(json.dumps(result),job_id))
        _write(_control_location(workspace)/('import-retained-'+reservation['reservation_id']+'.json'),
               {'disposition':'staged_copies_retained_not_published','reservation':{k:v for k,v in reservation.items() if not k.startswith('_')},
                'job_id':job_id,'journal':proof['journal'],'staged':proof['staged_file_count'],'published':proof['published_file_count']})
