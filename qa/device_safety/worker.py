"""Synthetic mount kernel for process/recovery tests; never invokes mount/mknod."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from app import source_helper as sh


def configure(root: Path):
    sh.MOUNT_ROOT = root / 'mounts'
    sh.MOUNT_ROOT.mkdir(exist_ok=True)
    kernel = root / 'kernel.json'
    sh._block_device_numbers = lambda name: (8, 1)
    sh._device_binding = lambda item: {'major': 8, 'minor': 1, 'device_id': item['device_id'], 'diskseq': 42}
    sh._node_matches_device = lambda path, major, minor: str(path) == '/synthetic/p1'
    sh._ensure_mount_device_node = lambda item: ('/synthetic/p1', False)
    sh.mount_identity = lambda path: {'unique': 101 if path == sh.MOUNT_ROOT else json.loads(kernel.read_text())['unique'],
                                      'directory': sh.directory_identity(path)}
    sh.lsblk = lambda: {'blockdevices': [{'type': 'disk', 'rm': True, 'tran': 'usb', 'children': [
        {'type': 'part', 'fstype': 'vfat', 'path': '/synthetic/p1', 'kname': 'p1', 'uuid': 'CARD'}]}]}
    def info(path):
        data = json.loads(kernel.read_text()) if kernel.exists() else {}
        return ({'target': path, 'source': '/synthetic/p1', 'fstype': 'vfat',
                 'options': data.get('options', 'ro,nosuid,nodev,noexec')} if data.get('mounted') else None)
    sh._mount_info = info
    def run(*args, **kwargs):
        with (root / 'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(args) + '\n')
        if args[0] == 'mount':
            kernel.write_text(json.dumps({'mounted': True, 'unique': 202}))
        elif args[0] == 'umount':
            kernel.write_text(json.dumps({'mounted': False, 'unique': 202}))
        return subprocess.CompletedProcess(args, 0, '', '')
    sh.run = run
    return kernel


def main():
    root, action, boundary = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    configure(root)
    original = sh.Ledger.write
    def write(self, device_id, record):
        original(self, device_id, record)
        if record['state'] == boundary:
            (root / 'killed-at').write_text(boundary)
            os.kill(os.getpid(), signal.SIGKILL)
    sh.Ledger.write = write
    real_run = sh.run
    def run(*args, **kwargs):
        result = real_run(*args, **kwargs)
        if args[0] == boundary:
            (root / 'killed-at').write_text(boundary)
            os.kill(os.getpid(), signal.SIGKILL)
        return result
    sh.run = run
    try:
        result = sh._operation({'device_path': '/synthetic/p1'}, unmount=action == 'unmount')
        print(json.dumps(result))
    except sh.HTTPException as error:
        print(json.dumps({'status': error.status_code, 'detail': error.detail}))
        raise SystemExit(9)


if __name__ == '__main__':
    main()
