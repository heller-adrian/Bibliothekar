"""Explicit retry of one unchanged archive-finalization reservation.

The original protected function must recheck pinned roots, generation and all
physical files. This capability cannot start another archive job or waive an
unrelated reservation. Other requests remain fenced while its lock is live.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path


@contextmanager
def qualified_finish_retry(workspace, paths):
    from app import operation_health as health, root_operations as ro
    status = health.inspect(workspace)
    if (len(paths) != 1 or len(status['reservations']) != 1
            or any(issue.get('phase') != 'startup-recovery' for issue in status['issues'])):
        raise ro.RootOperationError('archive_retry_has_other_unresolved_effects')
    item = status['reservations'][0]
    if item['path'] not in paths or item['live'] or not item['qualified']:
        raise ro.RootOperationError('archive_retry_original_reservation_required')
    parent = ro._control_location(workspace)
    record = ro._read(Path(item['path']))
    if (hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest() != item['record_sha256']
            or record['kind'] != 'archive'
            or record['ids'].get('function') != 'app.event_change_apply.finish_event_change'):
        raise ro.RootOperationError('archive_retry_reservation_changed')
    intent = parent / ('domain-recovery-intent-' + record['reservation_id'] + '.json')
    planned = {'format': 1, 'reservation': record, 'phase': 'qualified_recovery_not_finished'}
    previous = ro._read(intent, None)
    if previous is not None and previous != planned:
        raise ro.RootOperationError('archive_retry_intent_changed')
    with health.qualified_retry(workspace, paths):
        if previous is None:
            ro._write(intent, planned)
        yield
        # The domain API has completed and finish_qualified_retry has verified
        # retirement of the exact original lease before leaving this context.
        if Path(item['path']).exists():
            raise ro.RootOperationError('archive_retry_not_completed')
        intent.unlink()
        ro._sync(parent)
