# RC4 failure completion proof

Before integration, isolated reproduction confirms: unknown JPG/RAW alone can
complete normally. A real worker failure injected at import preflight leaves
both originals, independent staging copies, no catalogue rows, and only
Protocol/status.json in .incoming. RC4 rejects even that protocol-only residue.
An arbitrary existing .incoming directory remains insufficient evidence.

Limited extension: accept exactly one known Protocol/Protokoll directory with
exactly one bounded, app-owned, single-link regular failed status.json matching
job, source, and temporary-backup path. Bind every component without following
symlinks, retain inode/hash proof and all files, revalidate on every reservation
release. Any media, manifest, move journal, other entry, mismatch or unreadable
component remains blocked. Existing full partition, independent originals and
copies, all registered catalogue, F11 lock, F14 lease, and three-phase durable
receipt requirements stay mandatory. No incoming file is deleted or rewritten.

Worker completion runs only after fail_job persisted failure. Startup retries
only failed jobs through the same proof; active/interrupted/partial jobs are not
converted. GET remains read-only. A crash before committed receipt retains the
reservation; startup rechecks bytes, journal and all catalogues before finishing.
No proof based only on error text, state=failed, labels or directory names.
