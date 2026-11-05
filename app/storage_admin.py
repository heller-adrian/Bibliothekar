"""Offline, explicit RC10 evidence adoption. Never changes ACLs or media.

Run as the app owner after stopping RC10, making a consistent backup and
administratively qualifying private ACLs. A backup reference is an operator
attestation, not a claim that a historical ACL was secure.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from app.private_storage_security import RootOperationError, qualified
from app.storage_bootstrap import CONFIRMATION, digest, evidence, raw_file, tree, logical_database


def control_evidence(root, database):
    from app.root_operations import _control_location, _read, _identity
    from app.storage_config import load_storage_settings
    parent = _control_location(root); state = _read(parent/'state.json', {})
    if state.get('format') != 1 or state.get('workspace') != _identity(root):
        raise RootOperationError('control_migration_state_mismatch: '+str(parent))
    if state.get('storage_initialization', {}).get('phase') in ('initializing', 'prepared'):
        raise RootOperationError('pending_bootstrap_requires_bootstrap_scope: '+str(parent))
    for path, identity in state.get('bindings', {}).items():
        if identity is not None and _identity(path) != identity:
            raise RootOperationError('control_migration_binding_mismatch: '+path)
    if (parent/'mutation.json').exists() or list(parent.glob('.pending-*')):
        raise RootOperationError('control_migration_recovery_required: '+str(parent))
    # A general control migration never certifies an open domain operation.
    if list(parent.glob('operation-*.json')):
        raise RootOperationError('control_migration_open_operation: '+str(parent))
    for path in parent.iterdir():
        if path.is_symlink() or path.is_dir() or not (path.name.endswith('.json') or path.name.endswith('.lock')):
            raise RootOperationError('control_migration_unknown_entry: '+str(path))
        # Historical records are snapshotted, not discarded or reclassified.
        with qualified(path) as (_,check): check()
    scan = tree(root, load_storage_settings(workspace_root=root), allow_legacy=True)
    files = {p.name: raw_file(p) for p in parent.glob('*.json') if not p.name.startswith('rc11-adoption-')}
    material = {'workspace': str(root), 'database': str(database), 'state': files.get('state.json'),
                'control_files': files, 'legacy_lock': scan['legacy_lock'],
                'catalogues': {str(p): logical_database(p) for p in sorted(database.parent.rglob('*.sqlite3'))}}
    return {'material': material, 'token': digest(material), 'legacy_lock': scan['legacy_lock']}


def inspect(root, database, scope='bootstrap'):
    from app.root_operations import _control_location, _read
    if scope == 'control': return control_evidence(root, database)
    return evidence(root, database, _read(_control_location(root)/'state.json', {}), require_adoption=False)


def adopt(root, database, token, confirmation, backup_reference, scope='bootstrap'):
    from app.root_operations import _control, _read, _write, _lock
    if confirmation != CONFIRMATION or not backup_reference.strip():
        raise RootOperationError('administrative_confirmation_and_consistent_backup_required')
    _, parent = _control(root)
    with _lock(parent/'workspace.lock', exclusive=True), _lock(parent/'shared.lock', exclusive=True), _lock(parent/'state.lock', exclusive=True, wait=True):
        checked = inspect(root, database, scope)
        if token != checked['token']: raise RootOperationError('administrative_evidence_changed: '+str(parent))
        receipt = {'kind':'rc11_administrative_adoption', 'scope':scope, 'confirmation':confirmation,
                   'backup_reference':backup_reference, 'material':checked['material'],
                   'legacy_lock':checked['legacy_lock'],
                   'origin_boundary':'administrator reviewed prior potentially writable evidence; no retrospective authenticity claim'}
        path = parent/('rc11-adoption-'+token+'.json')
        old = _read(path, None)
        if old is not None and old != receipt: raise RootOperationError('administrative_receipt_conflict: '+str(path))
        if old is None: _write(path, receipt)
        return {'adopted':True, 'receipt':str(path), 'token':token, 'source_state_unchanged':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'adopt'])
    parser.add_argument('--workspace', default=os.environ.get('KAMERA_WORKSPACE', '/workspace'))
    parser.add_argument('--database', default=str(Path(os.environ.get('KAMERA_DATABASE_DIR', '/database'))/'kamera.sqlite3'))
    parser.add_argument('--scope', choices=['bootstrap', 'control'], default='bootstrap')
    parser.add_argument('--token', default='')
    parser.add_argument('--confirmation', default='')
    parser.add_argument('--backup-reference', default='')
    args = parser.parse_args()
    root, database = Path(args.workspace).absolute(), Path(args.database).absolute()
    try:
        result = inspect(root, database, args.scope) if args.command == 'inspect' else adopt(root, database, args.token, args.confirmation, args.backup_reference, args.scope)
        print(json.dumps(result, indent=2, sort_keys=True)); return 0
    except (RootOperationError, OSError, ValueError) as error:
        print(json.dumps({'allowed':False,'error':str(error)})); return 2


if __name__ == '__main__':
    sys.exit(main())
