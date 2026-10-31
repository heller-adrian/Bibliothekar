"""Replay existing, audited recovery entry points under their ORIGINAL F14 lease.

This is not permission to replay arbitrary media jobs. The two handlers already
verify their complete journal/database/byte state before recovery mutations. A
successful return is accepted only with no remaining journal in their domain.
"""
from contextvars import ContextVar
from pathlib import Path
import hashlib,json

_APPROVED=ContextVar('qualified_domain_recovery',default=None)


def handlers():
    from app.trash_selective import recover_trash_deletions
    from app.trash_restore import recover_trash_restores
    return {
        'app.trash_selective.recover_trash_deletions':recover_trash_deletions,
        'app.trash_restore.recover_trash_restores':recover_trash_restores,
    }


def approved(record):
    return _APPROVED.get()==record


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
    if not dead or not all(r['qualified'] and r['kind']=='recovery' and r['ids'].get('function') in dispatch for r in dead):
        return False
    if any(r['live'] for r in status['reservations']):
        raise health.DomainStartupError('domain_recovery_waits_for_live_operation')
    root=Path(workspace).absolute();parent=ro._control_location(root)
    state=ro._state(parent,root);check_active(root,parent)
    registered=set()
    with closing(read_connection(Path(registry))) as c:
        c.execute('BEGIN')
        for row in c.execute('SELECT workspace_root,database_path FROM libraries'):
            if Path(row['workspace_root']).absolute()!=root:
                raise health.DomainStartupError('domain_recovery_registry_workspace_mismatch')
            registered.add(Path(row['database_path']).absolute())
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
        if (hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()!=item['record_sha256']
            or set(record)-{'format','reservation_id','shared','workspace','library','generation','bindings','database','kind','ids','effect_resources'}
            or record.get('shared') is not True
            or record.get('library')!='shared' or record.get('database') is not None
            or record.get('ids')!={'function':item['ids']['function']}
            or record.get('generation')!=[state['generation'],state.get('libraries',{}).get('shared',0)]
            or not required<=record['bindings'].keys()
            or any(v is None or state['bindings'].get(k)!=v for k,v in record['bindings'].items())
            or set(record.get('effect_resources',[]))-{'libraries','central_stock','trash'}):
            raise health.DomainStartupError('domain_recovery_reservation_mismatch: '+str(path))
        ro._check(record['bindings']);records.append(record)
    # Capability belongs only to this synchronous call, unchanged nonces and
    # records. Other requests/processes never inherit it, including cached SQL.
    with health.qualified_retry(root,{r['path'] for r in dead}):
        for record in records:
            token=_APPROVED.set(record)
            try:
                with ro.reserve(root,library_id='shared',database=None,kind='recovery',
                        ids=record['ids'],paths=[Path(p) for p in record['bindings']],
                        expected_generation=record['generation'],_recovery_record=record):
                    function=record['ids']['function']
                    result=dispatch[function].__wrapped__(root,allowed_databases=registered)
                    domain=storage_paths(root)['metadata_root']/('.trash-deletions' if function.endswith('recover_trash_deletions') else '.trash-restores')
                    pattern='DELETE_*.json' if function.endswith('recover_trash_deletions') else '*.json'
                    if list(domain.glob(pattern)):
                        raise health.DomainStartupError('domain_recovery_journal_still_pending: '+str(domain))
                    ro._check(record['bindings']);check_active(root,parent)
                    receipt=parent/('domain-recovery-'+record['reservation_id']+'.json')
                    old=ro._read(receipt,None)
                    if old is not None:
                        if old.get('reservation')!=record or old.get('disposition')!='audited_recovery_returned_no_pending_journal':
                            raise health.DomainStartupError('domain_recovery_receipt_conflict: '+str(receipt))
                    else:
                        ro._write(receipt,{'format':1,'reservation':record,
                            'disposition':'audited_recovery_returned_no_pending_journal',
                            'handler':function,'result':result})
            finally:_APPROVED.reset(token)
    return True
