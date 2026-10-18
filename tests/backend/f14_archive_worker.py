"""Real archive copying with a bounded deterministic barrier."""
from pathlib import Path
import json,sys,time
from app import archive_release_copy as copy
case=json.loads(Path(sys.argv[1]).read_text());control=Path(sys.argv[2]);original=copy._sha256_file;first=True

def boundary(path):
    global first
    digest=original(path)
    if first:
        first=False;(control/'checkpoint.json').write_text(json.dumps({'path':str(path),'sha256':digest}))
        until=time.monotonic()+20
        while not (control/'continue').exists():
            if time.monotonic()>until:raise RuntimeError('Synthetic archive barrier timed out')
            time.sleep(.01)
    return digest
copy._sha256_file=boundary
try:
    result=copy.create_archive_release_copies(Path(case['db']),Path(case['archive']),Path(case['workspace']),case['cr_id'])
except Exception as e:
    (control/'result.json').write_text(json.dumps({'failed':True,'exception':type(e).__name__,'detail':str(e)},indent=2));raise
else:(control/'result.json').write_text(json.dumps(result,indent=2))
