# Progress

2026-10-29: Technical correction complete on `codex/pre2-metadata-abort-recovery`.
Tested application commit: `ff1cdf3557b87e5f390f8c1f71abe179ac9d4a52`.
Linux run 40957407776 SUCCESS: 148 regressions; historical/future general failure,
foreign-byte refusal and real SIGKILL supervisor cases pass. Four thousand files /
two libraries start in ~6 seconds; all 14 RC14 +13:00 JPEG regressions pass. Evidence ZIP
independently downloaded and SHA-256 checked; see EVIDENCE.json. No source changes after
this gate. Native TrueNAS and genuine DNG 1.7 NOT_RUN. No release/tag/GHCR push and no NAS
changes. Next: review the technical report and authorize a separate pre.2 candidate.

Publication preparation (2026-10-29): user authorized v1.0.0-pre.2. Separate
`codex/publish-1.0.0-pre.2` branch; frozen build f8e128c9e5aec462d16f987d2e71dbe0d02f1549
changes only app/__init__.py version string. Accepted artifact and all 14 members
reverified; 148 tests and three container groups confirmed. Eleven publisher tests,
including negative OCI/payload/artifact/runtime gates, and Actionlint pass locally.
Local user token cannot read package metadata (HTTP 403); mandatory Actions-token
visibility/protected-release preflight must pass before tag or push. New manual
publisher and main registration stub prepared. Next: register, dispatch exactly once,
verify versioned container gates, immutable pull and downloaded release assets.


Publication complete (2026-10-29): v1.0.0-pre.2 published and independently verified.
Actions 40960151711 SUCCESS on the dedicated self-hosted runner. Versioned-image
metadata abort/SIGKILL/foreign-byte, 4,000-file/two-library and 14 +13:00 JPEG gates
PASS. Build/tag f8e128c9e5aec462d16f987d2e71dbe0d02f1549; only version metadata differs
from the accepted application. Index digest:
sha256:b9434137951a8f1e40de047bed6e3d8ee3be425e079b92aa6df9ec491c982c13.
Real immutable pull and payload/OCI proof PASS. All 40 release assets independently
downloaded and verified against GitHub digests; 39 SHA256SUMS entries PASS. Source
archive's 196 app files match Git. Old releases/assets/tags/images/latest unchanged;
repository private and package public as before. See PUBLISHED.json for exact IDs.
No NAS access. Next: user upgrades the existing app using UPGRADE-TRUENAS.md and
performs native acceptance. TrueNAS/NFSv4, actual DNG 1.7, physical SD/USB NOT_RUN;
loss finalization DEFERRED. Never rerun this one-shot publisher for the existing version.
