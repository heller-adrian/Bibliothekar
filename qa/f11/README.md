# F11 – durable trash reservations

Base: `35299e900b3aa38a9a45935d2a6d5fd15f75be6f`. F12/F13 are not included.

Reservation publication, restore preparation/cleanup, inventory, selective deletion,
full HTTP deletion and recovery use the existing reentrant RLock + flock for the
same workspace. HTTP preflight uses nonblocking acquisition (409 on contention).
The actual deletion reacquires and holds the lock through its fresh reservation
check, file staging, individual database commits and journal cleanup. A competing
reservation either precedes that decision and prevents deletion, or cannot be
published until deletion has finished. There is no shared SQLite/WAL transaction.

A synced, atomically published restore intent precedes create_job's SQLite commit.
An orphan, failed/completed-without-cleanup intent remains protective. Only proven
cleanup or a committed known-file restore releases its paths. Release evidence
must cover the complete original selection with disjoint staged/restored paths;
cleanup requires an explicit skipped list containing only staged paths. Unreadable evidence
and overlapping legacy delete/restore journals fail closed; manual investigation
is required. No automatic override or journal deletion is introduced.

Full HTTP empty uses the existing F1/F2 selected-deletion journal over its complete
file selection. Links/special entries or unexplained missing catalogue entries
block it. Newly appearing unsnapshotted files are not swept. The historical low-
level filesystem-only helper retains its interface; it now shares the reservation
lock/check. The HTTP entry supplies the catalogue scope via a request ContextVar.

Restore pre-inventory must share this lock, otherwise it could modify snapshots
inside a live deletion (the observed F19 interleaving). This is a necessary narrow
prerequisite; other F19 combinations are not declared repaired. F24 (external path
component replacement) and R1 (restore-collision recovery) remain open. Advisory
flock coordinates cooperating processes, not arbitrary filesystem editors.

Run full backend: `PYTHONPATH=. pytest -q -p no:cacheprovider -o addopts='' tests/backend`.
New deterministic cases: `tests/backend/test_f11_trash_reservation.py`.
Genuine subprocess SIGKILL hooks extend `tests/backend/recovery_0562/worker.py`;
existing regression assertions are unchanged. Evidence is written under pytest's
external basetemp, never into application storage.

`original/` contains byte-identical audit files; hashes are in
`original-integrity.json`. Run outside the source tree using:

```
F11_QA_ROOT=/tmp/f11-original F11_QA_SOURCE_ROOT=$PWD python qa/f11/run_original.py f11
F11_QA_ROOT=/tmp/f11-neighbors F11_QA_SOURCE_ROOT=$PWD python qa/f11/run_original.py neighbors
F11_QA_ROOT=/tmp/f11-f24 F11_QA_SOURCE_ROOT=$PWD python qa/f11/run_original.py f24
```

Do not reinterpret their exit codes. The historical F11 test requires A.JPG still
in trash after three actual startups. A successful resumed restore legitimately
moves A to the central stock, so that location assertion can remain FAIL even when
empty was rejected with 409 and the exact original SHA-256 survives. The new
`test_f11_original_boundary_and_restore` separately asserts rejection, original
trash bytes before startup, and one matching copy after three successful startups.
Open R1/F24 audit failures are kept outside the regular backend suite. The workflow
retains raw failure status for every historical probe; its overall red status must
be distinguished from the complete backend job's outcome.

Scope: synthetic local/Linux runners. No NAS, TrueNAS, ZFS, power-loss or external
SMB platform acceptance follows from these tests.
