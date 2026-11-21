# Bibliothekar 1.1.2-rc.2 — development gates

Development branch based exactly on `v1.1.2-rc.1` / PR #43 head `4d6b1eb`.
**DRAFT: not approved for production, do not run the existing RC1 adoption script.**

## Verified real-library findings (21 Nov 2026)

- Prepared but not applied package `b95ce4e3d8f1418b9ea97e26ca6f59d7`: 10,346 moves, 35 event documents, approx. 560 GiB, 7,051 projected family keys.
- 2,908 `_Burst_` target files were examined on TrueNAS: 2,373 lacked EXIF subseconds, 506 were XMP sidecars, and 29 had explicit fractional values consisting only of zeroes (22 `000`, 7 `00`). There was **no verified nonzero SubSecTime ignored** in those 2,908 files.
- 708/799 XMP target files had no media file with the same resulting stem. In the 506 XMP burst subset, 451 lacked a media target stem; 440 had a same-stem original media candidate in the same capture-time slot. These are candidate anomalies, not proof that all sidecars are correctly attachable.
- Real `DSCF2915.RAF`, `DSCF2915.JPG`, and `DSCF2915.xmp` report identical original capture time (16 Apr 2025 19:37:26), camera FUJIFILM X-H2S, and original photo exposure. The XMP additionally contains `XMP-crs:RawFileName=DSCF2915.RAF` and an Adobe history/document identity.
- RC1 placed RAW/JPEG into one target stem `..._Burst_001` but the sidecar into `..._Burst_002`. This is a blocking error.

## RC2 areas and acceptance criteria

### 1. Sidecar association and naming (release blocker)
- Accept `foo.xmp`, `foo.RAF.xmp`, and sidecars located in arbitrary folders, without assuming labels such as `RAW`, `JPEG`, or `Sonstiges`.
- Read `XMP-crs:RawFileName` when available, match the exact referenced source filename; corroborate with compatible capture time, camera and other identity evidence; never resolve duplicate possible owners by arbitrary order.
- RAW/JPEG/XMP members of **one qualified capture** share one target stem. Edited XMP parameters do not by themselves split the capture. Unknown/contradictory cases remain in review.
- Preserve source-to-family registration in the final catalogue; verify import and legacy-adoption paths independently, plus registration after execution.
- **Additional user decision after the original diagnostic plan:** on moving a positively bound sidecar, update only its existing `XMP-crs:RawFileName` reference to the new RAW basename. This is a *content mutation* and must not enter production until the manifest records expected original and resulting hashes, the executor enforces both, an authentic copy of the original bytes is recoverable, and rollback restores those bytes exactly. Preserve all other XMP metadata. No shortcut mutation of an existing RC1 manifest.
- DNG sidecars and links to original RAW files require explicit nonambiguous handling.

### 2. Burst and copy naming (release blocker)
- Keep existing `capture_stem()` policy. If original trustworthy SubSecTime is present and differentiates images, use `YYYYMMDD_HHMMSSmmm_Kamera.ext`; do not invent milliseconds from rounded timestamps, editing timestamps or filesystem times.
- Distinct captures colliding on a real millisecond use `_001`, `_002` consistently.
- Equal SHA-256 source occurrence copies receive reproducible, sequential `_Duplicate_001`, `_Duplicate_002` labels without gaps or cross-group mixing.
- Compare all 10,346 planned source-target mappings in an unexecuted RC2 manifest against the original evidence, including per-family sidecars and collision aliases.

### 3. Long-running confirmation (release blocker)
- Prepare the binding/manifest in a server-owned durable job that survives browser reload, client disconnection and workstation restart.
- Persist phase, number of files, bytes processed, totals, last error, and committed completion; poll from the existing UI on reopen.
- Idempotent start, no duplicate second worker, interruption/resumption policy, and cancellation semantics consistent with journal/host-identity proof.
- Avoid redundant rehashes; preserve before-application protection against changed file bytes, replacing long SQLite IMMEDIATE locks with short durable state transitions where safety allows.

### 4. Initial setup preferences — including AFTER adoption (release blocker)
- Before the existing "take over an existing collection / start with empty library" decision, present the existing **Ordnerstruktur und Benennung** settings with saved defaults and a **Weiter** action that requires no changes.
- Reuse the actual editor controls, validation logic, read/write APIs and source-of-truth of the settings dialog rather than making an independent imitation: `/api/settings/event-naming` (`library_registry.settings_json.event_naming`) and `/api/settings/event-folder-layout` (catalogue `app_settings.event_folder_layout_default`), including normal-event, subevent and collection-name controls that already exist.
- The current first-setup middleware rejects normal settings routes while `initial_library_setup.decision=choice`. Add a **narrowly scoped, setup-only admission exception** for the genuine existing naming/layout endpoints; no general bypass of adoption or recovery protections. The initial preferences route should not be shown for an existing/complete installation.
- **Persistence is mandatory:** choosing custom values, refreshing the browser, proceeding through either the "empty" or "existing" choice, finishing the 35-event adoption, opening the normal settings dialog, and later creating/importing events must all use exactly the same persisted values. Completing the adoption must not reset these preferences to defaults.
- Preference changes must not silently rename previously planned or archived event paths. Show explicit effects on newly created events, previews and the current adoption draft; do not invalidate an immutable prepared package behind the user's back.
- Acceptance tests must cover (1) defaults rendered and **Weiter** with no modifications, (2) changing naming and folder layout before the choice, (3) saving and reloading before choosing, (4) choosing **both** empty and legacy-adoption paths, (5) read-after-finalize and ordinary post-adoption event creation preserving the values, and (6) no access to setup-only preference write routes when installation is complete.
- No duplicate settings database/table and no independent configuration state; backward-compatible with already configured installations.

### 5. Keep the saved user setup and prove upgrade safety
- User's saved **35 event definitions** and import decision must not be thrown away. RC1's confirmed immutable script package cannot simply be rewritten.
- Define a safe, explicitly gated retirement/replanning path for a *not applied* package, with old command invalidation and fresh host proof. Don't manually edit manifests, SQLite tables, or original files.
- Read-only planning and diagnostic scripts must never move/rename user data.

### Release gates
1. Focused unit/regression tests for the exact real DSCF2915 metadata and name collision/duplicate corner cases.
2. Isolated executor/rollback tests for byte-level sidecar updates, crash/recovery, unchanged-media proof, linked metadata preservation.
3. Eight-part backend QA + coverage + container/preflight + native TrueNAS ZFS verification.
4. Fresh RC2 test manifest with all targets audited; actual 35-event adoption and independent verify/registration.
5. Publish `v1.1.2-rc.2` using existing workflows only; stable `v1.1.2` remains blocked until real acceptance.

## Implementation status
- [x] Isolated RC2 branch created from qualified RC1 commit.
- [x] Initial `XMP-crs:RawFileName` ingestion and conservative cross-folder association patch; synthetic regression tests added.
- [ ] GitHub QA confirmation of first XMP patch.
- [ ] Controlled sidecar-content transform and recoverable executor integration.
- [ ] Complete deterministic collision/duplicate fixes.
- [ ] Durable job, reload-safe progress UI, and setup preferences.
- [ ] 10,346-file manifest recheck and release gates.
