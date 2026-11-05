"""External test observer; installed only by disposable QA bind mount."""
import json,os,signal,sys,threading
from pathlib import Path
if os.environ.get('RC14_BOUNDARY'):
 marker=Path('/qa-evidence/rc14-checkpoint.json');count=0
 def observe(frame,event,value):
  global count
  if (os.environ['RC14_BOUNDARY']=='retirement' and event=='c_return'
      and getattr(value,'__name__','')=='commit' and frame.f_code.co_name=='remove'
      and frame.f_code.co_filename.endswith('/app/library_retirement.py') and not marker.exists()):
   connection=frame.f_locals['connection']
   row=connection.execute('SELECT is_registered FROM libraries WHERE library_id=?',(frame.f_locals['library_id'],)).fetchone()
   if row and not row[0]:
    assert os.getuid()==568
    with marker.open('w') as f:json.dump({'boundary':'retirement-registry-committed','uid':568,'pid':os.getpid(),'event':event,'function':'remove.commit','thread':threading.current_thread().name},f);f.flush();os.fsync(f.fileno())
    sys.setprofile(None);os.kill(os.getpid(),signal.SIGKILL)
  if event!='return':return
  name=frame.f_code.co_name;boundary=os.environ['RC14_BOUNDARY']
  match=(boundary=='journal' and name=='_atomic_json' and str(frame.f_locals.get('path','')).endswith('/move-journal.json'))
  if name=='publish_import_file' and frame.f_code.co_filename.endswith('/app/import_publication.py'):
   count+=1;match=boundary=='partial' and count==3
  if match and not marker.exists():
   assert os.getuid()==568
   with marker.open('w') as f:json.dump({'boundary':boundary,'uid':os.getuid(),'pid':os.getpid(),'event':event,'function':name,'thread':threading.current_thread().name},f);f.flush();os.fsync(f.fileno())
   sys.setprofile(None);os.kill(os.getpid(),signal.SIGKILL)
 threading.setprofile_all_threads(observe)
