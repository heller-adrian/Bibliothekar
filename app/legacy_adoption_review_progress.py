"""Report live transfer bytes and persist only independently verified progress."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic

from app.database import database_connection
from app.legacy_adoption_review_cancel import cancellation_check


@dataclass
class Transfer:
    database: Path
    job: str
    family: str
    started: float
    batch: str | None = None
    initial: int = 0
    written: int = 0
    verified: int = 0


_current = ContextVar("legacy_review_transfer", default=None)
_active = {}
_lock = Lock()


@contextmanager
def track(database, job_id, family, batch=None):
    transfer = Transfer(database, job_id, family, monotonic(), batch)
    transfer.check = cancellation_check(database, job_id, batch)
    key = (database, job_id)
    with _lock:
        _active[key] = transfer
    token = _current.set(transfer)
    try:
        yield
    finally:
        with _lock:
            if _active.get(key) is transfer:
                del _active[key]
        _current.reset(token)


def wrote(count):
    transfer = _current.get()
    if transfer is not None:
        with _lock:
            transfer.written += count


def transfer():
    return _current.get()


def check(*, force=False):
    current = transfer()
    if current is not None:
        current.check(force=force)


def checkpoint(count, *, recovered=False):
    transfer = _current.get()
    if transfer is None:
        return
    with _lock:
        if recovered:
            transfer.initial = transfer.written = transfer.verified = count
        else:
            transfer.verified += count
        verified = transfer.verified
    with database_connection(transfer.database) as connection:
        connection.execute(
            "UPDATE legacy_adoption_review_batch SET bytes_verified = ? WHERE job_id = ? AND family_key = ?",
            (verified, transfer.job, transfer.family),
        )


def batch_details(connection, database, job_id):
    totals = connection.execute(
        """SELECT coalesce(sum(bytes_total), 0), coalesce(sum(bytes_verified), 0)
             FROM legacy_adoption_review_batch WHERE job_id = ?""", (job_id,),
    ).fetchone()
    total, verified = totals
    with _lock:
        transfer = _active.get((database, job_id))
        snapshot = vars(transfer).copy() if transfer else None
    active = eta = None
    written = verified
    if snapshot:
        row = connection.execute(
            """SELECT bytes_total, bytes_verified FROM legacy_adoption_review_batch
               WHERE job_id = ? AND family_key = ? AND state = 'pending'""",
            (job_id, snapshot["family"]),
        ).fetchone()
        if row:
            transferred = min(row["bytes_total"], snapshot["written"])
            written = min(total, verified + max(0, transferred - row["bytes_verified"]))
            active = dict(family_key=snapshot["family"], bytes_total=row["bytes_total"],
                          bytes_verified=min(transferred, snapshot["verified"]), bytes_written=transferred)
            elapsed = monotonic() - snapshot["started"]
            measured = transferred - snapshot["initial"]
            if elapsed >= 2 and measured >= 16 * 1024 * 1024 and total > written:
                eta = round((total - written) * elapsed / measured)
    recent = {row["family_key"]: row["state"] for row in connection.execute(
        """SELECT family_key, state FROM legacy_adoption_review_batch
           WHERE job_id = ? AND state IN ('copied', 'failed') ORDER BY family_key DESC LIMIT 80""", (job_id,),
    )}
    return dict(bytes_total=total, bytes_verified=verified, bytes_written=written, active=active,
                estimated_seconds=eta, recent=recent)
