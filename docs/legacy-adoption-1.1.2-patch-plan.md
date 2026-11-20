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

The initial characterization test is deliberately marked `xfail(strict=True)`
for the confirmed name-allocation problem. It is **evidence**, not a fix.
Do not publish or deploy this branch until the gates above are implemented and
the xfail has been converted to a passing regression test.
