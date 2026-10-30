"""Retire audited, media-read-only pre.4 intents after qualification.

SQLite transactions already committed remain evidence; uncommitted transactions
are rolled back by SQLite. This never declares a media mutation successful.
An immutable disposition retains the complete original F14 record.
"""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import sqlite3
from datetime import datetime,timezone
from app.sqlite_retry import idempotent_write

FUNCTIONS = {
    'app.central_stock_reconcile.reconcile_central_free_stock':'inventory',
    'app.event_inventory.scan_event_inventory':'inventory',
    'app.trash.reconcile_trash_inventory':'inventory',
    'app.archive_transfer.verify_event_archive':'verification',
    'app.sort_apply.prepare_sort_run':'plan',
    'app.event_reapply.prepare_reapply_sort_run':'plan',
    'app.workspace_reconcile.prepare_workspace_reconcile_run':'plan',
}


@idempotent_write
def record_failure(record,error):
    """Domain history after the observer's SQL rollback, never completion proof."""
    from app.database import database_connection
    database=record.get('database')
    if not database:return
    plain={k:v for k,v in record.items() if not k.startswith('_')}
    with database_connection(Path(database)) as connection:
        job=record['ids'].get('job_id')
        if job and not connection.execute('SELECT 1 FROM jobs WHERE id=?',(job,)).fetchone():job=None
        connection.execute("INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'observer_failed','operation',?,?,?)",
            (job,record['reservation_id'],json.dumps({'reservation':plain,'error':str(error),
                'media_writes':False,'next_action':'retry_preparation' if record['kind']=='plan' else 'retry_observation'},sort_keys=True),datetime.now(timezone.utc).isoformat()))


def read_snapshot(function,database,workspace):
    """Physical display snapshots, without catalogue reconciliation or adoption."""
    from app.database import database_connection
    from app.storage_config import storage_paths
    if function=='app.central_stock_reconcile.reconcile_central_free_stock':
        from app.central_stock_reconcile import _actual_files,_free_rows
        actual=_actual_files(storage_paths(workspace)['backup_root'])
        with database_connection(database) as connection:
            expected=len(_free_rows(connection,set()))
        return {'ready':True,'read_only':True,'reconciled':False,'expected_file_count':expected,
                'physical_file_count':len(actual),'deleted_file_count':0,'pending_missing_count':0,
                'misplaced_file_count':0,'modified_file_count':0,'trash_file_count':0}
    if function!='app.trash.reconcile_trash_inventory':
        raise ValueError('Unknown read-only inventory: '+function)
    from app.trash import _physical_entries
    root,entries,directories=_physical_entries(workspace)
    with database_connection(database) as connection:
        known={r['current_relative_path']:dict(r) for r in connection.execute(
            "SELECT id,family_id,current_relative_path,size_bytes FROM files WHERE current_root_kind='trash'")}
    public=[]
    for entry in entries:
        item={k:v for k,v in entry.items() if not k.startswith('_')}
        row=known.get(item.get('relative_path'))
        item['tracked']=bool(row and row['size_bytes']==item.get('size_bytes'))
        item['physical_state']='observed_not_hash_verified'
        if item['tracked']:item.update(file_id=row['id'],family_id=row['family_id'])
        public.append(item)
    files=[item for item in public if item.get('entry_type')=='file']
    tracked=sum(bool(item['tracked']) for item in files)
    return {'root':str(root),'folder_name':root.name,'entries':public,'read_only':True,
            'file_count':len(files),'entry_count':len(public),'directory_count':directories,
            'total_size_bytes':sum(item['size_bytes'] for item in files),
            'tracked_file_count':tracked,'untracked_file_count':len(files)-tracked,
            'adopted_file_count':0,'exact_file_count':tracked,'ambiguous_file_count':0}


def recover(workspace):
    from app import operation_health, root_operations as ro
    from app.storage_bootstrap import key_for
    root = Path(workspace).absolute()
    parent = ro._control_location(root)
    recovered = []
    for item in operation_health.inspect(root)['reservations']:
        if item['live'] or not item['qualified']:
            continue
        if FUNCTIONS.get(item.get('ids', {}).get('function')) != item.get('kind'):
            continue
        path = Path(item['path'])
        # Same lock order as reserve; never retire a record held by a writer.
        with ro._lock(parent/'workspace.lock'), ro._lock(parent/'shared.lock'), \
             ro._lock(parent/('library-'+hashlib.sha256(item['library'].encode()).hexdigest()+'.lock')), \
             ro._lock(path.with_suffix('.lock'), exclusive=True), \
             ro._lock(parent/'state.lock', exclusive=True, wait=True):
            record = ro._read(path)
            if set(record.get('effect_resources',[])) - {'library:'+item['library']}:
                raise ro.RootOperationError('inventory_recovery_contains_extended_effects: '+str(path))
            if (hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest() != item['record_sha256']
                    or path.name != 'operation-'+key_for(record)+'.json'):
                raise ro.RootOperationError('inventory_recovery_record_changed: '+str(path))
            state = ro._state(parent, root)
            owner = ro._registered(record.get('database'))
            if (not owner or owner['library_id'] != record['library']
                    or Path(owner['workspace_root']).absolute() != root
                    or Path(owner['database_path']).absolute() != Path(record['database']).absolute()
                    or record['generation'] != [state['generation'], state['libraries'].get(record['library'], 0)]
                    or record['bindings'].get(str(root)) != state['workspace']
                    or any(value is None or state['bindings'].get(name) != value
                           for name, value in record['bindings'].items())):
                raise ro.RootOperationError('inventory_recovery_authority_mismatch: '+str(path))
            ro._check(record['bindings'])
            from app.storage_anchors import check_active
            check_active(root, parent)
            db = Path(record['database']).absolute()
            if db.resolve() != db or not db.is_file():
                raise ro.RootOperationError('inventory_recovery_database_unavailable: '+str(db))
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)) as connection:
                connection.execute('PRAGMA query_only=ON')
                connection.execute('BEGIN')
                if (connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]
                        or connection.execute('PRAGMA foreign_key_check').fetchall()):
                    raise ro.RootOperationError('inventory_recovery_database_inconsistent: '+str(db))
            receipt = parent/(record['kind']+'-interruption-'+record['reservation_id']+'.json')
            preparation=record['kind']=='plan'
            proof = {'format': 1, 'disposition': 'sql_only_preparation_interrupted' if preparation else 'observational_scan_interrupted',
                     'sqlite_integrity': 'ok', 'media_writes': False,
                     'reservation': record, 'scan_required': not preparation}
            if preparation:proof['preparation_retry_required']=True
            previous = ro._read(receipt, None)
            if previous is not None and previous != proof:
                raise ro.RootOperationError('inventory_recovery_receipt_conflict: '+str(receipt))
            if previous is None:
                ro._write(receipt, proof)
            # Revalidate after the durable disposition, including its source.
            ro._check(record['bindings'])
            if ro._read(path) != record:
                raise ro.RootOperationError('inventory_recovery_record_changed: '+str(path))
            path.unlink()
            ro._sync(parent)
            recovered.append({'reservation_id': record['reservation_id'], 'receipt': str(receipt)})
    return recovered
