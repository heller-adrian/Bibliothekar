"""Read-only database diagnosis; never rebuild, reset or silently repair data."""
from contextlib import closing
from pathlib import Path
from functools import lru_cache
import sqlite3


def _schema(connection):
    result={}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        quoted='"'+name.replace('"','""')+'"'
        result[name]={
            'columns':{r[1]:(str(r[2]).upper(),r[3],r[5]) for r in connection.execute('PRAGMA table_info('+quoted+')')},
            'foreign_keys':{tuple(r[2:]) for r in connection.execute('PRAGMA foreign_key_list('+quoted+')')},
        }
    return result


@lru_cache(maxsize=2)
def _expected_schema(kind):
    # Execute only the shipped SQL in memory. No runtime catalogue is opened
    # for writing, migrated, rebuilt or "repaired" by diagnosis.
    with closing(sqlite3.connect(':memory:')) as connection:
        if kind=='catalogue':
            from app.database import available_migrations
            migrations={version:path.read_text() for version,path in available_migrations()}
            version_table='schema_versions'
        elif kind=='registry':
            from app.library_registry import REGISTRY_MIGRATIONS
            migrations=REGISTRY_MIGRATIONS
            version_table='registry_schema_versions'
        else:raise ValueError('unknown_database_role: '+str(kind))
        connection.execute('CREATE TABLE '+version_table+' (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
        for version in sorted(migrations):connection.executescript(migrations[version])
        return version_table,sorted(migrations),_schema(connection)


def inspect(database, *, kind='catalogue'):
    path = Path(database).absolute()
    result = {'path': str(path), 'connected': False, 'integrity': None,
              'foreign_key_violations': [], 'applied_versions': [], 'tables': [],
              'automatic_repair': False,'schema_current':False,'schema_issues':[]}
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
            version_table,expected_versions,expected_schema=_expected_schema(kind)
            if version_table in result['tables']:
                result['applied_versions'] = [r[0] for r in connection.execute('SELECT version FROM '+version_table+' ORDER BY version')]
            result['expected_versions']=expected_versions
            if result['applied_versions']!=expected_versions:
                result['schema_issues'].append({'code':'schema_version_mismatch','table':version_table})
            actual=_schema(connection)
            for table,contract in expected_schema.items():
                if table not in actual:
                    result['schema_issues'].append({'code':'required_table_missing','table':table})
                    continue
                for name,column in contract['columns'].items():
                    if actual[table]['columns'].get(name)!=column:
                        result['schema_issues'].append({'code':'column_contract_mismatch','table':table,'column':name})
                if not contract['foreign_keys'] <= actual[table]['foreign_keys']:
                    result['schema_issues'].append({'code':'foreign_key_contract_mismatch','table':table})
            result['schema_current']=not result['schema_issues']
        result['consistent'] = result['integrity'] == ['ok'] and not result['foreign_key_violations']
        result['recommended_action'] = ('review_domain_operations' if result['consistent'] and result['schema_current']
            else 'qualified_schema_recovery_required' if result['consistent'] else 'stop_and_restore_consistent_backup')
    except (OSError, ValueError, sqlite3.Error) as error:
        result.update(consistent=False, error=str(error), recommended_action='restore_original_database_or_consistent_backup')
    result['repair_instructions'] = [
        'Stop the app before restoring a database or filesystem snapshot.',
        'Retain the complete appdata, workspace, SQLite sidecars, journals and F14 evidence together.',
        'Recheck the original mount and permissions before restoring a known consistent backup.',
        'No automatic reconstruction or database reset is performed.',
    ]
    return result
