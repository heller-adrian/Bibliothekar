"""Bounded retries for explicitly idempotent, SQL-only transactions."""
from contextvars import ContextVar
from functools import wraps
import sqlite3
import time

WRITE_WAIT_MS = ContextVar('idempotent_write_wait_ms', default=30000)


def idempotent_write(function):
    @wraps(function)
    def call(*args, **kwargs):
        token = WRITE_WAIT_MS.set(250)
        try:
            for attempt in range(3):
                try:
                    return function(*args, **kwargs)
                except sqlite3.OperationalError as error:
                    code = getattr(error, 'sqlite_errorcode', 0) & 255
                    if code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or attempt == 2:
                        raise
                    time.sleep(.05 * (attempt + 1))
        finally:
            WRITE_WAIT_MS.reset(token)
    return call
