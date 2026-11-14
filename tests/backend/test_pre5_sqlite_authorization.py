"""Read-only schema checks must not become recovery or migration authority."""
from contextlib import closing, nullcontext
import sqlite3
import pytest
from app import database, library_registry, operation_health as health
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready, orphan


def dump(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
        return '\n'.join(c.iterdump())


@pytest.mark.parametrize('role',['catalogue','registry'])
@pytest.mark.parametrize('read_session',[False,True])
def test_current_schema_check_does_not_request_write_authority(ready,role,read_session):
    _,ws,reg,dbs,_=ready
    path,initialize,connect=(dbs[0],database.initialize_database,database.connect) if role=='catalogue' else (reg,library_registry.initialize_library_registry,library_registry._connect)
    records=orphan(ws,dbs[0]);evidence={p:p.read_bytes() for p in records}
    before=dump(path)
    with health.read_session() if read_session else nullcontext():
        checked=initialize(path)
    assert checked['newly_applied_versions']==[]
    # Successful diagnostics grant no write capability to this connection or
    # any later connection. Even an UPDATE matching no rows remains a write.
    with closing(connect(path)) as c:
        statements=['CREATE TABLE forbidden(id INTEGER)']
        table='files' if role=='catalogue' else 'libraries'
        statements += [f"UPDATE {table} SET updated_at='unsafe' WHERE 1=0",f'DELETE FROM {table} WHERE 1=0']
        for statement in statements:
            with pytest.raises(sqlite3.DatabaseError,match='not authorized'):
                c.execute(statement)
    assert dump(path)==before and evidence=={p:p.read_bytes() for p in records}
    assert not health.inspect(ws)['writes_allowed']


@pytest.mark.parametrize('role',['catalogue','registry'])
@pytest.mark.parametrize('damage',['missing_version_table','pending_migration'])
def test_real_schema_changes_still_require_write_qualification(ready,role,damage,tmp_path,monkeypatch):
    _,ws,reg,dbs,_=ready
    path,table,initialize=(dbs[0],'schema_versions',database.initialize_database) if role=='catalogue' else (reg,'registry_schema_versions',library_registry.initialize_library_registry)
    records=orphan(ws,dbs[0]);evidence={p:p.read_bytes() for p in records}
    if damage == 'missing_version_table':
        # External damage on disposable data must not grant migration rights.
        with closing(sqlite3.connect(path)) as c:
            c.execute('DROP TABLE ' + table)
            c.commit()
    else:
        # Use valid pending DDL. Replaying an already applied ALTER TABLE can
        # fail on a duplicate column before SQLite asks its authorizer.
        ddl = 'CREATE TABLE pending_test_migration(id INTEGER PRIMARY KEY);'
        if role == 'catalogue':
            migrations = database.available_migrations()
            pending = tmp_path / 'pending.sql'
            pending.write_text(ddl)
            monkeypatch.setattr(database, 'available_migrations',
                                lambda: [*migrations, (migrations[-1][0] + 1, pending)])
        else:
            migrations = library_registry.REGISTRY_MIGRATIONS
            version = max(migrations) + 1
            monkeypatch.setattr(library_registry, 'REGISTRY_MIGRATIONS', {**migrations, version: ddl})
            monkeypatch.setattr(library_registry, 'REGISTRY_SCHEMA_VERSION', version)
    before=dump(path)
    with pytest.raises(sqlite3.DatabaseError,match='not authorized'):
        initialize(path)
    assert dump(path)==before and evidence=={p:p.read_bytes() for p in records}
