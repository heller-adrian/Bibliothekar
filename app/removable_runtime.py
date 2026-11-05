"""RC12 removable mounts live only in this container's private mount namespace.

A root-owned tmpfs over the instance mountpoint separates privileged helper
journals from the host-managed appdata ACL. No permissions on host data change.
Container recreation discards mount ownership; sources are always mounted RO.
"""
from pathlib import Path
import os
import subprocess


def prepare():
    from app.appdata import root, mount
    base = root()
    if base is None: return
    target = base/'removable-sources'
    if Path(os.environ['KAMERA_REMOVABLE_MOUNT_ROOT']) != target:
        raise RuntimeError('RC12 helper requires its own appdata/removable-sources mountpoint')
    if mount(base)['target'] != str(base):
        raise RuntimeError('Helper appdata must be an actual dedicated bind mount')
    # Make only the container bind private before attaching any source; no
    # rshared propagation to the NAS or a second application is needed.
    subprocess.run(['mount','--make-rprivate',str(base)],check=True,capture_output=True)
    current = mount(target)
    if current['target'] == str(target):
        if current['filesystem'] != 'tmpfs': raise RuntimeError('Unexpected removable runtime mount; preserved')
        return
    from app.import_publication import _parent
    with _parent(target/'.probe') as (fd,_):
        if os.listdir(fd): raise RuntimeError('removable-sources contains unknown data; preserved, helper disabled')
    subprocess.run(['mount','-t','tmpfs','-o','mode=0755,uid=0,gid=0,nosuid,nodev,noexec,size=1m',
                    'bibliothekar-removable',str(target)],check=True,capture_output=True)
    from app.source_mount_state import protected_directory
    protected_directory(target)
