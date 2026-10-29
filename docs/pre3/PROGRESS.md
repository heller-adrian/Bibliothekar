# Progress

2026-10-29: pre.2 source reproduced exact missing-path failure after
completed metadata SQL, failed F14 acknowledgement and actual General import.
Success outcomes, strict historical import continuity, append-only location receipts,
serialized General handoff/cleanup and authenticated read-only diagnosis implemented.
Initial targeted gate: 72 cases pass; final added cases/serialization and full targeted
Linux/supervisor gates pending. Browser diagnosis renders eight EN/DE mobile/desktop
cases. No release/tag/GHCR push or NAS access. Next: finish targeted local gate, run
one self-hosted acceptance and document all actual results.

First Linux gate 40967129148: 176 passed, old legacy-start assertion failed against
the intentionally strengthened unknown-intent fence. Expectation corrected, original
evidence/byte checks retained. RC14 timestamp admission discovered in actual source;
full copy/protocol/origin qualification added, with four local unchanged-RC14 tests
passing. Next: final targeted Linux and supervisor gate, including actual RC14 import.
