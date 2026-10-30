"""Read-only database diagnosis; never rebuild, reset or silently repair data."""
from contextlib import closing
from pathlib import Path
import sqlite3


def inspect(database):
    path = Path(database).absolute()
    result = {'path': str(path), 'connected': False, 'integrity': None,
              'foreign_key_violations': [], 'applied_versions': [], 'tables': [],
              'automatic_repair': False}
    try:
        if not path.is_file() or path.resolve() != path:
            raise ValueError('database_missing_or_symlink: '+str(path))
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)) as connection:
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            result['tables'] = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            result['connected'] = True
            result['integrity'] = [r[0] for r in connection.execute('PRAGMA quick_check')]
            result['foreign_key_violations'] = [list(r) for r in connection.execute('PRAGMA foreign_key_check')]
            if 'schema_versions' in result['tables']:
                result['applied_versions'] = [r[0] for r in connection.execute('SELECT version FROM schema_versions ORDER BY version')]
        result['consistent'] = result['integrity'] == ['ok'] and not result['foreign_key_violations']
        result['recommended_action'] = ('review_domain_operations' if result['consistent'] else 'stop_and_restore_consistent_backup')
    except (OSError, ValueError, sqlite3.Error) as error:
        result.update(consistent=False, error=str(error), recommended_action='restore_original_database_or_consistent_backup')
    result['repair_instructions'] = [
        'Stop the app before restoring a database or filesystem snapshot.',
        'Retain the complete appdata, workspace, SQLite sidecars, journals and F14 evidence together.',
        'Recheck the original mount and permissions before restoring a known consistent backup.',
        'No automatic reconstruction or database reset is performed.',
    ]
    return result
