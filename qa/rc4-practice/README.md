# RC4 practice follow-up

Base: 7122afa8864258cba6d1d5500b78413ded7acae7. No version change.

See SAFETY.md for the limited automatic failure proof. `failure_worker.py` uses
real startup recovery and SIGKILL boundaries; `recover` uses a two-process gate
and accepts only the existing F14 busy refusal or one durable finalization.
`browser.cjs` reuses the installed offline Playwright/Chromium harness and the
actual shell, preview, history and presentation fragments exported by
`test_rc4_practice.py::test_browser_bundle`. Network requests are aborted.

Targeted QA: 171 distinct backend/Node cases PASS (latest outcome per node ID),
six offline Chromium cases PASS. Existing F11/F24/R1, archive, SD recheck,
SQLite/hash and process-recovery assertions retained. No full suite/CI run.
Historical originals and all failed attempts are preserved in the external QA
package. DOM adapters now model status containers/style and nested details;
raw evidence tests require immutable original JSON and escaped presentation,
without a second raw-log UI expander. The generic page-activity test runs on an
unaffected event page; a dedicated test proves SD/trash duplicate banners are
absent while persisted input records remain identical.

Real NAS state is unqualified until the .incoming contents are read. Unknown
partial imports, mixed known/unknown recovery, incomplete staging and absent
independent copies remain blocked. No cleanup or migration is added.
