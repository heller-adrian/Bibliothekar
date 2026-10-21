# SD helper F21/F22/F26 – supported boundary and QA

Development state, not platform approval. UI and helper routes remain unchanged;
ordinary imports from existing folders do not use this protocol.

IDs are SHA-256 over raw UUID/PARTUUID/label, partition path, kernel name, size
and parent serial. They are selectors, not evidence of ownership. Ownership is
proved by the protected record AND current device major/minor, sysfs identity,
disk sequence, boot, mount namespace, unique kernel mount ID and mounted root
identity. `findmnt` source/type/options and the actual block node are rechecked.
RO requires `ro,nosuid,nodev,noexec` and absence of `rw`. Unknown mounts are not
adopted, imported or automatically unmounted. Listing has no cleanup side effect.

The root helper uses `.bibliothekar-helper` (0700) under the existing removable
mount root. Exclusive flock serializes helper processes. Atomic, fsynced records
advance prepared → mounted → unmounting. A crash after mount but before ownership
commit is deliberately uncertain: no automatic adoption/unmount. A pending
journal write is preserved and blocks replacement. Empty, identity-bound native
mountpoint directories may be removed after an absent mount; unknown or nonempty
paths are retained. No glob-based legacy cleanup remains.

## Installation prerequisites

* Helper and web UIDs differ. Web app remains UID/GID 568 by default.
* Helpercode, `/sources`, mount root and private state must not be web-writable.
  Dockerfile changes only built-image ownership, retaining the existing layout;
  `/config`, `/database`, `/logs`, `/workspace` and `/sources/nas` remain web-owned.
  No runtime chown/chmod/ACL repair of host mounts is performed.
* Existing bind mounts need operator qualification. Non-directory/symlink parents,
  untrusted owners and writable group/other permissions are rejected. When root,
  an unprivileged child with the exact web UID/GID and empty groups additionally
  asks the kernel about write access, including ACLs, without creating files.
* Linux must actually support STATX_MNT_ID_UNIQUE (introduced in 6.8). No recycled
  mount-ID fallback. Boot/namespace changes invalidate ownership proof; surviving
  mounts after a container recreation stay fenced until separately qualified.
* Host root, CAP_SYS_ADMIN peers, ACL administrators and writable privileged code
  are outside the isolation boundary; this protocol does not protect against them.
* Persistent state must be on a durable, supported local filesystem; real power
  failure, host reboot, device hotplug/USB identity and container mount propagation
  require independent tests. A helper-process restart is not a host reboot.

The new tests use a synthetic kernel state file; their SIGKILL is real, their
mounts are not. `worker.py` never invokes privileged commands. Real Linux
STATX capability is checked separately by the backend test. Real mount/unmount,
UID/ACL separation in the shipped container and TrueNAS remain unqualified.

Historical originals are unchanged under `historical/`. Exactly two current
contracts now require foreign mounts to be preserved, instead of unmounting by
prefix. The phase-5 originals outside this repository remain raw evidence.

Kernel identity references:
https://man7.org/linux/man-pages/man2/statx.2.html
https://raw.githubusercontent.com/torvalds/linux/master/include/uapi/linux/stat.h
