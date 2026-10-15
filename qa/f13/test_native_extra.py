"""Additional real Linux interleavings; separate from whole-backend counts."""
import ctypes,hashlib,os,subprocess,sys
from pathlib import Path
import pytest
from app import ssd_archive_guard as guard


def test_C_process_write_during_hash(tmp_path,monkeypatch):
    assert sys.platform=='linux','BLOCKED: actual Linux required'
    p=tmp_path/'A.bin';data=b'a'*(2*1024*1024);p.write_bytes(data)
    g=guard.ArchiveGuard(tmp_path,['A.bin']);read=os.read;done=False
    def interleave(fd,count):
        nonlocal done
        block=read(fd,count)
        if block and not done:
            done=True
            subprocess.run([sys.executable,'-c',"from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b'X'*(2*1024*1024))",str(p)],check=True,timeout=5)
        return block
    monkeypatch.setattr(guard.os,'read',interleave)
    try:
        with pytest.raises(guard.ArchiveConflict):g.verify('A.bin',len(data),hashlib.sha256(data).hexdigest())
        assert done
    finally:g.close()


def test_C_native_watch_removed(tmp_path):
    assert sys.platform=='linux','BLOCKED: actual Linux required'
    p=tmp_path/'A.bin';p.write_bytes(b'original');fd=os.open(p,os.O_RDONLY);w=guard.InotifyWatcher()
    try:
        w.watch(fd);wd=next(iter(w.scopes))
        w.libc.inotify_rm_watch.argtypes=[ctypes.c_int,ctypes.c_int];w.libc.inotify_rm_watch.restype=ctypes.c_int
        assert w.libc.inotify_rm_watch(w.fd,wd)==0
        with pytest.raises(guard.ArchiveConflict):w.check()
        with pytest.raises(guard.ArchiveConflict):w.check()
        assert p.read_bytes()==b'original'
    finally:os.close(fd);w.close()


def test_C_native_event_descriptor_failure(tmp_path):
    assert sys.platform=='linux','BLOCKED: actual Linux required'
    w=guard.InotifyWatcher();os.close(w.fd)
    try:
        with pytest.raises(guard.ArchiveConflict):w.check()
        with pytest.raises(guard.ArchiveConflict):w.check()
    finally:w.fd=-1;w.close()
