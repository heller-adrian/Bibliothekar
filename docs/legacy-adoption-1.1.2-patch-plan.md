# Bibliothekar 1.1.2: library-adoption duplicate occurrence and naming patch

Development only. Not qualified for release until the exact commit passes the
full eight-part Backend QA, synthetic native ZFS smoke and manual review.

## Contract: existing libraries only

The normal camera/folder-import Burst implementation is **unchanged**.
Legacy adoption reuses its existing `capture_stem()` helper to format actual
EXIF SubSecTimeOriginal milliseconds when two captures share a second.
Never invent missing milliseconds.

- Capture identity comes from camera metadata, capture time, camera filename
  and corroborating identity / exposure evidence, never named source folders.
- Same SHA-256: byte-identical *physical occurrences*, not two different
  canonical contents. All occurrences participating in a new adoption batch
  keep their own source and eventual archive paths.
- Manual adoption: unchanged file names when there is no target filename
  collision; different bytes with the same complete target filename receive
  `_001`, `_002`, etc. for **all** members of the conflicting set.
  Matching byte-identical media receive `_Duplicate_001`,
  `_Duplicate_002`, etc., also for the first physical occurrence.
  RAW/JPEG/DNG with distinct endings need no suffix merely because their
  stems are equal. Associated XMP sidecars follow the family suffix.
- Script adoption: canonical date/time/camera naming remains in effect.
  Real distinct milliseconds are appended to the time as before.
  When different contents still have the same generated millisecond stem,
  *every* affected family gets `_001`, `_002`, etc.
  Real duplicate copies receive `_Duplicate_001`, `_Duplicate_002`, etc.
  No first copy is arbitrarily called an unsuffixed original.
- Prior registered archive media remain protected against accidental
  re-import; new duplicate occurrence handling is for multiple physical
  copies selected in the **same** initial library adoption.
  Explicit user destination overrides are not silently changed.
- Reused SHA-256 contents in a single adoption are separate source occurrences
  while the global registry keeps the single canonical-family ownership claim.
  Each source-family registration records its individual assigned event.
- No archive overwrites, no automatic source-file deletion. All transfers
  must still pass the existing FD-bound source-identity and SHA-256 verification.

## Remaining safety boundary

Multiple byte-identical *members within the same already-grouped local family*
that demand the exact same extension/target path, or conflicts between
already-registered media and a partly new family, remain blocked for review.
The normal import workflow and other libraries' ownership must not be
weakened to conceal these special cases.

## Qualification before RC

- Verify arbitrary nested source folders, camera-family identity and sidecars.
- Verify two, three and more identical copies: all numbered from 001; each
  physically retained and correctly catalogued under one canonical identity.
- Verify same second with differing real milliseconds; exact same
  millisecond with differing bytes; missing SubSecTime; prior archived names.
- Verify manual and scripted execution, interruption/retry, global registration,
  subsequent normal imports, cross-library conflicts and source retention.
- Verify 8k+ source files and report actual collisions and duplicate counts
  from a new read-only archive plan.
- Publish only after all regression and native ZFS checks succeed on the
  *exact* source commit through the existing `publish-container.yml`.

No production TrueNAS source, archive, application state or stable v1.1.1
release has been modified by this development branch.
