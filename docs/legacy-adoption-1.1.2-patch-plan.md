# 1.1.2 legacy adoption: safe duplicate and filename-collision repair

Development branch from the qualified 1.1.1 mainline. **Not production-ready.**

## Observed failures

1. Legacy family keys use source-relative directories. A RAW and JPEG from distinct
   old format folders can be planned as separate families even when they represent
   one camera capture. The target-name allocator reserves complete stems; it then
   assigns `_Adopted_001` to a non-conflicting extension.
2. The planner raises `Einzelne Mitglieder einer Dateifamilie ...` when one member
   is registered and another is new, or two members share one checksum.
3. Historic archives may intentionally contain content-identical copies. Releasing
   the planner's guard alone is **not safe**: global content uniqueness, source
   ownership, and event identity need explicit multi-occurrence semantics.

## Implemented development changes (not yet release-qualified)

- Local SHA-256 duplicate copies are now classified during inventory, before
  event planning, when the losing family is a strict content subset (or exact
  content match) of a deterministic canonical family. A complete RAW/JPEG
  family wins over an isolated copied JPEG.
- Differently edited XMP files are never silently deduplicated by media hash.
  When their only primary media copy is excluded they are kept at the source
  and reported as detached.
- A JPEG shared by two families whose RAW checksums disagree is **not**
  automatically collapsed; the conservative protection remains.
- The plan summary now explicitly counts renamed files and affected families,
  rather than requiring manual traversal of paginated results.
- The previously conflated mixed-registration and intrafamily-hash failures
  now have different explanatory messages.
- Real-device evidence is captured in isolated synthetic tests. Production
  images, databases and archive remain untouched.

**Limitation:** The current change skips exact redundant primary media at the
source; it does NOT yet permit copying both byte-identical physical occurrences
into different archive events. That behavior needs a separate, compatible
extension of source-occurrence versus canonical-content registration.

**Limitation:** Unnecessary _Adopted_ suffixes from still-unverified RAW/JPEG
pairs remain possible by design. The concrete `Export/Foto-Export` folder case
is now handled under evidence-gated matching; additional historic layouts must
be proved from real metadata before expanding the scope. The final count of
renames against the user's full dataset has not been measured after this fix.

## Required implementation gates

- [ ] Inventory metadata: model candidate family matching across source format
      folders, preserving exposure/date/camera contradictions as review cases.
      Never join solely by shared camera filename.
- [ ] Name planner: reserve actual targets and verified capture identities.
      Distinct captures with colliding stems still need one unique family suffix.
      RAW/JPEG/XMP of one verified capture use one common stem.
- [ ] Duplicate occurrences: define source occurrence vs canonical content,
      and handle mixed registered/new members, identical hashes, and intentional
      copies without inventing a second canonical media identity.
- [ ] Preserve explicit user destination overrides and existing archive file
      reservations. No overwrites, no automatic modification of read-only archive.
- [ ] Preflight all blocking cases before manual event planning, and support
      regenerating a plan from an unchanged draft.
- [ ] Tests for source RAW/JPEG split, XMP ownership, conflicting capture metadata,
      same stem/different capture, content-identical historical copies,
      existing global claims across two libraries, idempotent re-run,
      8k-file planning and source/target drift.
- [ ] Run focused tests and complete 8-way Backend QA + synthetic ZFS preflight.
      Publish container image **only after** full qualification.

## Real system evidence

No TrueNAS mutation or reset is required now. If a minimal real-data diagnostic
is later needed, use only read-only queries from an explicitly identified
container and library database. Never upload personal images, image hashes
associated with private paths, credentials or the complete production DB.

## Current branch status

The allocator's deliberately conservative behavior for **unverified**
RAW/JPEG pairs is now checked with a passing regression test. Separately,
the verified `DSCF4762` RAW/DNG/nested-export JPEG case is tested end-to-end
without unnecessary renaming, while alternate DNG variants retain their names.
This is not evidence that every historical folder layout is supported.
Do not publish or deploy until the full qualification gates pass.
