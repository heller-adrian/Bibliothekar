# 0.50.8 – Review and acceptance

This is a patch branch based on the 0.50.7 audit state. Nothing is automatically
deployed to TrueNAS, and no changes were made to existing photo files or databases.

## Resolved in code
- Available capacity now comes from the real shared workspace path, not the
  symlink compatibility directory on the container tmpfs.
- The SSD release button catches confirmation and API errors, requires a
  server task ID, and wakes the background task display.
- The background task display is available on smaller browser windows and on
  touch devices; completed apply and release tasks remain in the activity feed
  for a short period.
- English event subfolders All and Sorted are classified as valid branches.
- Additional English UI translations for the identified screenshots and error
  messages; the physical path appended to an error stays byte-for-byte intact.

## Mandatory manual acceptance in an isolated library
1. English and German toggle and reload: check Import, Photos, Events, Archive,
   Preferences, error messages, dialogs and PWA.
2. Run a small folder import; verify the background progress dock and post-run
   result, including a page reload while the job is running.
3. Apply one planned event and verify that its operation persists after
   navigation; check actual files, SQLite journal and archive state.
4. Verify the archive, accept a release, verify that the task becomes queued,
   then running and completed, and check no unverified file is deleted.
5. Deny a release, simulate a failed verification and a network error; ensure
   errors remain visible and no unwanted delete occurs.
6. Assert the workspace capacity against statvfs on the actual mounted dataset.
7. Provision a brand-new library and confirm English default folders while an
   existing legacy library retains its original physical folder names.

A source-only QA run cannot replace these real TrueNAS acceptance tests.
