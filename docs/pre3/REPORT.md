# pre.3 development: completed correction followed by General import

Base: published pre.2, commit f8e128c9e5aec462d16f987d2e71dbe0d02f1549.
No version bump, release, tag or registry push. All test data is synthetic. No NAS access.

## A–F: cause and control flow

A. A completed SQLite metadata row is a domain commit, not an F14 completion receipt.
`_complete_task` commits output hash, verification and completed_at before the swap
journal is retired and before the outer `reserve` context finishes. Process death or
an I/O error at that boundary retains the exact reservation. This is reproducible
with the released pre.2 code. Which event created the real historical reservation
is not established by the supplied completed row alone.

B. Once the physical swap, verified output and journal cleanup are complete, the
metadata domain should durably attest success before F14 acknowledges and removes
its active record. Pre.2 wrote a permanent domain outcome for verified failures,
but ordinary successful General corrections did not take that path. F14's temporary
finished receipt only exists during the final reservation cleanup.

C. Root admission and `_assert_startable` fence root mutations and bad bindings;
valid durable operations may coexist during normal execution. General-import
admission checked source bytes and known origins but did not settle a predecessor
metadata reservation. Its worker copied/staged/published the file and removed the
General source after comparing the imported hash. Therefore the released code can
accept a fully verified import while the old completed metadata intent remains.
The reproducer executes the real published pre.2 correction and import code, not a
fabricated catalogue or a filename-based move.

D. Pre.2 `_qualify` derives the source from the immutable General task path. Even
for status completed, `_source_proof` opens that same path using output_sha256.
There is no import-continuity branch. A legitimate missing old path is consequently
reported as `metadata_outcome_unverified: [Errno 2] ...` and startup is paused.

E. The new read-only transfer qualifier follows an exact completed
`metadata_general_import`: deterministic admission ID (or the specifically qualified
RC14 timestamp ID), recomputed full-manifest SHA-256 fingerprint, full selection,
source-stage path, job timestamps/signatures/fingerprint, completed protocol,
exclusive publication journal, exact main catalogue row/family, canonical source
family and immutable members. The destination is taken only from the journal and
must agree with the catalogue, central-stock role binding, current output SHA/size
and the journal's published inode. There is no filename/date/hash scan across media
or libraries. Missing, duplicate, contradictory or unsupported evidence fails closed.
RC14 timestamp IDs are accepted only for Main, with a plausible admission interval
and the same complete publication/catalogue/immutable-origin checks; the timestamp
is never destination or completion authority. A later sort/archive move that no longer agrees with this publication journal is
not guessed; it needs its own reviewed continuity chain.

F. The previous path confused an unreconciled successful intent with an unfinished
write once the source was moved. The fix distinguishes verified rollback, verified
completion in General, and verified completion followed by import. `completed`
alone still authorizes nothing. A failed correction retains its original error.

## Implemented correction

- Successful General apply now persists the full verified outcome before returning
  through its original F14 lease. SQL status, original and output hashes, original
  reservation ID/bindings and immutable task snapshots are retained.
- General-transfer admission settles qualified predecessor operations before staging;
  any remaining unknown intent refuses admission. The worker also refuses source
  cleanup when another unresolved predecessor is present. It retains source/staging
  bytes and documents the cleanup warning instead of deleting unverifiable files.
- A private `general-handoff.lock` serializes correction preparation/apply, transfer
  admission and General source cleanup. It complements the existing physical metadata
  writer and F14 exclusion. It is acquired before a new correction reservation and
  is reentrant only within the current call context. It creates no alternate metadata
  writer authority. Source cleanup uses pinned directory descriptors and rechecks the
  measured file identity before unlinking its exact verified source.
- Historical missing-source recovery closes only the original metadata reservation
  after full transfer proof. The metadata row stays byte-for-byte unchanged. A prior
  completed outcome is never overwritten: `metadata-location-<nonce>.json` appends the
  new qualified location and retains the entire original outcome.
- Source/target failures now retain the full expected path in their diagnosis.
- Legacy startup now also fences unknown durable intents when requesting all records;
  ordinary live-request behavior remains unchanged. Appdata startup already had this
  fence. Unknown operations are never cleaned up or completed by this patch.

## Bounded recovery access

The authenticated storage page now offers a read-only diagnosis of libraries and
all pending operations, including linked task status, hashes and expected paths.
Known, root-qualified single-file tasks are distinguished from storage/unknown
operations. No diagnosis grants completion authority, hashes a whole library on
page load, mutates SQLite, moves media or starts background workers.

Only the exact GET `/api/settings/recovery-diagnostics` is added to the storage
middleware allowlist. Existing owner authentication remains outside that middleware.
POST/mutations remain fenced. German/English and mobile/desktop rendering are tested;
all evidence is rendered as text, never trusted HTML.

This is a read-only recovery mode, not a blanket release or physical quarantine.
General and central stock are shared between libraries. With two of the three real
operations still unclassified, a safe per-library write release is not proven.
Workers and mutations therefore remain paused until every relevant shared intent
is qualified. Users can inspect library/task diagnoses while that fence remains.
Original folder restoration/replacement behavior is unchanged.

## Real-state assessment and limits

The supplied JPEG task, hashes and reservation are compatible with the reproduced
historical case, but do not prove its actual import destination. No real target is
assumed and none was read from TrueNAS. Recovery without Clean Slate is demonstrated
for a complete consistent historical chain, both with and without old intent/outcome
receipts. The real instance is eligible only if its actual evidence qualifies.

Other remaining blockers can include metadata reintegration intents, interrupted
General/folder imports, trash operations, backup deletion, sort/SSD operations,
root mutations, missing journals or different generations/mounts. They have distinct
domain authorities and must not be completed from a JPEG's metadata status.

See READ-ONLY-DIAGNOSIS.md for exact commands to collect the three original records,
state/bindings, linked SQL tasks/jobs, General-import manifests/publication records
and actual candidate destination fingerprints. Until those are available the other
two operations and the complete real NAS recovery remain **UNCLASSIFIED**.

Native TrueNAS/NFSv4 and real DNG-1.7 writing remain NOT_RUN; synthetic DNG refusal
is not a DNG writing acceptance. ExifTool is not upgraded. Actual historical cause
of the residual nonce, later media moves unsupported by the available journal, and
external host tampering beyond the existing cooperative-host trust model remain
limits. No weakened origin, F14, journal, hash, archive or storage repair checks.

## Test evidence

Targeted local reproduction before correction: exact pre.2 missing-path startup
failure after a real General import; one failed test saved under the task evidence.
Subsequent positive/negative cases and final Linux/container results are recorded in
PROGRESS.md / EVIDENCE.json after completion. The targeted CI does not publish images.


First Linux gate 40967129148: 176 passed, one old F14 assertion expected legacy
startup to succeed with an unknown orphan lease. The updated contract deliberately
fences that state, matching appdata behavior; the test now requires refusal and still
checks all original bytes/evidence after three real restarts. No security check was
relaxed. An additional source audit found RC14's timestamp General IDs; dedicated
unchanged-RC14 positive/negative fixtures now cover that historical format.
