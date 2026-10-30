"""Audited resource footprints for domain operations, independent of health.

Only registered application entry points gain a bounded footprint. Unknown
functions, unknown kinds and malformed records retain the workspace write
barrier. Resource names are not file-location or completion evidence.
"""
from contextvars import ContextVar
from contextlib import contextmanager

_POLICIES = {}
_ADMISSIONS = ContextVar('operation_admission_resources', default=())


def register(function, kind):
    _POLICIES[function.__module__+'.'+function.__qualname__] = kind


def resources(record):
    explicit = record.get('_resources')
    if explicit is not None:
        return frozenset(explicit)
    ids = record.get('ids') or {}
    function = ids.get('function')
    kind = record.get('kind')
    library = record.get('library')
    if (not library or library == 'shared' or not isinstance(ids, dict)
            or _POLICIES.get(function) != kind):
        return frozenset({'workspace'})
    own = 'library:'+library
    if kind == 'inventory':
        return frozenset({own})
    if kind == 'metadata':
        # General operations modify their own unindexed work copy and task.
        # Reintegration/library operations additionally affect owned stock.
        general = ids.get('area') == 'general'
        if function == 'app.metadata_correction.apply_metadata_correction':
            from app.metadata_abort_recovery import _task_rows
            try:
                tasks = _task_rows(record['database'], 'id=?', (ids.get('correction_id'),))
                general = len(tasks) == 1 and tasks[0]['area'] == 'general'
            except Exception:
                return frozenset({'workspace'})
        return frozenset({'metadata'} if general else {'metadata', own, 'central_stock'})
    if kind in {'import', 'import_cleanup'}:
        result = {own, 'central_stock'}
        from contextlib import closing
        import sqlite3
        from pathlib import Path
        try:
            database = Path(record['database']).absolute()
            with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as connection:
                row = connection.execute('SELECT operation FROM jobs WHERE id=?', (ids.get('job_id'),)).fetchone()
            if row is None or row[0] in {'metadata_general_import', 'metadata_multiple_import'}:
                result.add('metadata')
        except Exception:
            result.add('metadata')
        return frozenset(result)
    if kind in {'sort', 'ssd', 'plan', 'batch', 'archive', 'verification'}:
        return frozenset({own, 'central_stock'})
    if kind == 'trash':
        return frozenset({own, 'central_stock', 'trash'})
    if kind == 'recovery':
        if function.startswith(('app.sort_apply.', 'app.pipeline.')):
            return frozenset({own, 'central_stock'})
        if function.startswith(('app.trash_restore.', 'app.trash_selective.')):
            return frozenset({own, 'central_stock', 'trash'})
    return frozenset({'workspace'})


def conflicts(left, right):
    return 'workspace' in left or 'workspace' in right or bool(set(left) & set(right))


def job_resources(library, operation):
    if operation in {'folder_import', 'sd_recheck', 'trash_import'}:
        return {'library:'+str(library), 'central_stock', *({'trash'} if operation == 'trash_import' else set())}
    if operation in {'metadata_general_import', 'metadata_multiple_import'}:
        return {'library:'+str(library), 'central_stock', 'metadata'}
    return {'workspace'}


@contextmanager
def admission(workspace, library, *, extra=()):
    value = {'workspace': str(workspace), '_resources': frozenset({'library:'+str(library), 'central_stock', *extra})}
    token = _ADMISSIONS.set((*_ADMISSIONS.get(), value))
    try:
        yield value
    finally:
        _ADMISSIONS.reset(token)


def current(workspace):
    from app.root_operations import _ACTIVE
    records = [r for r in _ACTIVE.get() if r['workspace'] == str(workspace)]
    if records:
        return {'_resources': frozenset().union(*(resources(r) for r in records))}
    admissions = [r for r in _ADMISSIONS.get() if r['workspace'] == str(workspace)]
    if admissions:
        return {'_resources': frozenset().union(*(r['_resources'] for r in admissions))}
    return None
