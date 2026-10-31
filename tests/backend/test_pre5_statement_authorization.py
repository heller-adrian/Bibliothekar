"""Bounded SQL evidence reuse preserves fresh admission and trigger scopes."""
from contextlib import closing
import sqlite3
import pytest
from app import database,library_registry,operation_health as health,root_operations as ro
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready,orphan
from tests.backend.test_pre5_sqlite_authorization import dump


@pytest.mark.parametrize('role',['catalogue','registry'])
@pytest.mark.parametrize('handle',['connection','cursor'])
def test_one_observation_per_execute_never_survives_next_statement(ready,monkeypatch,role,handle):
    _,ws,reg,dbs,_=ready
    path,connect,table=(dbs[0],database.connect,'files') if role=='catalogue' else (reg,library_registry._connect,'libraries')
    statement=f'UPDATE {table} SET created_at=created_at,updated_at=updated_at WHERE 1=0'
    before=dump(path)
    with closing(connect(path)) as connection:
        target=connection if handle=='connection' else connection.cursor()
        actual=health.inspect;calls=[]
        def count(*args,**kwargs):
            calls.append(1);return actual(*args,**kwargs)
        monkeypatch.setattr(health,'inspect',count)
        target.execute(statement);assert len(calls)==1
        target.execute(statement);assert len(calls)==2
        connection.commit()
        records=orphan(ws,dbs[0]);saved={p:p.read_bytes() for p in records};calls.clear()
        with pytest.raises(sqlite3.DatabaseError,match='not authorized'):target.execute(statement)
        assert len(calls)==1
        assert saved=={p:p.read_bytes() for p in records}
    assert dump(path)==before


@pytest.mark.parametrize('handle',['connection','cursor'])
def test_script_checks_operation_created_between_its_statements(ready,handle):
    _,ws,_,dbs,_=ready;before=dump(dbs[0])
    with closing(database.connect(dbs[0])) as connection:
        def interrupted():
            orphan(ws,dbs[0]);return 1
        connection.create_function('new_interrupted_operation',0,interrupted)
        target=connection if handle=='connection' else connection.cursor()
        with pytest.raises(sqlite3.DatabaseError,match='not authorized'):
            target.executescript("SELECT new_interrupted_operation(); UPDATE files SET updated_at='unsafe';")
    assert dump(dbs[0])==before and not health.inspect(ws)['writes_allowed']


def test_trigger_actions_keep_their_own_resource_decision(ready):
    _,ws,_,dbs,_=ready
    with closing(database.connect(dbs[0])) as connection:
        connection.execute('CREATE TABLE metadata_qa(id TEXT)')
        connection.execute("CREATE TRIGGER qa_metadata_effect AFTER UPDATE ON jobs BEGIN INSERT INTO metadata_qa VALUES ('unsafe'); END")
        connection.commit()
        with pytest.raises(RuntimeError):
            with ro.reserve(ws,library_id='main',database=dbs[0],kind='metadata',ids={
                'function':'app.metadata_correction.execute_metadata_correction',
                'area':'general','relative_path':'one.JPG'}):
                raise RuntimeError('unresolved General file')
        connection.execute('UPDATE files SET updated_at=updated_at WHERE 1=0')
        with pytest.raises(sqlite3.DatabaseError,match='not authorized'):
            connection.execute('UPDATE jobs SET updated_at=updated_at WHERE 1=0')
        assert connection.execute('SELECT count(*) FROM metadata_qa').fetchone()[0]==0
