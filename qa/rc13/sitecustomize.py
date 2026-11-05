"""External SIGKILL observer; mounted read-only only in isolated QA."""
import json
import os
from pathlib import Path
import signal
import sys

if os.environ.get('RC13_QA_BOUNDARY')=='origin-qualified':
    marker=Path('/qa-evidence/rc13-checkpoint.json')
    def observe(frame,event,value):
        if (event=='return' and frame.f_code.co_name=='qualify_origins'
            and frame.f_code.co_filename.endswith('/app/source_provenance.py')
            and not marker.exists()):
            from app.root_operations import _control_location
            control=_control_location(Path('/workspace'))
            records=[json.loads(p.read_text()) for p in control.glob('operation-*.json')]
            startup=[r for r in records if r['kind']=='startup']
            assert len(startup)==1 and startup[0]['ids']=={},records
            assert os.getuid()==568
            with marker.open('w') as stream:
                json.dump({'boundary':'origin-qualified','uid':os.getuid(),'pid':os.getpid(),'startup':startup[0]},stream)
                stream.flush();os.fsync(stream.fileno())
            sys.setprofile(None)
            os.kill(os.getpid(),signal.SIGKILL)
    sys.setprofile(observe)
