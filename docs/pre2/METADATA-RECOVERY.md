# pre.2 development candidate: failed general metadata writes

## Scope and state

Base: published `v1.0.0-pre.1` (`282aeba2dd8464f30c8484034759cbb0fd8e0823`).
This branch is a technical correction and isolated QA candidate. No version tag,
release or registry push is authorized or performed. Production TrueNAS was not accessed.

## Reproduced cause

`execute_metadata_correction` owns the durable F14 metadata reservation. The nested
`apply_metadata_correction` writes an exclusively created staging copy in General.
`write_metadata_datetime` raises when ExifTool refuses that write. This occurs before
`prepare_swap` and the first rename of the original. The existing preparation-journal
recovery validates the original hash and the owned staging inode, removes its own
staging copy and journal, and keeps the metadata task `blocked` with its error.

An exception is intentionally insufficient to finish an F14 operation. Previously,
no domain outcome bridged this verified rollback to F14 completion. Startup recovered
swap journals, but its reservation recovery only qualified library-family reintegration,
not general `execute_metadata_correction` or direct general `apply_metadata_correction`.
The remaining reservation therefore caused `unresolved_reservation`. Other formats and
other failures on this same path can cause the same secondary startup block.

The isolated tests execute the actual published pre.1 source to create this state,
including generation `[2,0]`, a single blocked task, and no new-style intent receipt.
The ExifTool failure is injected on the staging copy, including partially written bytes.

## Correction and preserved authority

New general attempts persist `metadata-intent-<original nonce>.json` before writing.
The intent retains the complete reservation and immutable task/source fingerprint.
On failure, the domain may return an internal rollback result through the nested F14
leases only after full qualification. F14 then completes normally; the outer public
function still raises the original error. The task remains blocked and its original
error remains available. A subsequent retry no longer cancels an older blocked general
task. Library correction behavior is unchanged.

Startup runs the same qualification after physical journal recovery and after its own
startup lease exits, before any runtime worker starts. It reopens exactly the old
operation key, nonce, generation, roles and database. A recovery failure cannot use an
old transient `finished-*` receipt as a bypass. No new replacement reservation is used.
The permanent `metadata-outcome-<nonce>.json` retains the original reservation, original
and final task snapshots, source identity, size, SHA-256 and the decision. Normal F14
completion removes the active operation record through its existing protocol; the
original record remains in this permanent domain receipt.

Qualification requires:

- Exact operation function and ID fields; exact persisted reservation and filename.
- Registered database/library, matching workspace and every required role binding,
  generation and, for appdata format 3, mount provenance.
- Matching immutable intent, or, for historical execute records, exactly one matching
  general task. Duplicate historical tasks cannot be guessed apart.
- Correct task library, canonical path, status and consistent output/verification fields.
- No pending swap journals or unknown technical staging/backup files.
- A regular single-link source opened without following symlinks through pinned parents;
  exact expected size/SHA-256 and stable descriptor/named inode, mode and timestamps.
- For rollback, original fingerprint and no committed output; for completed-swap recovery,
  committed output fingerprint and verification. Existing swap recovery decides physical
  rollback/commit first and is not weakened.
- Revalidation after persisting the outcome. Late corruption retains the active reservation.

A bare `blocked` status, absent journal, or old receipt authorizes nothing. Foreign bytes,
missing backups, changed bindings, ambiguous tasks and malformed evidence stay blocked.
No schema reset, lost-history reinterpretation, retention cleanup or archive write is added.
These checks use the existing cooperative host/F14 trust model; they do not claim protection
against a host administrator able to forge both SQLite and private control evidence.

## DNG 1.7 is a separate issue

Published pre.1 container evidence records ExifTool 12.57. ExifTool's official
[history](https://exiftool.org/ancient_history.html) records DNG 1.7 support from 12.69.
The [official application documentation](https://exiftool.org/exiftool_pod.html) defines
exit 1 as error; `-m` ignores minor errors and validation. This patch never adds `-m`.

The exact untested-DNG diagnostic is surfaced with the native exit code and full output.
It is rejected even if a tool emits it with exit 0. Other successful warnings remain
visible in logs, and existing metadata verification is still required. ExifTool may have
changed its temporary copy before refusing. That does not establish that the original
changed: the reported error occurs before original exchange, and actual bytes must be
qualified by hash. No assertion about the real NAS file's hash is made here.

No real DNG-1.7 original was provided. Container fixtures use generated JPEG content named
`.dng` with a controlled writer refusal; read-side ExifTool is real. Native DNG 1.7 writing
and TrueNAS/NFSv4 acceptance remain **NOT_RUN**. Upgrading ExifTool is outside this patch.

## Test plan and evidence

`tests/backend/test_pre2_metadata_abort.py` covers published historical failure, future
refusal, exact error/history preservation, repeated attempts, partial staging output,
crashes during write/after backup/after swap/after DB commit, SIGKILL after outcome and
F14 receipt, startup worker gating, and contradictory bytes, links, tasks, journals,
backups, generations and reservation identities.

`.github/workflows/qa-pre2-metadata.yml` uses only the dedicated self-hosted Linux runner.
It runs targeted metadata/F14/provenance/storage regressions, builds a local test image,
and executes `qa/pre2/container.py` with real supervisor, UID 568, network disabled,
RW synthetic appdata/workspace and RO synthetic archive. The immutable released pre.1
image first reproduces the actual blocked restart. The candidate must recover it,
retain the task row and nonce evidence, support authenticated library access and another
refusal/restart, recover a real web-process SIGKILL, and reject foreign bytes.

The existing `qa/pre/startup_container.py` and `qa/pre/container.py` also check the 4,000-file,
two-library startup and the 14 RC14-corrected iPhone JPEGs with offset +13:00. No full
unrelated test matrix or publication workflow is requested. Results are recorded in
`PROGRESS.md` after execution and in the workflow's evidence artifact.

The old 0.33.2 route translation unit test now invokes the route body (`__wrapped__`):
its fake `/tmp/workspace` cannot pass today's admission guard. Actual F14 admission is
covered by dedicated fixtures and real authenticated container tests; production guards
are unchanged.

## Existing TrueNAS state / eventual upgrade

Do not remove the reservation, mark SQLite completed, delete journals or use Clean Slate.
A future approved candidate upgrade retains existing appdata, workspace and RO archive
mounts and runs exactly one app instance. Startup itself qualifies the historical state.
A qualified blocked task stays blocked as historical evidence while normal use resumes.

If qualification fails, keep the authenticated recovery shell and precise
`metadata_outcome_<reason>: <path>` diagnosis. Read-only diagnostic evidence may still be
needed: full task source/output/verification/detected fields, current source size and
SHA-256, complete reservation/state/mount bindings, and remaining journal/staging/backup
inventory. The reported task status/error alone cannot prove this real instance safe.
Unknown or contradictory evidence requires a separate reviewed recovery decision.

## Executed results (2026-10-29)

- [Linux run 40957407776](https://github.com/heller-adrian/Bibliothekar/actions/runs/40957407776): **SUCCESS**, source `ff1cdf3557b87e5f390f8c1f71abe179ac9d4a52`.
- 148 targeted Linux regression tests passed; zero failures/errors/skips. Includes all
  32 new domain recovery cases and existing metadata, F14, provenance and RC12 storage tests.
- Real supervisor containers: all three new historical/future-refusal, foreign-byte and
  SIGKILL cases PASS. Original task row preserved, exact reservation retained in the
  permanent receipt, authenticated access/restart works, independent RO archive unchanged.
- Existing 4,000-file / two-library upgrade and restart: PASS, 6.023 / 5.732 seconds on
  the isolated Linux runner. Origin evidence and 14 corrected files preserved.
- Actual released RC14 fourteen-JPEG correction/reintegration upgrade: PASS. Offset
  +13:00, same pending reintegration reservation, second-library projection and archive
  fingerprints remain correct. Candidate native ExifTool reports **12.57**.
- Evidence artifact `12933834151`, downloaded ZIP SHA-256 verified against GitHub:
  `46a5015aaacf31c5307bfa2a5c9d2b34efe3594ba88073121748e60a4f201668`.
  Per-file hashes and application-tree identity are recorded in `EVIDENCE.json`.
- Local macOS: 32 new cases and 29 metadata/storage cases pass. These supplement the
  decisive Linux results; they are not native TrueNAS acceptance.
- Actionlint, Python compilation and `git diff --check`: PASS. The existing pre.1 tag,
  published images and application version are unchanged. Only a local QA image was built.

The implementation is suitable for a separately approved pre.2 candidate. It fixes the
secondary permanent startup block; it does not claim DNG-1.7 writing support. Real NAS
state remains unexamined; startup must perform its own full qualification at upgrade.
Native TrueNAS/NFSv4 and a genuine DNG-1.7 original test are **NOT_RUN**. No additional NAS
information was needed to implement and reproduce the fix. Read-only evidence is needed
only to diagnose a real state that does not satisfy the documented qualification.
