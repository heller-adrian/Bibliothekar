"""Actual released RC13 staging -> RC14 continuation, HTTP and RO mounts."""
import importlib.util,json,os,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('oldqa',Path(__file__).parents[1]/'rc13/container.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
base=Path(os.environ['RUNNER_TEMP'])/'rc14-container';base.mkdir()
logs=Path(os.environ['RUNNER_TEMP'])/'rc14-container-logs';logs.mkdir()
report={'source':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN','cases':[]}
def run_case(boundary):
 root=base/boundary;root.mkdir()
 for name in ('appdata','workspace','archive','business','nas','evidence'):(root/name).mkdir()
 old.command('sudo','chown','-R','568:568',str(root))
 old.docker('run','--rm','--user','568:568','-v',str(root)+':/fixture','--entrypoint','python',os.environ['RC13_IMAGE'],'-c',r'''
from pathlib import Path
from PIL import Image
import subprocess
root=Path('/fixture/nas/CARD');root.mkdir()
Path('/fixture/nas/BusinessArchive').mkdir()
for i in range(16):Image.new('RGB',(8,8),(i,30,20)).save(root/f'PHOTO{i:03}.JPG')
subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:10:27 12:00:00',str(root)],check=True,capture_output=True)
Path('/fixture/workspace/.DS_Store').write_bytes(b'Finder')
Path('/fixture/archive/untouched.txt').write_bytes(b'independent archive')
# Business archive is an authorized future Folder Import source too.
business=Path('/fixture/business');Image.new('RGB',(8,8),'blue').save(business/'BUSINESS.JPG')
subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:10:26 12:00:00',str(business)],check=True,capture_output=True)
''')
 name='bibliothekar-rc14-'+boundary
 def create(image,observe=False):
  args=['--read-only','--tmpfs','/tmp:size=64m,mode=1777','-p','127.0.0.1:18319:8080']
  env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_POOL_PROBE':'/workspace','KAMERA_NAS_SOURCE_ROOT':'/sources/nas','KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-rc13-upgrade-password'}
  if observe:env.update(PYTHONPATH='/qa-code:/opt/kamera',RC14_BOUNDARY=boundary)
  elif boundary=='journal':env.update(PYTHONPATH='/qa-code:/opt/kamera',RC14_BOUNDARY='retirement')
  for k,v in env.items():args+=['-e',k+'='+v]
  for src,dst in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('business','/Businessarchiv:ro'),('nas','/sources/nas:ro'),('evidence','/qa-evidence')]:args+=['-v',str(root/src)+':'+dst]
  args+=['-v',str(root/'business')+':/sources/nas/BusinessArchive:ro','-v',str(old.source/'qa/rc14')+':/qa-code:ro']
  old.docker('create','--name',name,*args,image);old.docker('start',name)
 def snapshot():return json.loads(old.docker('exec','--user','568:568',name,'python','-c',old.SNAPSHOT))
 def wait_job(api,jid):
  for _ in range(400):
   job=api('/api/jobs/'+jid)
   if job['state'] in ('completed','failed','interrupted'):return job
   time.sleep(.2)
  raise AssertionError(job)
 def unregister_when_idle(api,lid):
  path='/api/libraries/'+lid+'/unregister'
  for attempt in range(80):
   try:return api(path,{'confirmation':'REMOVE LIBRARY'})
   except AssertionError as error:
    details=error.args[0] if error.args else None
    if not (isinstance(details,tuple) and len(details)==3
            and details[0]==path and details[1]==409
            and 'Ein anderer Vorgang verwendet diesen Bereich.' in details[2]):
     raise
    if attempt==79:
     raise AssertionError('F14 lock remained busy after bounded retries: '+str(details)) from error
    time.sleep(.2)
 try:
  create(os.environ['RC13_IMAGE'],True);api=old.client()
  api('/api/libraries',{'display_name':'Main Library','work_root':'','archive_root':'/main-library'},expect=201)
  old.docker('exec','--user','568:568',name,'python','-c',"import json;from pathlib import Path;p=Path('/appdata/config/settings.json');v=json.loads(p.read_text());v.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(v))")
  task=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'CARD','source_mode':'folder'},expect=202)['task_id']
  for _ in range(600):
   if (root/'evidence/rc14-checkpoint.json').exists() and old.docker('inspect','-f','{{.State.Running}}',name).strip()=='false':break
   time.sleep(.2)
  if not (root/'evidence/rc14-checkpoint.json').exists():
   diagnostic={'boundary':boundary,'phase':'initial-import','task_id':task,
               'container':old.docker('inspect','-f','{{json .State}}',name,check=False).stdout.strip()}
   for key,path in [('recheck','/api/sd-rechecks/'+task),('history','/api/import-history')]:
    try:diagnostic[key]=api(path)
    except Exception as error:diagnostic[key+'_error']=str(error)
   live=old.docker('logs',name,check=False)
   diagnostic['logs_tail']=(live.stdout+live.stderr)[-6000:]
   raise AssertionError('RC14 checkpoint missing: '+json.dumps(diagnostic,default=str,ensure_ascii=False))
  checkpoint=json.loads((root/'evidence/rc14-checkpoint.json').read_text())
  assert checkpoint['boundary']==boundary and checkpoint['uid']==568 and checkpoint['event']=='return',checkpoint
  assert checkpoint['function']==('_atomic_json' if boundary=='journal' else 'publish_import_file'),checkpoint
  assert checkpoint['thread']=='kamera-job-worker',checkpoint
  assert old.docker('inspect','-f','{{.State.ExitCode}}',name).strip()!='0',checkpoint
  # The runner cannot rename UID568-owned evidence in this host fixture.
  old.command('sudo','mv',str(root/'evidence/rc14-checkpoint.json'),str(root/'evidence/rc13-import-checkpoint.json'))
  old.docker('rm',name);create(os.environ['IMAGE']);api=old.client()
  history=api('/api/import-history')['jobs'];job=next(j for j in history if j['operation']=='folder_import')
  assert job['state'] in ('failed','interrupted'),job
  before=snapshot();assert len(before['files'])==16
  jid=job['id'];proof=api('/api/jobs/'+jid+'/import-recovery',{'action':'inspect'})
  assert proof['staged_file_count']==(16 if boundary=='journal' else 13),proof
  assert proof['published_file_count']==(0 if boundary=='journal' else 3),proof
  tasks=api('/api/tasks');assert not any(t.get('kind')=='unassigned_families' and t.get('count') for t in tasks['tasks']),tasks
  api('/api/jobs/'+jid+'/import-recovery',{'action':'resume','confirmation':'RESUME ORIGINAL IMPORT'})
  completed=wait_job(api,jid);assert completed['state']=='completed',completed
  after=snapshot();assert after['origin']==before['origin'] and after['readonly']==before['readonly']
  second=api('/api/libraries',{'display_name':'Business','work_root':'','archive_root':'/Businessarchiv'},expect=201)['library']
  assert second['work_root']=='/workspace/Library Workspaces/business',second
  lid=second['library_id']
  if boundary=='journal':
   try:unregister_when_idle(api,lid)
   except OSError:pass
   for _ in range(200):
    if (root/'evidence/rc14-checkpoint.json').exists() and old.docker('inspect','-f','{{.State.Running}}',name).strip()=='false':break
    time.sleep(.2)
   if not (root/'evidence/rc14-checkpoint.json').exists():
    live=old.docker('logs',name,check=False)
    diagnostic={'boundary':boundary,'phase':'retirement','library_id':lid,
                'container':old.docker('inspect','-f','{{json .State}}',name,check=False).stdout.strip(),
                'logs_tail':(live.stdout+live.stderr)[-6000:]}
    try:diagnostic['libraries']=api('/api/libraries')
    except Exception as error:diagnostic['api_error']=str(error)
    raise AssertionError('RC14 retirement checkpoint missing: '+json.dumps(diagnostic,default=str,ensure_ascii=False))
   retirement_checkpoint=json.loads((root/'evidence/rc14-checkpoint.json').read_text())
   assert retirement_checkpoint['boundary']=='retirement-registry-committed' and retirement_checkpoint['event']=='c_return' and retirement_checkpoint['function']=='remove.commit',retirement_checkpoint
   assert retirement_checkpoint['uid']==568 and old.docker('inspect','-f','{{.State.ExitCode}}',name).strip()!='0',retirement_checkpoint
   old.docker('start',name);api=old.client();assert api('/api/settings/storage-health')['ready']
   assert not any(r['library_id']==lid for r in api('/api/libraries')['libraries'])
  else:unregister_when_idle(api,lid)
  assert (root/'workspace/Library Workspaces/business').is_dir()
  # The only re-entry route is the normal Folder Import API via explicit RO source.
  admitted=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'BusinessArchive','source_mode':'folder'},expect=202)
  for _ in range(300):
   checked=api('/api/sd-rechecks/'+admitted['task_id'])
   if checked['state'] in ('completed','failed'):break
   time.sleep(.2)
  assert checked['state']=='completed',checked
  reentry=wait_job(api,checked['result']['import_job_id']);assert reentry['state']=='completed',reentry
  for _ in range(2):
   old.docker('restart',name);api=old.client();assert api('/api/settings/storage-health')['ready']
  assert snapshot()['readonly']==before['readonly']
  report['cases'].append({'boundary':boundary,'status':'PASS','uid':568,'real_rc13_upgrade':True,'original_job_resumed':jid,'normal_archive_reimport':True,'two_restarts':True,'readonly_bytes_unchanged':True,'import_crash':checkpoint,'retirement_crash':retirement_checkpoint if boundary=='journal' else None})
 finally:
  result=old.docker('logs',name,check=False);(logs/(boundary+'.log')).write_text(result.stdout+result.stderr)
  old.docker('rm','-f',name,check=False)
  (Path(os.environ['RUNNER_TEMP'])/'rc14-evidence.json').write_text(json.dumps(report,indent=2))
run_case('journal');run_case('partial')
