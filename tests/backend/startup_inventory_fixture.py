from pathlib import Path
import hashlib,json,sqlite3
from app.database import initialize_database,database_connection
from app.library_registry import initialize_library_registry,_canonical_family_id
from app.global_library_inventory import family_content_fingerprint
NOW='2026-10-29T12:00:00+00:00'
def seed(root,count, *, registry=None, databases=None, library_ids=('main','second'), existing=False):
 root=Path(root);root.mkdir(parents=True,exist_ok=True);reg=registry or root/'registry.sqlite3';dbs=databases or [root/'main.sqlite3',root/'second.sqlite3']
 initialize_library_registry(reg)
 for db in dbs:
  initialize_database(db)
  with database_connection(db) as c:
   c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_path,source_signature,created_at,updated_at) VALUES('J','sd_import','manual','completed','organized_verified','folder_import','/synthetic-source','synthetic-source',?,?)",(NOW,NOW))
   for i in range(count):
    family=f'F{i:05}';rel=f'2026/2026-10-29/{family}.JPG';sha=hashlib.sha256(f'synthetic-{i}'.encode()).hexdigest()
    c.execute("INSERT INTO file_families(id,job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES(?,'J',?,?,'complete','2026-10-29T12:00:00+00:00','high')",(i+1,family,family))
    c.execute("INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,current_root_kind,created_at,updated_at) VALUES('J',?,?,?,? ,'.JPG','jpeg',?, ?,?,'shared_workspace',?,?)",(i+1,rel,rel,Path(rel).name,len(f'synthetic-{i}'.encode()),sha,sha,NOW,NOW))
 with sqlite3.connect(reg) as c:
  for lid,db in zip(library_ids,dbs):
   if not existing:c.execute('INSERT INTO libraries(library_id,display_name,database_path,workspace_root,work_root,archive_root,is_main,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(lid,lid,str(db),str(root/'workspace'),str(root/'workspace'/lid),str(root/('archive-'+lid)),lid=='main',NOW,NOW))
   c.execute('INSERT INTO source_backups VALUES(?,?,?,?,?,?,?)',(lid+':J','import' if lid=='main' else 'existing_library','synthetic-source' if lid=='main' else lid+':synthetic-source','/synthetic-source','{}',NOW,NOW))
  for i in range(count):
   family=f'F{i:05}';rel=f'2026/2026-10-29/{family}.JPG';sha=hashlib.sha256(f'synthetic-{i}'.encode()).hexdigest()
   fp=family_content_fingerprint([{'sha256':sha,'size_bytes':len(f'synthetic-{i}'.encode()),'media_type':'jpeg'}]);canonical=_canonical_family_id(fp)
   c.execute('INSERT INTO canonical_families VALUES(?,?,?,?)',(canonical,fp,NOW,NOW))
   for lid in library_ids:
    key=f'{lid}:J:{family}';media=f'{lid}:M{i}';meta={'library_id':lid,'job_id':'J'}
    if lid=='second':meta.update(projection_origin=f'main:J:{family}',projected_missing_members=[])
    c.execute('INSERT INTO source_families VALUES(?,?,?,?,?,?,?)',(key,lid+':J',family,canonical,json.dumps(meta),NOW,NOW))
    c.execute('INSERT INTO source_media VALUES(?,?,?,?,?,?,?,?,?)',(media,lid+':J',rel,len(f'synthetic-{i}'.encode()),sha,'jpeg','{}',NOW,NOW))
    c.execute('INSERT INTO source_family_members(source_family_key,media_id,created_at) VALUES(?,?,?)',(key,media,NOW))
 return reg,dbs
