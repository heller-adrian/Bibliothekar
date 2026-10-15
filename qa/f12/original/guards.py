"""Additional read/data guards; macOS sandbox supplies the write/network boundary."""
from pathlib import Path
import json, os, sys, time

scratch=Path(os.environ['AUDIT_SCRATCH']).resolve()
source=Path(os.environ['AUDIT_SOURCE']).resolve()
output=Path(os.environ['AUDIT_OUTPUT']).resolve()
audit_tools=Path(__file__).resolve().parent

def inside(p,root):
    try:p.relative_to(root);return True
    except ValueError:return False

def guard(event,args):
    if event=='sqlite3.connect':
        raw=str(args[0])
        if raw==':memory:':return
        raw=raw.removeprefix('file:').split('?',1)[0]
        if not inside(Path(raw).resolve(),scratch):
            raise PermissionError('AUDIT: database outside synthetic scratch: '+raw)
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).absolute()
        documents=Path('/Users/adi/Documents')
        if inside(p,documents) and not any(inside(p,r) for r in (scratch,source,output,audit_tools,Path(sys.prefix))):
            raise PermissionError('AUDIT: unrelated Documents read/write blocked: '+str(p))
        if any(inside(p,Path(r)) for r in ('/mnt','/workspace','/database','/config','/logs','/main-library','/sources')):
            raise PermissionError('AUDIT: production-shaped root blocked: '+str(p))

sys.addaudithook(guard)
