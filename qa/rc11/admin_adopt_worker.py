"""QA-only CLI observer. Real adoption, then SIGKILL at its durable receipt."""
import json
import os
from pathlib import Path
import signal

assert os.environ.get('RC11_QA_SYNTHETIC')=='true'
from app import root_operations as ro
from app import storage_admin
original_write=ro._write

def observed_write(path,value):
    original_write(path,value)
    if os.environ.get('RC11_QA_BOUNDARY')=='adoption-receipt' and Path(path).name.startswith('rc11-adoption-'):
        marker=Path('/qa-evidence/checkpoint.json')
        with marker.open('x') as stream:
            json.dump({'boundary':'adoption-receipt','pid':os.getpid(),'uid':os.getuid(),'gid':os.getgid(),'publication':str(path)},stream)
            stream.flush();os.fsync(stream.fileno())
        os.kill(os.getpid(),signal.SIGKILL)
ro._write=observed_write
raise SystemExit(storage_admin.main())
