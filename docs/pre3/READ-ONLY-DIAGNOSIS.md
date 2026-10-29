# Read-only evidence for the three actual F14 operations

No NAS access was performed by Codex. No content of the two unclassified operations
is assumed. Use the following only to collect evidence, not to repair or clear state.

The script is `qa/pre3/read_only_diagnosis.py` on the development branch. It reads
persistent files through O_RDONLY descriptors. SQLite opens only verified copies
of DB/WAL/SHM in a dedicated container `/tmp` directory. Those temporary copies are
removed on exit. No live database is opened by SQLite; no real WAL/SHM, operation,
journal, media, ACL or configuration is modified. If a database changes during
copying or isolated temporary space is insufficient, the script reports an error.
Never work around that error by deleting sidecars or evidence.

From a local checkout of this development branch, on your own computer:

```sh
ssh NAS_ADMIN@NAS_HOST 'docker exec --user 568:568 -i ix-bibliothekar-bibliothekar-1 python -' < qa/pre3/read_only_diagnosis.py > bibliothekar-pre3-diagnosis.json
```

Replace only NAS_ADMIN/NAS_HOST with your existing administrative login/host.
The redirection writes the report on your computer. The script is supplied through
standard input and is not installed on the NAS. Use existing Docker access rights;
no permission changes are required or proposed. Alternatively paste the script into
`python -` in the app shell running as UID 568. Do not run startup, storage_admin,
SQL updates, cleanup, chmod/chown or a second app instance to obtain the report.

Required evidence in that JSON:

1. All three original `operation-*.json` records, including filename, nonce, kind,
   ids, database, generation, library and complete bindings.
2. Full `state.json` and current bound-root identities; any finished, intent,
   outcome or location receipts for those exact nonces.
3. Linked metadata rows, including verification JSON, source/output fingerprints,
   statuses and timestamps, plus linked jobs where a job ID is present.
4. Main General-import job rows and actual catalogue paths, with their completed
   manifest, move-journal and status protocol. Candidate destination SHA/size/inode
   comes from those journals; no destination is invented from a filename or date.
5. Any reported read/copy errors. Missing evidence is a finding, never authorization.

The report contains private paths and library history. Share it only through your
chosen private project channel. The script does not send it anywhere itself.

For later candidate acceptance, retain existing appdata/workspace/RO archives and
all original evidence. A successful qualification preserves the old completed JPEG
row and original nonce in a durable receipt; an unknown operation stays blocked.
This task does not publish or install a candidate.
