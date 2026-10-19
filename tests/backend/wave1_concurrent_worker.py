"""Current F14 import barrier on F12's actual post-rename/pre-fsync boundary.

The historical concurrency worker and all preservation assertions stay intact.
"""
from pathlib import Path
import json,os,runpy,sys,time,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'qa/f14/original'))
from app import import_publication as pub
boundary=sys.argv[3];control=Path(sys.argv[4]);native=pub._native_rename;count=0

def renamed(*args):
    global count
    result=native(*args);count+=1
    if boundary=='import.move'+str(count):
        with (control/'checkpoint.json').open('w') as handle:
            json.dump({'pid':os.getpid(),'boundary':boundary,'primitive':'exclusive native rename before directory fsync','stack':traceback.format_stack(limit=8)},handle);handle.flush();os.fsync(handle.fileno())
        deadline=time.monotonic()+20
        while not (control/'continue').exists():
            if time.monotonic()>deadline:raise RuntimeError('Current concurrency barrier timed out')
            time.sleep(.01)
    return result
pub._native_rename=renamed
runpy.run_path(str(Path(__file__).resolve().parents[2]/'qa/f14/original/worker_concurrent.py'),run_name='__main__')
