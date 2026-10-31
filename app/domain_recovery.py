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


def handlers():
    from app.trash_selective import recover_trash_deletions
    from app.trash_restore import recover_trash_restores
    from app.trash_failure import finalize_failure
    return {
        'app.trash_selective.recover_trash_deletions':recover_trash_deletions,
        'app.trash_restore.recover_trash_restores':recover_trash_restores,
        'app.trash_failure.finalize_failure':finalize_failure,
    }


def approved(record):
    return record is not None and _APPROVED.get()==record


def replay(workspace,registry,*,database):
    from app import operation_health as health,root_operations as ro
    from app.storage_config import load_storage_settings,storage_paths
    from app.storage_anchors import check_active
    from app.database_diagnostics import inspect as inspect_database
    from app.operation_health import read_connection
    from contextlib import closing
    dispatch=handlers()  # Registers the audited footprints before inspection.
    status=health.inspect(workspace)
    dead=[r for r in status['reservations'] if not r['live']]
    if not dead or not all(r['qualified'] and r['ids'].get('function') in dispatch
            and r['kind']==('trash' if r['ids']['function']=='app.trash_failure.finalize_failure' else 'recovery') for r in dead):
        return False
    if any(r['live'] for r in status['reservations']):
        raise health.DomainStartupError('domain_recovery_waits_for_live_operation')
    root=Path(workspace).absolute();parent=ro._control_location(root)
    state=ro._state(parent,root);check_active(root,parent)
    registered=set();owners={}
    with closing(read_connection(Path(registry))) as c:
        c.execute('BEGIN')
        for row in c.execute('SELECT library_id,workspace_root,database_path,work_root,archive_root FROM libraries'):
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
    for path,role in [(Path(registry),'registry'),*((p,'catalogue') for p in sorted(registered))]:
        diagnosis=inspect_database(path,kind=role)
        if not diagnosis['consistent'] or not diagnosis['schema_current']:
            raise health.DomainStartupError('domain_recovery_database_not_qualified: '+str(path))
    required={str(root),*(str(root/n) for n in load_storage_settings(workspace_root=root).values())}
    records=[]
    for item in dead:
        path=Path(item['path']);record=ro._read(path)
        failure_finish=record['ids']['function']=='app.trash_failure.finalize_failure'
        owner=owners.get(record.get('database')) if failure_finish else None
        expected_ids={'function':record['ids']['function']}
        expected_roots=set(required)
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
            token=_APPROVED.set(record)
            try:
                with ro.reserve(root,library_id=record['library'],database=record['database'],kind=record['kind'],
                        ids=record['ids'],paths=[Path(p) for p in record['bindings']],
                        expected_generation=record['generation'],_recovery_record=record):
                    function=record['ids']['function']
                    failure_finish=function=='app.trash_failure.finalize_failure'
                    if failure_finish:
                        from app.trash_failure import validate_finalized
                        from app.database import get_job
                        before=get_job(Path(record['database']),record['ids']['job_id'])
                        if not before or before['state']!='failed' or before['operation']!='trash_import':
                            raise health.DomainStartupError('domain_recovery_job_not_failed_restore')
                        result=dispatch[function].__wrapped__(Path(record['database']),root,record['ids']['job_id'])
                        validate_finalized(Path(record['database']),root,record['ids']['job_id'])
                        after=get_job(Path(record['database']),record['ids']['job_id'])
                        if any(after[k]!=before[k] for k in ('state','stage','error_message')):
                            raise health.DomainStartupError('domain_recovery_failure_history_changed')
                        disposition='verified_failed_restore_finalized_error_preserved'
                    else:
                        result=dispatch[function].__wrapped__(root,allowed_databases=registered)
                        domain=storage_paths(root)['metadata_root']/('.trash-deletions' if function.endswith('recover_trash_deletions') else '.trash-restores')
                        pattern='DELETE_*.json' if function.endswith('recover_trash_deletions') else '*.json'
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
            finally:_APPROVED.reset(token)
    return True
