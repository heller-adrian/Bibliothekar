# RC3 targeted renderer QA

Install `qa/rc3/requirements.txt` in the test environment in addition to existing backend test prerequisites. Run `tests/backend/test_rc3_mobile.py` using the existing isolated launcher with `AUDIT_OUTPUT` pointing outside the checkout. It writes `browser-bundle.json` containing the actual HTML, CSS, translation engine and relevant renderer functions.

Run `node qa/rc3/browser.cjs /absolute/path/browser-bundle.json /absolute/path/results` with an available Playwright module and Chromium. `PLAYWRIGHT_MODULE` and `CHROMIUM_EXECUTABLE` may identify already installed runtimes. Network requests are aborted and the browser context is offline. Only synthetic DOM data is used. This tests actual renderers and CSS at 390×844 and 1280×900, not a live TrueNAS installation or its APIs. No server, NAS connection or CI run is required.

Backend selection also includes the existing RC1 SD-reimport, package A, B01 and C tests and the `import.move1` / `import.complete` SIGKILL cases. Historical test files and assertions remain unchanged. No release version bump is included.
