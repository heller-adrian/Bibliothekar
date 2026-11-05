"""Provision the empty installation declared by the isolated QA environment.

Legacy tests may supply their own workspace without replacing the configured
registry. That registry must exist; production missing-database checks remain
unchanged. Per-test missing/corrupt database fixtures still own their paths.
"""
import guards
from pathlib import Path
import json
import os
import sqlite3
from contextlib import closing

from app.database import initialize_database
from app.library_registry import initialize_library_registry

scratch=Path(os.environ['AUDIT_SCRATCH']).resolve()
config=Path(os.environ['KAMERA_CONFIG'])
registry=Path(os.environ['KAMERA_REGISTRY_DATABASE'])
catalogue=Path(os.environ['KAMERA_DATABASE_DIR'])/'kamera.sqlite3'
for path in (config,registry,catalogue):
    assert path.is_relative_to(scratch/'bootstrap') and not path.exists() and not path.is_symlink(), path
config.write_text('{}')
initialize_library_registry(registry)
initialize_database(catalogue)
proof={}
for path,table in ((registry,'libraries'),(catalogue,'jobs'),(catalogue,'files')):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        count=connection.execute('SELECT count(*) FROM '+table).fetchone()[0]
        assert count==0
        proof[table]={'database':str(path),'rows':count}
(Path(os.environ['AUDIT_OUTPUT'])/'bootstrap.json').write_text(json.dumps(proof,indent=2))
