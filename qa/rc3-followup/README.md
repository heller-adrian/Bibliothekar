# RC3 follow-up (2026-10-25)

Base: `d7610205f2c7bc8708e36a130bab896d3ef568d1`.

Targeted regressions: `tests/backend/test_rc3_followup.py`,
`test_rc3_mobile.py`, `test_rc1_sd_reimport.py`, relevant RC1 package A/C/B01,
F11/F24 and the selected import/restore SIGKILL cases. No full suite or CI run.
Use isolated synthetic config, database, registry, source and workspace paths.
The QA package contains the reviewed isolation launcher, commands, JUnit/JSON,
original tests, before/after failures and a per-case matrix.

`browser.cjs BUNDLE_JSON OUTPUT_DIR` runs with the existing Playwright runtime
and Chromium (`PLAYWRIGHT_MODULE`, `CHROMIUM_EXECUTABLE`). The bundle is exported
by `test_r03_r04_browser_bundle_and_css`. Network requests are aborted. Real
shell styles and renderer fragments are exercised with synthetic data.

Known limits: actual NAS reservation state unavailable; already completed
legacy renames are not automatically rewritten; SD full confirmation reads
source and retained-copy hashes synchronously before any new job. Real SD
latency / reverse proxy timeout, iOS/PWA gestures and TrueNAS retest required.
English internal message-base migration is intentionally deferred.
