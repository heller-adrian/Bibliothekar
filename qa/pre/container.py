"""Actual released RC14 batch correction -> candidate upgrade, RO archives.
No database edits: RC14 itself creates the truncated timestamp regression.
"""
import importlib.util,json,os,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('oldqa',Path(__file__).parents[1]/'rc13/container.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
root=Path(os.environ['RUNNER_TEMP'])/'pre-container';root.mkdir()
for folder in ('appdata','workspace','archive','business','nas'):(root/folder).mkdir()
# These directories were just created by this isolated fixture. Use the
# authorized Docker runtime; no sudo or host permission changes are required.
old.docker('run','--rm','--network','none','-v',str(root)+':/fixture',
           '--entrypoint','python',os.environ['IMAGE'],'-c',
           "from pathlib import Path;import os;r=Path('/fixture');assert not r.is_symlink();os.chown(r,568,568);[os.chown(p,568,568) for p in r.iterdir() if p.is_dir() and not p.is_symlink()]")
old.docker('run','--rm','--user','568:568','-v',str(root)+':/fixture','--entrypoint','python',os.environ['RC14_IMAGE'],'-c',r'''
from PIL import Image
from pathlib import Path
import subprocess
p=Path('/fixture/nas/CARD');p.mkdir()
for i in range(14):Image.new('RGB',(8,8),(i*17,i*13,i*7)).save(p/f'PHOTO{i:03}.JPG')
# Conflicting high-confidence tags put the original files in Undated.
# The batch correction must then make all tags consistently +13:00.
subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2025:12:07 15:04:37','-EXIF:OffsetTimeOriginal=+13:00','-XMP-exif:DateTimeOriginal=2024:12:07 15:04:37+01:00',str(p)],check=True,capture_output=True)
Path('/fixture/archive/untouched.txt').write_bytes(b'independent archive')
Path('/fixture/business/untouched.txt').write_bytes(b'second independent archive')
Path('/fixture/workspace/.DS_Store').write_bytes(b'Finder')
''')
name='bibliothekar-pre-upgrade'
def create(image):
 args=['--read-only','--tmpfs','/tmp:size=64m,mode=1777','-p','127.0.0.1:18319:8080']
 env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_POOL_PROBE':'/workspace','KAMERA_NAS_SOURCE_ROOT':'/sources/nas','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-rc13-upgrade-password'}
 if image==os.environ['RC14_IMAGE']:env['KAMERA_SOURCE_HELPER_ENABLED']='false'
 # Exercise the corrected candidate default without a helper override.
 for k,v in env.items():args+=['-e',k+'='+v]
 for src,dst in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('business','/Businessarchiv:ro'),('nas','/sources/nas:ro')]:args+=['-v',str(root/src)+':'+dst]
 old.docker('create','--name',name,*args,image);old.docker('start',name)
def snapshot():return json.loads(old.docker('exec','--user','568:568',name,'python','-c',old.SNAPSHOT))
def pending_metadata():
 return json.loads(old.docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;import json;p=Path('/appdata/database/.bibliothekar-root-control');print(json.dumps([r for f in p.rglob('operation-*.json') if (r:=json.loads(f.read_text())).get('ids',{}).get('function')=='app.metadata_correction.reintegrate_library_metadata_family']))"))

def wait_import(api,task):
 for _ in range(600):
  rows=api('/api/import-history')['jobs'];active=[j for j in rows if j['operation']=='folder_import']
  if active and active[0]['state'] in ('completed','failed','interrupted'):
   assert active[0]['state']=='completed',active;return active[0]
  time.sleep(.25)
 raise AssertionError({'task':task,'jobs':rows})
report={'commit':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN'}
try:
 create(os.environ['RC14_IMAGE']);api=old.client()
 report['rc14_exiftool']=old.docker('exec',name,'exiftool','-ver').strip()
 api('/api/libraries',{'display_name':'Main Library','work_root':'','archive_root':'/main-library'},expect=201)
 old.docker('exec','--user','568:568',name,'python','-c',"import json;from pathlib import Path;p=Path('/appdata/config/settings.json');v=json.loads(p.read_text());v.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(v))")
 task=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'CARD','source_mode':'folder'},expect=202)
 job=wait_import(api,task)
 scan=api('/api/metadata-correction/scan?area=library');files=scan['files'];assert len(files)==14,scan
 source_type=next(c['source_type'] for c in files[0]['metadata_candidates'] if c['usable'] and c['normalized_datetime'].endswith('+13:00'))
 items=[{'library_id':f['library_id'],'family_id':f['family_id']} for f in files]
 api('/api/metadata-correction/correct-batch',{'area':'library','source_type':source_type,'items':items})
 # Required reproduction in original RC14, with a real authenticated HTTP call.
 failure=api('/api/metadata-correction/reintegrate',{'items':items},expect=409)
 assert 'bestätigt' in str(failure),failure
 original_intents=pending_metadata();assert len(original_intents)==1;report['original_intent']=original_intents[0]
 before=snapshot();report['before']=before;assert all(r['selected_capture_time']=='2025-12-07T15:04:37' for r in before['files'])
 old.docker('stop',name);old.docker('rm',name)
 create(os.environ['IMAGE']);api=old.client();health=api('/api/settings/storage-health');assert health['ready'],health
 assert pending_metadata()==original_intents
 report['candidate_exiftool']=old.docker('exec',name,'exiftool','-ver').strip()
 response=api('/api/metadata-correction/reintegrate',{'items':items});report['reintegrate']=response
 assert pending_metadata()==[]
 report['same_reservation_preserved_until_retry']=True
 after=snapshot();report['after']=after;assert after['origin']==before['origin'] and after['readonly']==before['readonly']
 assert all(r['selected_capture_time']=='2025-12-07T15:04:37+13:00' for r in after['files'])
 assert all('Undated' not in r['current_relative_path'] and '2025-12-07' in r['current_relative_path'] for r in after['files'])
 old.docker('restart',name);api=old.client();assert api('/api/settings/storage-health')['ready']
 second=api('/api/libraries',{'display_name':'After metadata upgrade','work_root':'','archive_root':'/Businessarchiv'},expect=201)['library']
 final=snapshot();report['final']=final
 from origin_proof import assert_projection_preserves_origins
 assert_projection_preserves_origins(before['origin'],final['origin'],second['library_id'])
 assert final['readonly']==before['readonly']
 report.update(status='PASS',corrected_files=14,rc14_failure=failure,origin_preserved=True,readonly_bytes_preserved=True)
finally:
 log=old.docker('logs',name,check=False)
 (Path(os.environ['RUNNER_TEMP'])/'pre-container.log').write_text(log.stdout+log.stderr)
 print((log.stdout+log.stderr)[-18000:])
 (Path(os.environ['RUNNER_TEMP'])/'pre-evidence.json').write_text(json.dumps(report,indent=2))
 old.docker('rm','-f',name,check=False)
print(json.dumps(report,indent=2))
