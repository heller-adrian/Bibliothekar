"""Retire audited, media-read-only pre.4 inventory intents after qualification.

SQLite transactions already committed remain evidence; uncommitted transactions
are rolled back by SQLite. This never declares a media mutation successful.
An immutable disposition retains the complete original F14 record.
"""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import sqlite3

FUNCTIONS = frozenset({
    'app.central_stock_reconcile.reconcile_central_free_stock',
    'app.event_inventory.scan_event_inventory',
    'app.trash.reconcile_trash_inventory',
})


def recover(workspace):
    from app import operation_health, root_operations as ro
    from app.storage_bootstrap import key_for
    root = Path(workspace).absolute()
    parent = ro._control_location(root)
    recovered = []
    for item in operation_health.inspect(root)['reservations']:
        if item['live'] or not item['qualified'] or item.get('kind') != 'inventory':
            continue
        if item.get('ids', {}).get('function') not in FUNCTIONS:
            continue
        path = Path(item['path'])
        # Same lock order as reserve; never retire a record held by a writer.
        with ro._lock(parent/'workspace.lock'), ro._lock(parent/'shared.lock'), \
             ro._lock(parent/('library-'+hashlib.sha256(item['library'].encode()).hexdigest()+'.lock')), \
             ro._lock(path.with_suffix('.lock'), exclusive=True), \
             ro._lock(parent/'state.lock', exclusive=True, wait=True):
            record = ro._read(path)
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
            receipt = parent/('inventory-interruption-'+record['reservation_id']+'.json')
            proof = {'format': 1, 'disposition': 'observational_scan_interrupted',
                     'sqlite_integrity': 'ok', 'media_writes': False,
                     'reservation': record, 'scan_required': True}
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
