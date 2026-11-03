"""Replay existing, audited recovery entry points under their ORIGINAL F14 lease.

This is not permission to replay arbitrary media jobs. The audited handlers
verify their journal/database/byte state before recovery mutations. General
recovery requires no pending journal; failed-restore finalization instead
requires its complete retained-copy proof and preserves the failed job.
"""
from contextvars import ContextVar
from pathlib import Path
import hashlib,json
from app.sort_recovery_proof import FUNCTIONS as SORT_FUNCTIONS

_APPROVED=ContextVar('qualified_domain_recovery',default=None)
DELETE_FUNCTIONS={'app.trash_selective.delete_selected_trash_files','app.trash.empty_trash_filesystem'}
RECOVERY_FUNCTIONS={'app.trash_selective.recover_trash_deletions','app.trash_restore.recover_trash_restores'}
ORIGINAL_TRASH_RESTORE='app.trash_restore.restore_trash_files'
ARCHIVE_COPY='app.archive_release_copy.create_archive_release_copies'


def handlers():
    from app.trash_selective import recover_trash_deletions
    from app.trash_restore import recover_trash_restores
    from app.trash_failure import finalize_failure,rescue_failure
    from app.sort_apply import recover_interrupted_sort_runs
    # Register the original protected archive entry before qualifying its scope.
    from app.archive_release_copy import create_archive_release_copies
    from app.archive_release_copy_recovery import recover_archive_release_copy
    return {
        ARCHIVE_COPY: recover_archive_release_copy,
        'app.trash_selective.recover_trash_deletions':recover_trash_deletions,
        'app.trash_restore.recover_trash_restores':recover_trash_restores,
        ORIGINAL_TRASH_RESTORE:recover_trash_restores,
        'app.trash_failure.finalize_failure':finalize_failure,
        'app.trash_failure.rescue_failure':rescue_failure,
        **{name:recover_trash_deletions for name in DELETE_FUNCTIONS},
        **{name:recover_interrupted_sort_runs for name in SORT_FUNCTIONS},
    }


def approved(record):
    return record is not None and _APPROVED.get()==record


def replay(workspace,registry,*,database,outcomes=None,allowed_databases=None,confirmed_rescue=False):
    from app import operation_health as health,root_operations as ro
    from app.storage_config import load_storage_settings,storage_paths
    from app.storage_anchors import check_active
    from app.database_diagnostics import inspect as inspect_database
    from app.operation_health import read_connection
    from contextlib import closing
    dispatch=handlers()  # Registers the audited footprints before inspection.
    status=health.inspect(workspace)
    dead=[r for r in status['reservations'] if not r['live']]
    failures={'app.trash_failure.finalize_failure','app.trash_failure.rescue_failure'}
    if not dead or not all(r['qualified'] and r['ids'].get('function') in dispatch
            and r['kind']==('archive' if r['ids']['function']==ARCHIVE_COPY else 'sort' if r['ids']['function'] in SORT_FUNCTIONS else 'trash' if r['ids']['function'] in failures
                           or r['ids']['function'] in DELETE_FUNCTIONS
                           or r['ids']['function']==ORIGINAL_TRASH_RESTORE else 'recovery') for r in dead):
        return False
    if len(dead)!=1 and any(r['ids']['function'] in SORT_FUNCTIONS or r['ids']['function']==ARCHIVE_COPY for r in dead):
        return False  # No combined media replay without a cross-domain proof.
    if not confirmed_rescue and any(r['ids']['function']=='app.trash_failure.rescue_failure' for r in dead):
        return False  # Never infer or renew a user's explicit rescue decision.
    if any(r['live'] for r in status['reservations']):
        raise health.DomainStartupError('domain_recovery_waits_for_live_operation')
    if confirmed_rescue and (len(dead)!=1 or dead[0]['ids'].get('function') not in failures):
        raise health.DomainStartupError('domain_recovery_rescue_requires_exact_failed_finalizer')
    root=Path(workspace).absolute();parent=ro._control_location(root)
    state=ro._state(parent,root);check_active(root,parent)
    registered=set();owners={}
    with closing(read_connection(Path(registry))) as c:
        c.execute('BEGIN')
        for row in c.execute('SELECT library_id,workspace_root,database_path,work_root,archive_root FROM libraries WHERE COALESCE(is_registered,1)=1'):
            if Path(row['workspace_root']).absolute()!=root:
                raise health.DomainStartupError('domain_recovery_registry_workspace_mismatch')
            registered.add(Path(row['database_path']).absolute())
            owners[str(Path(row['database_path']).absolute())]=dict(row)
    if database is not None:
        supplied=Path(database).absolute()
        if supplied not in registered and (state.get('storage_initialization') or {}).get('database')!=str(supplied):
            raise health.DomainStartupError('domain_recovery_unregistered_database')
        registered.add(supplied)
    if not registered:
        raise health.DomainStartupError('domain_recovery_missing_database_authority')
    if allowed_databases is not None and {Path(p).absolute() for p in allowed_databases}!=registered:
        raise health.DomainStartupError('domain_recovery_database_scope_mismatch')
    for path,role in [(Path(registry),'registry'),*((p,'catalogue') for p in sorted(registered))]:
        diagnosis=inspect_database(path,kind=role)
        if not diagnosis['consistent'] or not diagnosis['schema_current']:
            raise health.DomainStartupError('domain_recovery_database_not_qualified: '+str(path))
    required={str(root),*(str(root/n) for n in load_storage_settings(workspace_root=root).values())}
    records=[]
    for item in dead:
        path=Path(item['path']);record=ro._read(path)
        failure_finish=record['ids']['function'] in failures
        sort_replay=record['ids']['function'] in SORT_FUNCTIONS
        archive_copy=record['ids']['function']==ARCHIVE_COPY
        owner=owners.get(record.get('database')) if failure_finish or sort_replay or archive_copy else None
        expected_ids={'function':record['ids']['function']}
        expected_roots=set(required)
        if record['ids']['function']==ORIGINAL_TRASH_RESTORE:
            from app.trash_restore import _load_restore, _relative
            # Replaying arbitrary restore work would turn an unknown source into
            # ownership. Accept only a unique, existing journal matching the
            # exact original F14 selection and registered DB identities.
            raw=record['ids'].get('relative_paths')
            if raw is not None:
                try:
                    paths=json.loads(raw)
                    if (not isinstance(paths,list) or not paths
                        or not all(isinstance(p,str) and _relative(p).as_posix()==p for p in paths)
                        or json.dumps(sorted(paths))!=raw or len(paths)!=len(set(paths))):
                        raise ValueError('invalid relative path selection')
                except (ValueError,TypeError,KeyError) as error:
                    raise health.DomainStartupError('restore_recovery_invalid_original_selection') from error
                expected_ids['relative_paths']=raw
            request_id=record['ids'].get('operation_id')
            if request_id is not None:
                if not isinstance(request_id,str) or not request_id or '/' in request_id or '..' in request_id:
                    raise health.DomainStartupError('restore_recovery_invalid_request_identity')
                expected_ids['operation_id']=request_id
            directory=storage_paths(root)['metadata_root']/'.trash-restores'
            if directory.is_symlink() or not directory.is_dir():
                raise health.DomainStartupError('restore_recovery_journal_directory_unavailable')
            journals=sorted(directory.glob('*.json'))
            if len(journals)!=1 or any(p.is_symlink() for p in journals):
                raise health.DomainStartupError('restore_recovery_ambiguous_journal_scope')
            try:
                saved,_,_,plans=_load_restore(journals[0],root,sorted(registered))
            except Exception as error:
                raise health.DomainStartupError('restore_recovery_invalid_original_journal') from error
            if (saved.get('operation_id')!=request_id
                or (raw is not None and sorted(paths)!=sorted(plan['relative'] for plan in plans))):
                raise health.DomainStartupError('restore_recovery_selection_does_not_match_journal')
        if record['ids']['function']=='app.trash_selective.delete_selected_trash_files':
            from app.trash_restore import _relative
            try:
                selection=json.loads(record['ids']['relative_paths'])
                if (not isinstance(selection,list) or not selection or len(selection)!=len(set(selection))
                    or any(not isinstance(p,str) or _relative(p).as_posix()!=p for p in selection)
                    or json.dumps(sorted(selection))!=record['ids']['relative_paths']):
                    raise ValueError('invalid selection')
            except (KeyError,TypeError,ValueError) as error:
                raise health.DomainStartupError('domain_recovery_selection_invalid') from error
            expected_ids['relative_paths']=record['ids']['relative_paths']
        if sort_replay:
            from app.sort_recovery_proof import qualify
            if not owner or owner['library_id']!=record['library']:
                raise health.DomainStartupError('sort_recovery_library_owner_mismatch')
            expected_ids['run_id']=record['ids'].get('run_id')
            expected_roots.update((owner['work_root'],owner['archive_root']))
            qualify(Path(record['database']),root,owner,expected_ids['run_id'])
        elif archive_copy:
            change_id=record['ids'].get('cr_id')
            if (not isinstance(change_id,str) or not change_id.startswith('cr-')
                    or not owner or owner['library_id']!=record['library']
                    or record['kind']!='archive'):
                raise health.DomainStartupError('archive_release_recovery_owner_mismatch')
            expected_ids['cr_id']=change_id
            expected_roots.update((owner['work_root'],owner['archive_root']))
        elif failure_finish:
            job=record['ids'].get('job_id')
            if (not isinstance(job,str) or not job or '/' in job or '\\' in job or '\x00' in job
                    or not owner or owner['library_id']!=record['library']):
                raise health.DomainStartupError('domain_recovery_job_owner_mismatch')
            expected_ids['job_id']=job
            expected_roots.update((owner['work_root'],owner['archive_root']))
        elif record.get('library')!='shared' or record.get('database') is not None:
            raise health.DomainStartupError('domain_recovery_shared_owner_mismatch')
        if (hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()!=item['record_sha256']
            or set(record)-{'format','reservation_id','shared','workspace','library','generation','bindings','database','kind','ids','effect_resources'}
            or record.get('shared') is not (False if sort_replay or archive_copy else True)
            or record.get('ids')!=expected_ids
            or record.get('generation')!=[state['generation'],state.get('libraries',{}).get(record['library'],0)]
            or not expected_roots<=record['bindings'].keys()
            or any(v is None or state['bindings'].get(k)!=v for k,v in record['bindings'].items())
            or set(record.get('effect_resources',[]))-{'libraries','central_stock','trash','library:'+record['library']}):
            raise health.DomainStartupError('domain_recovery_reservation_mismatch: '+str(path))
        ro._check(record['bindings']);records.append(record)
    # Capability belongs only to this synchronous call, unchanged nonces and
    # records. Other requests/processes never inherit it, including cached SQL.
    with health.qualified_retry(root,{r['path'] for r in dead}):
        for record in records:
            # Written while the original lease is still orphaned. It keeps
            # that same effect fence visible to other processes after the
            # kernel lock becomes live; no liveness-to-write-permission gap.
            intent=parent/('domain-recovery-intent-'+record['reservation_id']+'.json')
            planned={'format':1,'reservation':record,'phase':'qualified_recovery_not_finished'}
            prior=ro._read(intent,None)
            if prior is not None and prior!=planned:
                raise health.DomainStartupError('domain_recovery_intent_conflict: '+str(intent))
            if prior is None:ro._write(intent,planned)
            if confirmed_rescue:
                decision=parent/('domain-rescue-decision-'+record['reservation_id']+'.json')
                consent={'format':1,'reservation':record,'confirmation':'RETAIN_ALL_FAILED_RESTORE_VARIANTS'}
                old=ro._read(decision,None)
                if old is not None and old!=consent:
                    raise health.DomainStartupError('domain_recovery_rescue_decision_conflict')
                if old is None:ro._write(decision,consent)
            token=_APPROVED.set(record)
            try:
                with ro.reserve(root,library_id=record['library'],database=record['database'],kind=record['kind'],
                        ids=record['ids'],paths=[Path(p) for p in record['bindings']],
                        expected_generation=record['generation'],_recovery_record=record):
                    function=record['ids']['function']
                    failure_finish=function in failures
                    sort_replay=function in SORT_FUNCTIONS
                    archive_copy=function==ARCHIVE_COPY
                    isolated=[]
                    if archive_copy:
                        owner=owners[record['database']]
                        result=dispatch[function](
                            Path(record['database']),Path(owner['archive_root']),
                            root,record['ids']['cr_id'],
                        )
                        disposition='verified_prior_archive_release_copies_restored_without_media_mutation'
                    elif sort_replay:
                        from app.sort_recovery_proof import qualify
                        from app.database import database_connection
                        owner=owners[record['database']];run_id=record['ids']['run_id']
                        before,plan_hash=qualify(Path(record['database']),root,owner,run_id)
                        with database_connection(Path(record['database'])) as connection:
                            connection.execute("UPDATE sort_runs SET status='interrupted' WHERE id=? AND status IN ('queued','verifying','moving','finalizing','rolling_back')",(run_id,))
                        result=dispatch[function].__wrapped__(Path(record['database']),run_id=run_id,strict_endpoints=True)
                        after,after_hash=qualify(Path(record['database']),root,owner,run_id,finished=True)
                        if result['blocked'] or after!=before or after_hash!=plan_hash:
                            raise health.DomainStartupError('sort_recovery_unverified_rollback')
                        disposition='verified_original_sort_rolled_back'
                        result={**result,'plan_sha256':plan_hash,'proof':after}
                    elif failure_finish:
                        from app.trash_failure import validate_finalized
                        from app.database import get_job
                        before=get_job(Path(record['database']),record['ids']['job_id'])
                        if not before or before['state']!='failed' or before['operation']!='trash_import':
                            raise health.DomainStartupError('domain_recovery_job_not_failed_restore')
                        action=dispatch[function]
                        if confirmed_rescue:
                            from app.trash_failure import rescue_failure
                            action=rescue_failure
                        result=action.__wrapped__(Path(record['database']),root,record['ids']['job_id'])
                        validate_finalized(Path(record['database']),root,record['ids']['job_id'])
                        after=get_job(Path(record['database']),record['ids']['job_id'])
                        if any(after[k]!=before[k] for k in ('state','stage','error_message')):
                            raise health.DomainStartupError('domain_recovery_failure_history_changed')
                        disposition=('confirmed_all_current_variants_retained_error_preserved' if confirmed_rescue
                                     else 'verified_failed_restore_finalized_error_preserved')
                    else:
                        handler=dispatch[function]
                        if function in DELETE_FUNCTIONS:
                            from app import trash_fd
                            journals=list((storage_paths(root)['metadata_root']/'.trash-deletions').glob('DELETE_*.json'))
                            if not journals and not ro._completed(record):
                                raise health.DomainStartupError('domain_recovery_missing_delete_journal_or_receipt')
                            if function.endswith('delete_selected_trash_files') and journals:
                                if len(journals)!=1 or sorted(i['path'] for i in trash_fd.read_json(journals[0])['files'])!=json.loads(record['ids']['relative_paths']):
                                    raise health.DomainStartupError('domain_recovery_delete_selection_mismatch')
                        from app.trash_selective import _operation_lock
                        with _operation_lock(root):
                            result=handler.__wrapped__(root,allowed_databases=registered)
                            deletion=handler.__name__=='recover_trash_deletions'
                            domain=storage_paths(root)['metadata_root']/('.trash-deletions' if deletion else '.trash-restores')
                            pattern='DELETE_*.json' if deletion else '*.json'
                            pending=list(domain.glob(pattern));isolated=[]
                            if pending and not deletion:
                                from app.trash_restore import _load_restore,_conflict_invariants
                                for journal in pending:
                                    data,trash,_,plans=_load_restore(journal,root,sorted(registered))
                                    if data['state']!='conflict':
                                        raise health.DomainStartupError('domain_recovery_journal_still_pending: '+str(journal))
                                    # A conflict is a terminal ISOLATION, not a
                                    # successful restore. Recheck every original,
                                    # identity, catalogue and unclaimed target
                                    # under the same trash exclusion lock.
                                    _conflict_invariants(data,plans,trash,sorted(registered),existing=True)
                                    isolated.append({'journal':str(journal),
                                        'sha256':hashlib.sha256(journal.read_bytes()).hexdigest(),
                                        'reserved_sources':[p['relative'] for p in plans],
                                        'reserved_targets':[p['target_relative'] for p in plans]})
                            elif pending:
                                raise health.DomainStartupError('domain_recovery_journal_still_pending: '+str(domain))
                            disposition=('verified_restore_conflict_isolated_paths_remain_reserved' if isolated
                                         else 'audited_recovery_returned_no_pending_journal')
                    ro._check(record['bindings']);check_active(root,parent)
                    receipt=parent/('domain-recovery-'+record['reservation_id']+'.json')
                    old=ro._read(receipt,None)
                    if old is not None:
                        if old.get('reservation')!=record or old.get('disposition')!=disposition:
                            raise health.DomainStartupError('domain_recovery_receipt_conflict: '+str(receipt))
                    else:
                        ro._write(receipt,{'format':1,'reservation':record,
                            'disposition':disposition,
                            'handler':function,'result':result,
                            **({'isolated_conflicts':isolated} if not failure_finish and isolated else {})})
                    if outcomes is not None:outcomes.append((dispatch[function].__module__+'.'+dispatch[function].__name__,result))
            finally:_APPROVED.reset(token)
        health.finish_qualified_retry(root)
    return True


def retry_failed_completion(database,workspace,job_id,*,confirmation):
    """Explicit existing UI repair, limited to this one old failed finalizer.

    Rescue authenticates no former bytes or origin. Its existing private
    qualifier must retain every current variant and reject anchored mismatches.
    """
    from app import root_operations as ro,operation_health as health
    import os
    if not isinstance(confirmation,str) or confirmation not in {'SAFE_ABORT_FAILED_RESTORE','RETAIN_ALL_FAILED_RESTORE_VARIANTS'}:
        raise ro.RootOperationError('domain_recovery_confirmation_missing')
    dead=[r for r in health.inspect(workspace)['reservations'] if not r['live']]
    if not dead:return None
    functions={'app.trash_failure.finalize_failure'}
    if confirmation=='RETAIN_ALL_FAILED_RESTORE_VARIANTS':functions.add('app.trash_failure.rescue_failure')
    if (len(dead)!=1 or not dead[0]['qualified'] or dead[0]['kind']!='trash'
        or dead[0]['database']!=str(Path(database).absolute())
        or dead[0]['ids'].get('function') not in functions
        or dead[0]['ids']!={'function':dead[0]['ids'].get('function'),'job_id':job_id}):
        raise ro.RootOperationError('domain_recovery_has_other_unresolved_effects')
    registry=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if not registry:raise ro.RootOperationError('domain_recovery_registry_missing')
    results=[]
    try:
        if not replay(workspace,registry,database=database,outcomes=results,
                      confirmed_rescue=confirmation=='RETAIN_ALL_FAILED_RESTORE_VARIANTS'):
            raise health.DomainStartupError('domain_recovery_finalizer_not_qualified')
    except health.DomainStartupError as error:raise ro.RootOperationError(str(error)) from error
    return results[0][1]


def try_entry(function,workspace,*,allowed_databases=None):
    """A recovery entry must acquire the old writer's lease, not a new key."""
    from app import root_operations as ro,operation_health as health
    import os
    if function not in RECOVERY_FUNCTIONS or any(r['workspace']==str(Path(workspace).absolute()) for r in ro._ACTIVE.get()):
        return None
    dispatch=handlers();dead=[r for r in health.inspect(workspace)['reservations'] if not r['live']]
    if not dead or any(not r['qualified'] or r['ids'].get('function') not in dispatch
            or dispatch[r['ids']['function']].__module__+'.'+dispatch[r['ids']['function']].__name__!=function for r in dead):
        return None
    registry=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if not registry:return None
    results=[]
    if not replay(workspace,registry,database=None,outcomes=results,allowed_databases=allowed_databases):return None
    if function.endswith('recover_trash_deletions'):
        return {'recovered_paths':sorted({p for _,result in results for p in result['recovered_paths']})}
    return sum(result for _,result in results)


class _BackupRecoveryPending(Exception):
    """A verified retry was attempted, but the original operation is not finished."""
    def __init__(self,result):
        self.result=result


def try_backup_entry(workspace, *, database, registry, central_root):
    """Resume exactly one orphaned BA-02 delete under its ORIGINAL F14 lease.

    A new recovery lease is forbidden: all authorization here belongs to the
    unchanged old record, its registered owner and its exact durable journal.
    Invalid/foreign bytes and journals remain fenced. This narrow entry does
    not grant normal writers or unrelated pending operations any rights.
    """
    from app import operation_health as health, root_operations as ro
    from app.storage_anchors import check_active
    from app.storage_config import storage_paths, load_storage_settings
    from app.managed_storage_health import require_pinned_storage
    from app.database_diagnostics import inspect as inspect_database
    from app.backup_management import (
        recover_backup_deletions, _deletion_paths, _read_journal,
        _validate_backup_job_id,
    )
    from app.operation_health import read_connection
    from contextlib import closing

    root=Path(workspace).absolute()
    database=Path(database).absolute()
    registry=Path(registry).absolute()
    central_root=Path(central_root).absolute()
    status=health.inspect(root)
    dead=[item for item in status['reservations'] if not item['live']]
    if len(dead)!=1 or dead[0].get('kind')!='backup' or dead[0].get('ids',{}).get('function')!='app.backup_management.delete_backup':
        return None
    if any(item['live'] for item in status['reservations']) or status['issues']:
        raise health.DomainStartupError('backup_recovery_other_active_effects')
    item=dead[0]
    if not item['qualified']:
        raise health.DomainStartupError('backup_recovery_unqualified_original_lease')
    require_pinned_storage(root)
    parent=ro._control_location(root)
    state=ro._state(parent,root)
    check_active(root,parent)
    if central_root!=storage_paths(root)['backup_root'].absolute():
        raise health.DomainStartupError('backup_recovery_noncanonical_central_root')
    record=ro._read(Path(item['path']))
    expected_ids={'function':'app.backup_management.delete_backup','job_id':record.get('ids',{}).get('job_id')}
    if (record.get('ids')!=expected_ids or record.get('kind')!='backup'
        or record.get('library')!='main' or record.get('shared') is not True
        or record.get('database')!=str(database)
        or record.get('workspace')!=str(root)
        or record.get('generation')!=[state.get('generation'),state.get('libraries',{}).get('main',0)]
        or set(record)-{'format','reservation_id','shared','workspace','library','generation','bindings','database','kind','ids','effect_resources'}
        or hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()!=item['record_sha256']):
        raise health.DomainStartupError('backup_recovery_original_lease_changed')
    try:
        job_id=_validate_backup_job_id(expected_ids['job_id'])
    except Exception as error:
        raise health.DomainStartupError('backup_recovery_invalid_job_identity') from error
    with closing(read_connection(registry)) as connection:
        rows=[dict(row) for row in connection.execute(
            'SELECT library_id,database_path,workspace_root,work_root,archive_root,is_main,is_registered FROM libraries')]
    main=[row for row in rows if row['library_id']=='main' and row['is_main'] and row['is_registered']]
    if (len(main)!=1 or Path(main[0]['database_path']).absolute()!=database
        or Path(main[0]['workspace_root']).absolute()!=root):
        raise health.DomainStartupError('backup_recovery_registry_owner_changed')
    for path,kind in ((registry,'registry'),(database,'catalogue')):
        diagnosis=inspect_database(path,kind=kind)
        if not diagnosis['consistent'] or not diagnosis['schema_current']:
            raise health.DomainStartupError('backup_recovery_database_not_qualified')
    required={str(root),str(central_root),str(Path(main[0]['work_root'])),str(Path(main[0]['archive_root'])),
              *(str(root/name) for name in load_storage_settings(workspace_root=root).values())}
    if (not required <= set(record['bindings'])
        or any(value is None or state['bindings'].get(key)!=value for key,value in record['bindings'].items())):
        raise health.DomainStartupError('backup_recovery_bindings_changed')
    ro._check(record['bindings'])
    journal,_stage=_deletion_paths(central_root,job_id)
    directory=journal.parent
    if (directory.is_symlink() or not directory.is_dir()
        or sorted(path.name for path in directory.iterdir())!=[journal.name]):
        raise health.DomainStartupError('backup_recovery_journal_scope_changed')
    try:
        manifest=_read_journal(journal,central_root)
    except Exception as error:
        raise health.DomainStartupError('backup_recovery_invalid_journal') from error
    if (manifest.get('root_reservation')!=record
        or manifest.get('job_id')!=job_id
        or manifest.get('main_database')!=str(database)
        or manifest.get('registry_database')!=str(registry)):
        raise health.DomainStartupError('backup_recovery_journal_not_bound_to_original_lease')

    # An intent fences other processes even while the orphan's kernel lock is
    # temporarily held live. Both retry scope and approval are call-local.
    intent=parent/('domain-recovery-intent-'+record['reservation_id']+'.json')
    planned={'format':1,'reservation':record,'phase':'qualified_recovery_not_finished'}
    previous=ro._read(intent,None)
    if previous is not None and previous!=planned:
        raise health.DomainStartupError('backup_recovery_intent_conflict')
    if previous is None:ro._write(intent,planned)
    with health.qualified_retry(root,{item['path']}):
        token=_APPROVED.set(record)
        try:
            try:
                with ro.reserve(root,library_id=record['library'],database=database,
                                kind=record['kind'],ids=record['ids'],
                                paths=[Path(p) for p in record['bindings']],
                                expected_generation=record['generation'],_recovery_record=record):
                    # A second read inside the F14 lock defeats changed-journal
                    # races between qualification and the destructive handler.
                    if _read_journal(journal,central_root).get('root_reservation')!=record:
                        raise health.DomainStartupError('backup_recovery_journal_changed_under_lock')
                    result=recover_backup_deletions.__wrapped__(database,registry,central_root)
                    if (result['blocked'] or result['errors']
                        or result['completed']+result['rolled_back']!=1
                        or journal.exists() or journal.is_symlink()):
                        raise _BackupRecoveryPending(result)
                    ro._check(record['bindings'])
                    check_active(root,parent)
                    receipt=parent/('domain-recovery-'+record['reservation_id']+'.json')
                    disposition='audited_backup_'+('completed' if result['completed']==1 else 'rolled_back')
                    old=ro._read(receipt,None)
                    if old is not None and (old.get('reservation')!=record or old.get('disposition')!=disposition):
                        raise health.DomainStartupError('backup_recovery_receipt_conflict')
                    if old is None:
                        ro._write(receipt,{'format':1,'reservation':record,
                                          'disposition':disposition,
                                          'handler':'app.backup_management.recover_backup_deletions',
                                          'result':result})
            except _BackupRecoveryPending as blocked:
                # Absolutely no F14 completion receipt was written. The lease,
                # original journal and unowned bytes stay protected.
                return blocked.result
        finally:
            _APPROVED.reset(token)
        health.finish_qualified_retry(root)
    return result
