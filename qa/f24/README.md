# F24 path safety

Base `35299e900b3aa38a9a45935d2a6d5fd15f75be6f`; independent branch.
No F11/F12/F13 product changes included.

Directory capabilities pin every component with O_DIRECTORY/O_NOFOLLOW. The
public trash name is never unlinked: a no-replace rename captures it in private
staging, where identity/hash are checked before irreversible removal. An
unexpected captured entry is returned with no-replace; if that conflicts, it and
the journal remain untouched for manual resolution. The durable staging snapshot
is an independent application-owned 0600 copy, not an externally writable alias.
New format-3 journals bind workspace/directories and source/staged inode IDs.

Private namespace ownership is a prerequisite explicitly authorized by the user.
It excludes untrusted processes sharing the app UID or DAC-bypass privileges.
The test supervisor drops a separate writer to UID/GID 65534; that writer can
change public trash but cannot read/write/create/rename/unlink the private stage.
The application gains no additional privileges and changes no existing ACLs.

Directory FDs alone cannot prevent a public directory being reparented outside
workspace after validation. On Linux each native mutation is therefore executed
by a short-lived child at the application UID, with no_new_privs and Landlock ABI
>=2. This irreversible restriction affects only the child, so SQLite and the
shared web process are not sandboxed by accident. There is no listening helper,
root service, mount, setuid executable or unsafe syscall fallback. Rules bind the
workspace directory FD; out-of-tree remove/rename/link/create/write operations
are denied by the kernel, including operations through pre-opened directory FDs.
A protected workspace anchor and private namespace remain mandatory.

The first implementation was locally tested on macOS; those development syscall
results are not Linux Landlock/platform acceptance. Linux runtime qualification
is mandatory. Missing Landlock, unknown ACLs/filesystem semantics, or a real
cross-mount capture cause a fail-closed error. The current qualified POSIX family
list excludes ZFS/NFS/CIFS/FUSE. TrueNAS/ZFS/Samba positive operation is BLOCKED
until a separate isolated platform proof; existing data are not migrated or
modified to enable it. Real cross-mount capture does not use copy-then-public-
unlink. Public empty parent directories are retained rather than raced with rmdir.

Normal format-2 private staged recovery remains supported. A legacy dual-copy
case with unknown target identity requires manual review. F19 and R1 remain open;
F11 is needed in later integration for full-empty/reservation coordination, but
this selected-delete boundary does not depend on F11's code.

Historical test_0561_recovery.py is byte-identical under historical/. Only its
regular syscall instrumentation moves from the removed public source.unlink and
os.link calls to atomic capture/DirectoryTree.link. All assertions remain AST-
identical. Original Phase-5 F24 test bodies and Phase-4 neighbor tools are unchanged
under original/ with SHA-256 manifest. The original F24 barrier still exists.

Reproduce (isolated Linux Python 3.12, ExifTool, requirements + pytest/httpx):

```
PYTHONPATH=. pytest -q -p no:cacheprovider -o addopts='' --basetemp=/tmp/f24-qa tests/backend
F24_QA_ROOT=/tmp/f24-original F24_QA_SOURCE_ROOT=$PWD python qa/f24/run_original.py f24
F24_QA_ROOT=/tmp/f24-neighbors F24_QA_SOURCE_ROOT=$PWD python qa/f24/run_original.py neighbors
F24_KERNEL_OUTPUT=/tmp/f24-kernel PYTHONPATH=. python qa/f24/check_kernel_boundary.py
```

The distinct-UID probe requires the disposable runner's existing passwordless
sudo solely to drop a test process's credentials; never run it on production.
