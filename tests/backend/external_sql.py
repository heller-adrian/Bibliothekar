"""Explicit external damage/history setup on an existing disposable database.

This is deliberately separate from guarded application connections. Production
write admission must reject these edits while an operation is unresolved.
"""
from contextlib import closing,contextmanager
from pathlib import Path
import sqlite3


@contextmanager
def external_edit(database, *, fixture_root):
    path=Path(database).absolute();root=Path(fixture_root).resolve()
    assert path.is_relative_to(root) and path.resolve()==path and path.is_file()
    with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True)) as connection:
        connection.row_factory=sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
