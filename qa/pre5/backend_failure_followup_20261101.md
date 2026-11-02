# Pre.5 backend regression gate – 2026-11-01

Evidence source: [GitHub Actions run 41331175415](https://github.com/heller-adrian/Bibliothekar/actions/runs/41331175415), backend job 124922437608 (aborted by concurrency after 7 of 8 backend partitions).

Exactly 19 *observed*, distinct failed pytest nodes are pinned in `qa/pre5/backend_19_previous_failures.json`. These failures were seen across 7 completed partitions (2,236 passes, 19 failures); the eighth partition had not finished. Do not interpret the 19 as an exhaustive failure count or as 19 distinct root causes.

The revised test harness now sets up the required real synthetic registry, library identity, and F14 root-control baseline before registered metadata operations. The code-side missing-database guard remains fail-closed. Historical R14/RC14 crashes with missing prospective ownership evidence remain blocked: a green local fixture is not authorization to resume old unproven mutations.

The full Pre.5 workflow must first run these exact 19 nodes in an isolated F14 Linux harness and stop on any failure. Only then proceed to the 147-node historical gate, complete backend partitions, frontend, and container. A **release requires all stages green**, including the immutable historical 14-iPhone-JPEG migration contract. Do not publish or tag based on targeted success.

## Full acceptance after targeted recovery success

GitHub Actions 41351503688 (commit 3d2a9acbce7774cab607ee9f89854068fc5d77b1) passed the isolated 15 recovery contracts and 7 RC14 key/lease checks. Its backend, frontend, container and 19-node full regression gate were skipped. Trigger the full Pre.5 acceptance on this exact source state without relaxing negative migration tests. This checkpoint authorizes tests only; it is not a release signoff.

## Closed initial 19-node gate; full-suite retest

On commit 568a2065f892f1006ff78a46cecbd0fae53093ac, GitHub Actions run 41356554010 passed the entire explicitly pinned 19-node backend regression gate, including the former real-process overlap failure. This does NOT establish full backend or migration acceptance.

The last independent failure was a normal F14 writer releasing its durable operation while another process iterated a stale `operation-*.json` glob result. `operation_health.inspect` now skips an enumerated entry ONLY if the file vanished after enumeration; still-present unreadable/symlinked entries remain full write fences. New positive and negative tests in `test_rc6_handoff.py` must be exercised in the full backend. No historical RC14 journal, reservation or failed migration evidence is cleared or relaxed.

Next: all 147 historical nodes, all backend partitions, complete frontend and immutable-container historical migration. Release remains blocked until independently green.

## Original 147 gate: seven historically protected metadata cases

Full run 41356769073 passed 15 recovery tests, 7 original RC14-key checks and 19 pinned previously failing backend nodes, then stopped on 7/147 historical backend cases. Four SIGKILL cases could not seed a registered nested metadata fixture because the legacy probe attempted a second registry adoption under different roots. Three immutable F15/F17 wrapper cases were also blocked at seed.

Historical F16/F20 **original** worker was restored byte-for-byte to its previous blob (sha256 manifest enforcement remains authoritative). The fixture helper now recognizes its already provisioned nested `case/fixture` installation and creates precisely the originally intended historic `Arbeitsbereich` and parent `archive` *before* first F14 control. This prevents a later test-only adoption from switching an already pinned binding. The mutable 0562 worker instead uses the existing original registered owner.

Seven observed nodes are pinned in `backend_remaining_7.json`; rerun them without relaxing original fail-closed safety requirements. These tests are diagnostics, not a migration/release waiver.

## Follow-up to seven-node gate

Run 41362934864: four actual SIGKILL tests passed. Three immutable F15/F17 cases failed because two independent registries claimed the same nested synthetic workspace; the application correctly rejected that configuration. The historical nested fixture now creates and uses `fixture/registry.sqlite3` as its **sole** registry from the first F14 baseline; both the untouched F16/F20 original worker and the mutable 0562 worker use that exact registry. No registry or safety checks are bypassed.

## November 2 full-suite findings and metadata preflight fix

Full workflow 41363591064: all 15 recovery contracts, 7 scoped-key tests, 19 previous backend failures, 7 additional historical cases, and 147 originally failing backend nodes passed; frontend also passed. The independent container RC14 14-iPhone-JPEG historic reintegration remains legitimately blocked because the original prospective ownership proof is absent (HTTP 409 retry_original_reservation_identity_required); do not fabricate ownership or silently lift the old F14 lease.

The complete backend suite had separate failures, largely BA-12 legacy direct recovery attempts and one catalog-missing and one F11 restart case. The 8 concrete observed nodes are pinned in backend_full_new_failures.json. A targeted run 41421171252 showed a real ordering bug: a generic metadata swap rollback moved original bytes before a *later* SQLite authorizer refused to mark the job blocked. The application now checks F14 admission before the first filesystem side effect in recover_swap_journal. The negative test preserves the source file and journal byte-for-byte on refusal; original-prospective domain recovery is a separate positive path.

The release remains BLOCKED and cannot be declared complete based on these focused checks.

## 2026-11-02 follow-up: fail-closed ordering fixed and eight-node gate green

The prior eight-node diagnostic (run 41421171252) exposed a genuine safety defect, not just a stale test: generic metadata rollback could mutate a backup/original *before* SQLite later denied marking its task blocked. In `app/metadata_swap_recovery.py`, `recover_swap_journal` now calls the original F14 scope-aware `require_write` before any rollback, commit cleanup, or SQL effects. The corresponding test asserts the source directory remains byte-for-byte identical on refusal, while separately qualifying an original recorded library ownership proof for the legitimate precommit rollback.

Run 41421582444's exact eight-node regression gate passed; a broader focused backend check also proceeds. The independent original RC14 container owner-proof blocker remains open. The next backend-only full suite checks whether this early admission check affects any unrelated functionality; it does not waive the separate RC14 container release blocker.

## 2026-11-02: regression contract update after F14 pre-mutation authorization

Run 41422089815 stopped at the pinned 19-node gate with 8 legacy direct replay failures, all in multiple/reintegration metadata swaps, after 11 passes. The new F14 admission guard correctly refused these generic unowned journal replays. The tests now assert (a) generic replay leaves original bytes and journal unchanged, (b) the qualified original prospective F14 recovery handles precommit cases, and (c) already committed ambiguous cases stay fenced. This changes neither the historical immutable QA nor app safety. Re-run 19 targeted nodes before any complete backend pass.

## 2026-11-02 strict exception assertions

The originally failing 19-node gate completed successfully in run 41425816512 on commit 7e4c943f832c57dfa03f2d5fb824a773fcf88b1a. As a separate strengthening step the updated BA-12 tests now demand the exact F14 `DomainStartupError` code for committed-or-ambiguous swaps and a typed `MetadataSwapRecoveryError` for the still-pending durable journal, not a broad `Exception`. Run the gate again before any longer acceptance test.

## 2026-11-02 strict original refusal codes

Run 41426283357: 16/19 targeted backend cases passed; the other three failed only because an overly narrow test regex demanded `scoped_metadata_recovery_committed_or_ambiguous_effects`. Actual fail-closed reasons were `scoped_metadata_recovery_original_sql_membership_changed` in two reintegration committed-crash cases and `scoped_metadata_recovery_foreign_or_modified_swap_journal` in one completed batch case. Preserve the precise safety denials, unmodified file/journal assertions, and typed DomainStartupError; do not touch application safety or any immutable historical QA. Recheck all 19.

## Nov 2: exact three typed refusal codes fixed

Run 41426283357 failed only three strict test regexes, 16/19 passed. The app correctly refused unsafe committed metadata retries, but two reintegration cases used `scoped_metadata_recovery_original_sql_membership_changed` and the multiple case used `scoped_metadata_recovery_foreign_or_modified_swap_journal`, rather than the incorrectly hardcoded `scoped_metadata_recovery_committed_or_ambiguous_effects`. The test now asserts the observed exact typed denial while preserving file/journal unchanged and no app changes. Run 41427081196 subsequently passed all 19 pinned backend nodes. Launch isolated full backend partitions before revisiting the independently unresolved historical RC14 container migration.

## November 2 full backend acceptance 41427400005 — all 2,579 nodes executed

- On source 711ee4389a598069df6bf21f3268e0e96fd756ba, the eight disjoint backend partitions all completed before the 240-minute limit and uploaded durable JUnit evidence (artifact 13143782510). Results: **2,572 passed, 7 failed, 0 skipped**. No runner timeout or artifact race.
- Six failures in `tests/backend/test_0561_recovery.py` came from General metadata crash/restart cases invoking `recover_metadata_swaps` directly after an F14 interruption, without an originally registered library. F14's pre-mutation admission guard correctly refused that unowned replay. The revised test cases create the real synthetic config + registered main library BEFORE metadata intent, assert generic retry leaves source/journal bytes unchanged, and use `recover_general_outcomes(..., physical=True)` for the qualified original-lease recovery; successful restart and idempotence are still required. The retry-interruption case injects a second crash into that qualified original physical rollback and verifies successful later retry.
- The seventh failure, `test_0331_library_correction_stays_undated_until_explicit_reintegration`, created a synthetic `library-a` name but no actual registered owner. The secondary-library fixture now establishes its real internal database identity and registry bindings before the original metadata write, preserving the 0.33.5 correction and explicit reintegration behavior and exercising non-main-library functionality.
- First targeted run 41456761665 exposed that the synthetic `settings.json` was not created before F14 froze its identity (seven fail-closed `configuration_unavailable` responses). The tests now materialize that legitimate fresh test configuration BEFORE first F14 admission; never manufacture configuration during recovery.
- Targeted run **41456923653** passed the **seven exact observed nodes** in `backend_full_seven_20261102.json`. No application code, real media, immutable historical original fixtures, production settings or security gates changed in this patch series.
- Release still requires the entire independent backend suite plus the previously blocked immutable RC14 container 14-iPhone-JPEG migration. Full backend alone does not waive that historical provenance gap.

## RC14 original 14-JPEG container migration diagnosis (2026-11-02)

The original RC14 image (immutable digest 86991ef...) returned an authenticated HTTP 409 during the first reintegration attempt and preserved an F14 lease with `ids={"function":"app.metadata_correction.reintegrate_library_metadata_family"}`, no family key and no pre-swap journal ownership proof. The current app cannot rightfully use the later family-scoped lease while that original is unresolved (`retry_original_reservation_identity_required`). The historical RC14 writer verifies original EXIF before it stages a file or creates a swap journal; a completed metadata correction with wall-clock-truncated timestamp can fail that *earliest* verification. Distinguish this provable negative prejournal state from all interrupted physical swaps.

The proposed isolated recovery path in `metadata_legacy_rc14_recovery.py` requires the exact historical unscoped key, unchanged registered owner and F14 bindings, an empty and safe original journal directory, unchanged catalogue identity, completed family correction receipts and all referenced source file hashes/inodes, and a precise RC14-style failing earliest EXIF verification for every potential family. It creates no prospective swap ownership, no media writes and no new owner; a qualified original F14 retry records a typed negative-outcome receipt only after the whole proof repeats under lock. Any other missing proof, journal, mismatching byte/receipt, or successful EXIF preflight remains blocked. Must validate in the unmodified RC14 container and explicitly negative tamper cases before release.

## RC14 dedicated immutable-container repro gate
Added `[pre5-iphone]` to the existing self-hosted pre5 container job. It builds the actual candidate and pulls the digest-pinned released RC14 image, then runs only the unmodified `qa/pre/container.py` real authenticated 14-JPEG upgrade scenario; all other container cases remain required for the final full check. This is a diagnostic fast-fail optimization, not a substitution for release gates. The RC14 no-effect qualifier permits the original `.swap-journals` directory to be absent (the exact expected pre-journal state), but refuses all present/foreign journals and unverified bytes.

## Exact historical timing: postpone no-effect completion until authenticated POST

The original immutable `qa/pre/container.py` expects the RC14 F14 reservation to survive candidate first startup and remain byte-for-byte identical until the explicit authenticated `/api/metadata-correction/reintegrate` request. Startup is therefore NOT authorized to finalize the negative prejournal case. The new `recover(...,allow_legacy_prejournal=False)` default preserves the original and returns the exact missing-proof denial at startup. Only the authenticated explicit reintegration route may invoke `allow_legacy_prejournal=True`, and only if the dead reservation has the exact old global family-less key; only a fully qualified read-only negative proof then allows the original F14 lease to finish, after which normal startup and new family-scoped operations proceed. This is distinct from modern prospective scoped crash recovery and does not bless absent swap ownership.
