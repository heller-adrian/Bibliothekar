"""External test observer; installed only by disposable QA bind mount."""
import json,os,signal,sys
from pathlib import Path
if os.environ.get('RC14_BOUNDARY'):
 marker=Path('/qa-evidence/rc14-checkpoint.json');count=0
 def observe(frame,event,value):
  global count
  if event!='return' or marker.exists():return
  name=frame.f_code.co_name;boundary=os.environ['RC14_BOUNDARY']
  match=(boundary=='journal' and name=='_atomic_json' and str(frame.f_locals.get('path','')).endswith('/move-journal.json'))
  if name=='publish_import_file' and frame.f_code.co_filename.endswith('/app/import_publication.py'):
   count+=1;match=boundary=='partial' and count==3
  if match:
   assert os.getuid()==568
   with marker.open('w') as f:json.dump({'boundary':boundary,'uid':os.getuid(),'pid':os.getpid()},f);f.flush();os.fsync(f.fileno())
   sys.setprofile(None);os.kill(os.getpid(),signal.SIGKILL)
 sys.setprofile(observe)
