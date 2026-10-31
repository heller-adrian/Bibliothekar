"""Share one observation during one execute's authorizer callbacks only.

Every execute/cursor.execute starts afresh. Scripts and executemany deliberately
use the uncached observer. This caches evidence, never a permission decision:
each table/column action still receives its own resource/admission check.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import sqlite3

_PREPARATION=ContextVar('sqlite_authorization_preparation',default=None)


@contextmanager
def _statement(connection):
    token=_PREPARATION.set([connection,None])
    try:yield
    finally:_PREPARATION.reset(token)


@contextmanager
def _uncached():
    token=_PREPARATION.set(None)
    try:yield
    finally:_PREPARATION.reset(token)


def observe(connection,observer):
    current=_PREPARATION.get()
    if current is None or current[0] is not connection:return observer()
    if current[1] is None:current[1]=observer()
    return current[1]


class Cursor(sqlite3.Cursor):
    def execute(self,*args,**kwargs):
        with _statement(self.connection):return super().execute(*args,**kwargs)

    def executemany(self,*args,**kwargs):
        with _uncached():return super().executemany(*args,**kwargs)

    def executescript(self,*args,**kwargs):
        with _uncached():return super().executescript(*args,**kwargs)


class Connection(sqlite3.Connection):
    def cursor(self,factory=Cursor):return super().cursor(factory)
    def execute(self,*args,**kwargs):return self.cursor().execute(*args,**kwargs)
    def executemany(self,*args,**kwargs):return self.cursor().executemany(*args,**kwargs)
    def executescript(self,*args,**kwargs):return self.cursor().executescript(*args,**kwargs)
