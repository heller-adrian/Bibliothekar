# TrueNAS catalog deployment profile

Bibliothekar uses the same image and version for both profiles. This guide describes the profile intended for catalog submission. Official catalog acceptance is pending.

## Standard profile

Use [the standard Compose example](../compose.example.yaml) with `KAMERA_SOURCE_HELPER_ENABLED=false`. The supervisor and web process run as UID/GID 568. Grant that account access to the selected datasets using the existing ownership or ACL policy.

| Mount | Access | Purpose |
| --- | --- | --- |
| `/appdata` | read/write | Configuration, databases and logs |
| `/workspace` | read/write | Verified backups and working media |
| `/main-library` | read-only | Main archive |
| `/sources/nas` | read-only | Inbox or existing source folders |
| `/sources/import` | read-only, optional | Existing supported backup folders |
| Additional archive roots | read-only, optional | Separate managed libraries |

Use [the NAS source overlay](../compose.nas-source.yaml) to bind an inbox dataset. Copy photos to that inbox over SMB from another computer and choose the folder in **Import & Review → Back up a source**. The application can read the inbox but cannot change its contents. Mount an existing backup dataset at `/sources/import` to make it selectable as **Existing backups**.

The standard profile uses a read-only container filesystem, private bind mounts and no-new-privileges. It requires no privileged mode, host devices, udev mount, added capabilities or host mount propagation. Keep the archive read-only for additional libraries as well.

The web application blocks direct removable device and folder requests when the helper is disabled. Folder check and recovery jobs for regular storage remain available. Pending removable jobs are left queued until an enabled deployment is available.

## Optional local removable-media profile

Administrators can add [the removable-media overlay](../compose.removable.yaml) for a Custom App under their own control. It explicitly uses a root supervisor with a privileged, container-local helper. The web process still runs as UID/GID 568. The helper verifies read-only mounts for both SD cards and USB drives. Keep the same application data and workspace when changing profiles and recreate the container to apply the new settings.

The helper mounts its temporary filesystem inside the container. Its mount identity is checked separately from the persistent AppData directory. If an older installation only recorded the temporary mount, Bibliothekar qualifies the underlying directory on its first folder-only start. Unexpected contents or a replacement of an already registered directory keep affected operations blocked.

Physical reader and USB drive insertion, removal and repeated reinsertion are manual acceptance checks on supported hardware. The automated device responses and mount-policy fixtures are synthetic.

The standard deployment choices follow the [TrueNAS app contribution guide](https://github.com/truenas/apps/blob/master/CONTRIBUTIONS.md) and [TrueNAS app storage documentation](https://www.truenas.com/docs/scale/apps/appsscreens/).
