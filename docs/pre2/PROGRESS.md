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
