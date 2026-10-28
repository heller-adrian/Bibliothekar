"""Filesystem dispatch uses a fresh held descriptor, never cached ACL trust."""
import ctypes
import errno
from types import SimpleNamespace
import pytest
from app import private_storage_security as security


def test_descriptor_filesystem_dispatch_and_requery(monkeypatch):
    seen = []
    magic = [0xEF53, 0x2FC12FC1, 0x794C7630]
    def query(fd, buffer):
        seen.append(fd)
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_long))[0] = magic.pop(0)
        return 0
    monkeypatch.setattr(security.sys, 'platform', 'linux')
    monkeypatch.setattr(security, '_LIBC', SimpleNamespace(fstatfs=query))
    assert [security.filesystem(71) for _ in range(3)] == ['ext4', 'zfs', 'overlay']
    assert seen == [71, 71, 71]


def test_descriptor_query_failure_is_not_acl_absence(monkeypatch):
    monkeypatch.setattr(security.sys, 'platform', 'linux')
    monkeypatch.setattr(security, '_LIBC', SimpleNamespace(fstatfs=lambda *args: -1))
    ctypes.set_errno(errno.EBADF)
    with pytest.raises(OSError, match='descriptor filesystem query failed'):
        security.filesystem(-1)


def test_real_linux_descriptor_filesystem(tmp_path):
    if security.sys.platform != 'linux':
        pytest.skip('Linux descriptor ABI exercised in mandatory Linux acceptance')
    with (tmp_path/'probe').open('w') as stream:
        assert security.filesystem(stream.fileno()) in security.LOCAL_FILESYSTEMS
