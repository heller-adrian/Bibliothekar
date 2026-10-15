"""Small synthetic guard benchmark, not a TrueNAS/SSD workload benchmark."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
import tracemalloc
from app import ssd_archive_guard as guard

class RehashOnly:
    count = 0
    def watch(self, fd, children=None): pass
    def check(self): pass
    def close(self): pass

native = guard.InotifyWatcher
results = {'platform':sys.platform,'kernel':os.uname().release,'scope':'guard only, warm cache, synthetic; no SSD deletion','runs':[]}
with tempfile.TemporaryDirectory(prefix='f13-measure-') as tmp:
    root = Path(tmp).resolve()
    for i in range(64): (root/f'{i}.JPG').write_bytes(b'x'*1024)
    for i in range(2): (root/f'large{i}.bin').write_bytes(b'X'*(32*1024*1024))
    entries = [(p.name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.iterdir()]
    for mode in ['B','C']:
        guard.InotifyWatcher = RehashOnly if mode=='B' else native
        start=time.perf_counter();tracemalloc.start()
        before=len(os.listdir('/proc/self/fd')) if sys.platform=='linux' else None
        g=None
        try:
            g=guard.ArchiveGuard(root,[p for p,s,h in entries])
            ready=time.perf_counter()
            for p,size,digest in entries:g.verify(p,size,digest)
            row=dict(mode=mode,registration_seconds=ready-start,total_seconds=time.perf_counter()-start,files=len(entries),**g.metrics())
            row['tracemalloc_peak_bytes']=tracemalloc.get_traced_memory()[1]
            row['ru_maxrss_platform_units']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception as e:
            row={'mode':mode,'status':'BLOCKED','error':str(e)}
        finally:
            if g:g.close()
            tracemalloc.stop()
            guard.InotifyWatcher=native
        row['open_fds_before']=before
        row['open_fds_after']=len(os.listdir('/proc/self/fd')) if sys.platform=='linux' else None
        results['runs'].append(row)
print(json.dumps(results,indent=2))
