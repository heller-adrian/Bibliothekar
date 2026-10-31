"""Replay existing, audited recovery entry points under their ORIGINAL F14 lease.

This is not permission to replay arbitrary media jobs. The audited handlers
verify their journal/database/byte state before recovery mutations. General
recovery requires no pending journal; failed-restore finalization instead
requires its complete retained-copy proof and preserves the failed job.
"""
from contextvars import ContextVar
from pathlib import Path
import hashlib,json

_APPROVED=ContextVar('qualified_domain_recovery',default=None)
DELETE_FUNCTIONS={'app.trash_selective.delete_selected_trash_files','app.trash.empty_trash_filesystem'}
RECOVERY_FUNCTIONS={'app.trash_selective.recover_trash_deletions','app.trash_restore.recover_trash_restores'}


def handlers():
    from app.trash_selective import recover_trash_deletions
    from app.trash_restore import recover_trash_restores
    from app.trash_failure import finalize_failure,rescue_failure
    return {
        'app.trash_selective.recover_trash_deletions':recover_trash_deletions,
        'app.trash_restore.recover_trash_restores':recover_trash_restores,
        'app.trash_failure.finalize_failure':finalize_failure,
        'app.trash_failure.rescue_failure':rescue_failure,
        **{name:recover_trash_deletions for name in DELETE_FUNCTIONS},
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
            and r['kind']==('trash' if r['ids']['function'] in failures
                           or r['ids']['function'] in DELETE_FUNCTIONS else 'recovery') for r in dead):
        return False
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
        owner=owners.get(record.get('database')) if failure_finish else None
        expected_ids={'function':record['ids']['function']}
        expected_roots=set(required)
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
        if failure_finish:
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
            or record.get('shared') is not True
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
                    if failure_finish:
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
                        result=handler.__wrapped__(root,allowed_databases=registered)
                        deletion=handler.__name__=='recover_trash_deletions'
                        domain=storage_paths(root)['metadata_root']/('.trash-deletions' if deletion else '.trash-restores')
                        pattern='DELETE_*.json' if deletion else '*.json'
                        if list(domain.glob(pattern)):
                            raise health.DomainStartupError('domain_recovery_journal_still_pending: '+str(domain))
                        disposition='audited_recovery_returned_no_pending_journal'
                    ro._check(record['bindings']);check_active(root,parent)
                    receipt=parent/('domain-recovery-'+record['reservation_id']+'.json')
                    old=ro._read(receipt,None)
                    if old is not None:
                        if old.get('reservation')!=record or old.get('disposition')!=disposition:
                            raise health.DomainStartupError('domain_recovery_receipt_conflict: '+str(receipt))
                    else:
                        ro._write(receipt,{'format':1,'reservation':record,
                            'disposition':disposition,
                            'handler':function,'result':result})
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
