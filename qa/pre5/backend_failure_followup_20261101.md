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
