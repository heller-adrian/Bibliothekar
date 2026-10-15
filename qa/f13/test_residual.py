"""Strict conservation assertion, intentionally not XFAIL/skip/softened."""
import hashlib,json,mmap,os,sys
from pathlib import Path
from app.ssd_archive_guard import ArchiveGuard,ArchiveConflict


def test_mmap_after_last_gate_conserves_original(tmp_path):
    assert sys.platform=='linux','BLOCKED: real mmap/inotify Linux test required'
    archive=tmp_path/'archive';archive.mkdir();src=tmp_path/'ssd.bin'
    original=b'synthetic-original';p=archive/'A.bin'
    src.write_bytes(original);p.write_bytes(original)
    with p.open('r+b') as writer:
        mapping=mmap.mmap(writer.fileno(),len(original))
        g=ArchiveGuard(archive,['A.bin'])
        try:
            g.verify('A.bin',len(original),hashlib.sha256(original).hexdigest(),src.stat())
            g.check()  # Actually last gate, no later decision before unlink.
            mapping[:]=b'X'*len(original);mapping.flush()
            src.unlink()
            observed=False
            try:g.check()
            except ArchiveConflict:observed=True
            (tmp_path/'mmap-observation.json').write_text(json.dumps({'scope':'filesystem primitive interleaving, not whole release worker',
                'source_exists':src.exists(),'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'expected_sha256':hashlib.sha256(original).hexdigest(),'notification_observed_after_unlink':observed}))
            assert (src.exists() and src.read_bytes()==original) or p.read_bytes()==original,'Last matching original lost after mmap write at final gate'
        finally:g.close();mapping.close()
