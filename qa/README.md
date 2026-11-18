# Bibliothekar QA and tests

The application, test implementations and historical qualification artifacts are intentionally separate. This directory contains regression tools and synthetic-data integration tests; it is **not** part of the installed image by default.

## Current orientation

- `../tests/backend/` contains the main automated backend regression suite.
- `../tests/fixtures/` contains test fixtures.
- `.github/workflows/qa-tests.yml` runs the ordinary backend regression on source changes and supports manual dispatch. Documentation-only housekeeping is excluded from automatic source-test triggers.
- `qa/rc13/regression.py` is still used to partition the exact-source **1.0.0** full qualification. Its older name does **not** mean that the script can be deleted or renamed without updating its consumers.
- The version-specific 1.0.0 qualification workflow is preserved at `v1.0.0:.github/workflows/qa-100-stabilization.yml` (not active on `main`), **not** a reusable future-release gate.

## Safety rules

Run tests against isolated synthetic media, disposable databases and temporary workspace/archive roots only. Do not run archive mutation or cleanup tests against the actual TrueNAS production application, photo archive or a live library database. Do not copy private photos or credentials into public CI artifacts.

Keep source/commit identity, environment information, test manifests and immutable evidence together. Never report a full pass if any required partition, restart, container, frontend or filesystem verification did not complete.

## Historical test plans

The original `TEST_MATRIX.md`, `CLEAN_SLATE.md`, `archive_e2e/`, `pre*/`, `rc*/`, `f*/` and other older phases preserve substantial regression coverage. They also contain version-bound assumptions, earlier path conventions and historical test procedures. Their descriptions and test IDs should **not** be mistaken for a current operator runbook. In particular, old references to named NAS datasets or dedicated QA machines are examples of past test conditions, not supported default installation paths.

Preserve these materials and their referenced paths until a separate dependency-aware refactor is reviewed. Refer to the [documentation index](../docs/README.md) and [release instructions](../docs/RELEASING.md) for current orientation.

## Browser regression for collection adoption

Run `node qa/release/adoption_browser.cjs` with Playwright and Chromium against a fresh disposable installation. Set `BIBLIOTHEKAR_BROWSER_URL`, `BIBLIOTHEKAR_BROWSER_ARCHIVE` (container path) and `BIBLIOTHEKAR_BROWSER_PASSWORD`. Mount the synthetic `02-manuell` fixture as the NAS source, with one JPEG/XMP pair each on 19, 21 and 24 July 2026. Use a fresh catalogue per origin.

Run with a LAN HTTP hostname and with HTTP/HTTPS localhost. The test maps `truenas.test` to loopback for a local HTTP reproduction. It checks the browser's secure-context flag, setup and source selection, saving and reopening events, nested subevents, collection folders and creation of a plan. Set `BIBLIOTHEKAR_BROWSER_DELAYED_SCAN=1` if the disposable server delays the scan, to check progress through a reload. Set `BIBLIOTHEKAR_BROWSER_SCREENSHOTS` to an existing local directory to save screenshots.
