"""Isolated container fixture from supplied RC10 evidence; no fixed live inodes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import pwd

assert os.environ.get('RC11_QA_SYNTHETIC')=='true'
assert Path('/qa-evidence').is_dir()
from app.storage_config import ENGLISH_STORAGE_DEFAULTS as names
root=Path('/workspace')
for name in names.values():
    path=root/name;path.mkdir(exist_ok=True);os.chown(path,568,0)
meta=root/'Metadata Correction'
for name in ('General','Batch Correction','.trash-deletions'):
    path=meta/name;path.mkdir(exist_ok=True);os.chown(path,568,0)
(meta/'.trash-deletions').chmod(0o2700)
control=Path('/database/.bibliothekar-root-control');control.mkdir(mode=0o700,exist_ok=True);os.chown(control,568,0);control.chmod(0o2700)
leaf=control/hashlib.sha256(b'/workspace').hexdigest();leaf.mkdir(mode=0o700,exist_ok=True);os.chown(leaf,568,0);leaf.chmod(0o2700)
os.setgroups([]);os.setgid(568);os.setuid(568)
from app import root_operations as ro
from app.storage_bootstrap import key_for
from app.database import initialize_database
from app.library_registry import initialize_library_registry
source=json.loads(Path('/qa-rc10.json').read_text());state=copy.deepcopy(source['state']);operation=copy.deepcopy(source['operation'])
bindings={str(path):ro._identity(path) for path in [root,*(root/n for n in names.values())]}
state.update(workspace=bindings['/workspace'],bindings=bindings);operation['bindings']=bindings
if os.environ.get('RC11_QA_LEGACY_COMPLETED')=='true':state['storage_initialization']['phase']='completed'
ro._write(leaf/'state.json',state);ro._write(leaf/('operation-'+key_for(operation)+'.json'),operation)
Path('/config/settings.json').write_text('{}')
initialize_database(Path('/database/kamera.sqlite3'));initialize_library_registry(Path('/database/bibliothekar-global.sqlite3'))
lock=meta/'.trash-deletions/.lock';lock.write_bytes(b'');lock.chmod(0o770)
info=lock.stat();assert info.st_uid==568 and info.st_gid==0 and info.st_size==0 and info.st_nlink==1
original={'state':(leaf/'state.json').read_text(),'operation':(leaf/('operation-'+key_for(operation)+'.json')).read_text(),'bindings':bindings,'reservation_id':operation['reservation_id'],'lock_identity':[info.st_dev,info.st_ino],'lock_mode':info.st_mode&0o777,'lock_gid':info.st_gid}
Path('/qa-evidence/rc10-original.json').write_text(json.dumps(original,indent=2))
