"""No real devices or privileged commands. Kernel views are explicitly synthetic."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import pytest
from app import source_helper as sh
from app.source_mount_state import Ledger, UnsafeMount, protected_directory
from qa.device_safety.worker import configure


@pytest.fixture
def card(tmp_path, monkeypatch):
    # configure assigns helper globals; restore them after every case.
    for name in ('MOUNT_ROOT', '_block_device_numbers', '_device_binding', '_node_matches_device',
                 '_ensure_mount_device_node', 'mount_identity', 'lsblk', '_mount_info', 'run'):
        monkeypatch.setattr(sh, name, getattr(sh, name))
    kernel = configure(tmp_path)
    return tmp_path, kernel


def call(unmount=False):
    return sh._operation({'device_path': '/synthetic/p1'}, unmount=unmount)


def test_owned_mount_survives_helper_restart_and_ejects(card):
    root, kernel = card
    assert call()['mounted']
    record = next((sh.MOUNT_ROOT / '.bibliothekar-helper').glob('*.json'))
    assert json.loads(record.read_text())['state'] == 'mounted'
    assert sh.devices()[0]['read_only']
    assert call()['mounted']  # idempotent retry, no second mount
    assert call(True)['mounted'] is False
    commands = [json.loads(line)[0] for line in (root / 'commands.jsonl').read_text().splitlines()]
    assert commands == ['mount', 'umount']
    assert not record.exists()


@pytest.mark.parametrize('change', ['foreign', 'unique', 'rw', 'source', 'filesystem', 'device'])
def test_unproven_or_writable_mount_blocks_import_without_cleanup(card, monkeypatch, change):
    root, kernel = card
    assert call()['mounted']
    record = next((sh.MOUNT_ROOT / '.bibliothekar-helper').glob('*.json'))
    if change == 'foreign':
        record.unlink()
    elif change == 'unique':
        kernel.write_text(json.dumps({'mounted': True, 'unique': 999}))
    elif change == 'rw':
        kernel.write_text(json.dumps({'mounted': True, 'unique': 202, 'options': 'rw,nosuid,nodev,noexec'}))
    elif change == 'device':
        monkeypatch.setattr(sh, '_device_binding', lambda item: {'major': 8, 'minor': 2})
    else:
        old = sh._mount_info
        monkeypatch.setattr(sh, '_mount_info', lambda path: {**old(path), ('source' if change == 'source' else 'fstype'): 'foreign'})
    target = sh.MOUNT_ROOT / sh._scan_devices()[0]['device_id']
    sentinel = target / 'foreign.jpg'
    sentinel.write_bytes(b'synthetic-foreign-original')
    before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    with pytest.raises(sh.HTTPException):
        call()
    assert not sh.devices()[0]['mounted']
    assert not sh.devices()[0]['read_only']
    assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == before
    assert 'umount' not in (root / 'commands.jsonl').read_text()
    if change != 'rw':
        with pytest.raises(sh.HTTPException):
            call(True)
        assert 'umount' not in (root / 'commands.jsonl').read_text()


@pytest.mark.parametrize('label', ['.', '..', 'a/b', 'a?b', '\u202e', '/absolute'])
def test_ids_are_bounded_and_partition_specific(card, monkeypatch, label):
    monkeypatch.setattr(sh, 'lsblk', lambda: {'blockdevices': [{'type': 'disk', 'rm': True, 'children': [
        {'type': 'part', 'fstype': 'vfat', 'path': f'/synthetic/p{i}', 'kname': f'p{i}', 'label': label,
         'uuid': 'CLONE'} for i in (1, 2)]}]})
    items = sh._scan_devices()
    assert len({item['device_id'] for item in items}) == 2
    for item in items:
        assert Path(item['device_id']).name == item['device_id']
        assert item['device_id'].startswith('media-')
        assert len(item['device_id']) == 70


def process(root, action='mount', boundary='none'):
    return subprocess.run([sys.executable, '-m', 'qa.device_safety.worker', str(root), action, boundary],
                          capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize('boundary', ['prepared', 'mount', 'mounted', 'unmounting', 'umount'])
def test_sigkill_recovery_is_conservative_and_repeated(tmp_path, boundary):
    if boundary in {'unmounting', 'umount'}:
        assert process(tmp_path).returncode == 0
    result = process(tmp_path, 'unmount' if boundary in {'unmounting', 'umount'} else 'mount', boundary)
    assert result.returncode == -signal.SIGKILL, result.stdout + result.stderr
    assert (tmp_path / 'killed-at').read_text() == boundary
    for _ in range(3):
        recovery = process(tmp_path, 'unmount')
        assert recovery.returncode == (9 if boundary == 'mount' else 0), recovery.stdout + recovery.stderr
    commands = [json.loads(line)[0] for line in (tmp_path / 'commands.jsonl').read_text().splitlines()] if (tmp_path / 'commands.jsonl').exists() else []
    assert commands.count('mount') == (0 if boundary == 'prepared' else 1)
    assert commands.count('umount') == (1 if boundary in {'mounted', 'unmounting', 'umount'} else 0)
    records = list((tmp_path / 'mounts/.bibliothekar-helper').glob('*.json'))
    assert bool(records) == (boundary == 'mount')  # unknowable mount remains fenced


def test_cross_process_lock_rejects_second_helper(card):
    root, _ = card
    with Ledger(sh.MOUNT_ROOT).locked():
        result = process(root)
        assert result.returncode == 9 and 'operation is active' in result.stdout
    assert process(root).returncode == 0


def test_unknown_target_is_not_adopted_or_removed(card):
    root, _ = card
    target = sh.MOUNT_ROOT / sh._scan_devices()[0]['device_id']
    target.mkdir()
    (target / 'foreign').write_bytes(b'foreign')
    with pytest.raises(sh.HTTPException):
        call()
    assert (target / 'foreign').read_bytes() == b'foreign'
    assert not (root / 'commands.jsonl').exists()


def test_parent_permissions_and_symlink_are_not_repaired(tmp_path):
    parent = tmp_path / 'unsafe'
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    child = parent / 'mounts'
    child.mkdir()
    with pytest.raises(UnsafeMount):
        protected_directory(child)
    assert parent.stat().st_mode & 0o777 == 0o777
    link = tmp_path / 'link'
    link.symlink_to(child, target_is_directory=True)
    with pytest.raises(UnsafeMount):
        protected_directory(link)


def test_incomplete_record_write_is_preserved_and_blocks(card):
    root, _ = card
    item = sh._scan_devices()[0]
    with Ledger(sh.MOUNT_ROOT).locked() as ledger:
        pending = ledger.private / (item['device_id'] + '.json.pending')
        pending.write_bytes(b'{interrupted')
        with pytest.raises(UnsafeMount):
            ledger.write(item['device_id'], {'state': 'prepared'})
        assert pending.read_bytes() == b'{interrupted'


@pytest.mark.parametrize('label', ['.', '..', 'SAFE-UUID', 'Camera/One', 'Camera?One', '\u202e'])
def test_actual_mount_command_stays_inside_root(card, monkeypatch, label):
    root, _ = card
    original = sh.lsblk()
    partition = original['blockdevices'][0]['children'][0]
    partition.update(uuid=label, label=label)
    monkeypatch.setattr(sh, 'lsblk', lambda: original)
    assert call()['mounted']
    args = json.loads((root / 'commands.jsonl').read_text().splitlines()[0])
    target = Path(args[-1])
    assert args[0] == 'mount'
    assert target.parent == sh.MOUNT_ROOT
    assert target.resolve() != sh.MOUNT_ROOT.resolve()
    assert target.is_dir()
    assert call(True)['mounted'] is False


def test_unsupported_mount_identity_prevents_mount_or_target_creation(card, monkeypatch):
    root, _ = card
    def unsupported(path):
        raise UnsafeMount('STATX_MNT_ID_UNIQUE is required')
    monkeypatch.setattr(sh, 'mount_identity', unsupported)
    with pytest.raises(sh.HTTPException) as caught:
        call()
    assert caught.value.status_code == 409
    assert not (root / 'commands.jsonl').exists()
    assert not list(sh.MOUNT_ROOT.glob('media-*'))


def test_changed_device_before_mount_keeps_prepared_evidence(card, monkeypatch):
    root, _ = card
    original = sh._ensure_mount_device_node
    def change(item):
        monkeypatch.setattr(sh, '_device_binding', lambda _: {'major': 8, 'minor': 99})
        return original(item)
    monkeypatch.setattr(sh, '_ensure_mount_device_node', change)
    with pytest.raises(sh.HTTPException):
        call()
    assert not (root / 'commands.jsonl').exists()
    record = next((sh.MOUNT_ROOT / '.bibliothekar-helper').glob('*.json'))
    assert json.loads(record.read_text())['state'] == 'prepared'


def test_effective_acl_write_grant_is_refused_without_permission_changes(tmp_path, monkeypatch):
    from app import source_mount_state as ms
    monkeypatch.setattr(ms.os, 'geteuid', lambda: 0)
    # Synthetic root ownership; subprocess response models the kernel ACL result.
    real = Path.lstat
    def owned(path):
        s = real(path)
        return os.stat_result((s.st_mode, s.st_ino, s.st_dev, s.st_nlink, 0, s.st_gid, s.st_size,
                               s.st_atime, s.st_mtime, s.st_ctime))
    monkeypatch.setattr(Path, 'lstat', owned)
    monkeypatch.setattr(ms.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0, json.dumps([str(tmp_path)]), ''))
    with pytest.raises(UnsafeMount, match='Web UID'):
        protected_directory(tmp_path)


def test_private_state_symlink_is_not_followed(card):
    root, _ = card
    outside = root / 'outside'
    outside.mkdir()
    (sh.MOUNT_ROOT / '.bibliothekar-helper').symlink_to(outside, target_is_directory=True)
    with pytest.raises(sh.HTTPException):
        call()
    assert not list(outside.iterdir())
    assert not (root / 'commands.jsonl').exists()


def test_platform_mount_identity_capability_is_explicit(tmp_path):
    from app.source_mount_state import mount_identity
    if sys.platform == 'linux':
        proof = mount_identity(tmp_path)
        assert proof['unique'] > 0 and proof['namespace'] > 0 and proof['boot']
        assert proof['directory'] == sh.directory_identity(tmp_path)
        if os.environ.get('AUDIT_OUTPUT'):
            (Path(os.environ['AUDIT_OUTPUT']) / 'linux-mount-identity.json').write_text(json.dumps(proof))
    else:
        with pytest.raises(UnsafeMount):
            mount_identity(tmp_path)
