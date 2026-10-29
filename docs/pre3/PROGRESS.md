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

Final targeted acceptance completed 2026-10-29 23:08 UTC (2026-10-30 CET):
- [Linux CI 40969680973](https://github.com/heller-adrian/Bibliothekar/actions/runs/40969680973) SUCCESS, tested commit `7733c64bc7c555e7dc416ed7b953a00b6cf911b2`.
- 181 pytest regressions PASS, 0 failed, 0 skipped; local test image and all immutable historical image pulls PASS.
- Six pre3 real-supervisor container cases PASS (pre2 historical, actual RC14, foreign bytes, three open operations, completed SIGKILL, import SIGKILL). Authenticated read-only diagnostics, write fences and unmodified RO archive verified.
- Three pre2 DNG-abort recovery cases PASS; 4,000-file/two-library starts 6.015/6.430 s, 14 corrected RC14 iPhone JPEGs (+13:00), origin proofs and archive hashes PASS.
- GitHub Actions evidence ZIP artifact `12939434627` downloaded and independently SHA-256 verified as `e8f17247f477d46e115e4bdc351258451b829fd8734cf63c080e4ede08f94a03`; per-file SHA-256 listed in `EVIDENCE.json`.
- The only change since application code commit `86d42d440b0340b82227b7b0d9f775da6b9a2de3` is a stricter/accurate container negative-test expectation in `qa/pre3/container.py`.
- Native TrueNAS/NFSv4, real DNG 1.7 and physical SD/USB remain NOT_RUN; three actual NAS F14 records remain unclassified. No tag, release, GHCR push or NAS change. Prepare separately verified `v1.0.0-pre.3` publication next.
