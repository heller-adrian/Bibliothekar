# Pre.5 backend regression gate – 2026-11-01

Evidence source: [GitHub Actions run 41331175415](https://github.com/heller-adrian/Bibliothekar/actions/runs/41331175415), backend job 124922437608 (aborted by concurrency after 7 of 8 backend partitions).

Exactly 19 *observed*, distinct failed pytest nodes are pinned in `qa/pre5/backend_19_previous_failures.json`. These failures were seen across 7 completed partitions (2,236 passes, 19 failures); the eighth partition had not finished. Do not interpret the 19 as an exhaustive failure count or as 19 distinct root causes.

The revised test harness now sets up the required real synthetic registry, library identity, and F14 root-control baseline before registered metadata operations. The code-side missing-database guard remains fail-closed. Historical R14/RC14 crashes with missing prospective ownership evidence remain blocked: a green local fixture is not authorization to resume old unproven mutations.

The full Pre.5 workflow must first run these exact 19 nodes in an isolated F14 Linux harness and stop on any failure. Only then proceed to the 147-node historical gate, complete backend partitions, frontend, and container. A **release requires all stages green**, including the immutable historical 14-iPhone-JPEG migration contract. Do not publish or tag based on targeted success.
