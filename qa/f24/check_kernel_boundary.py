"""Real Linux Landlock tests at the post-validation syscall boundary."""
import json,os,tempfile,errno
from pathlib import Path
from app.trash_path_safety import DirectoryTree,identity

out=Path(os.environ['F24_KERNEL_OUTPUT']);out.mkdir(parents=True,exist_ok=True);rows=[]
for operation in ('rename','unlink','link','mkdir','copy','json'):
 case=Path(tempfile.mkdtemp(prefix='f24-kernel-',dir='/tmp'));ws=case/'workspace';ws.mkdir();source=ws/'source';source.mkdir();private=ws/'private';private.mkdir(mode=0o700)
 (source/'A.JPG').write_bytes(b'original');(private/'A.JPG').write_bytes(b'private-original')
 with DirectoryTree(ws) as tree:
  src=tree.directory(source);dst=tree.directory(private,private=True);tree.enable_confinement();tree.verify()
  proof=tree.native('probe')
  tree.native('rename',src=src,source='A.JPG',dst=dst,target='positive.JPG')
  tree.native('rename',src=dst,source='positive.JPG',dst=src,target='A.JPG')
  # Deliberately mutate AFTER the caller's last validation, using existing FDs.
  outside=case/'outside';outside.mkdir();source.rename(outside/'moved');moved=outside/'moved';(moved/'A.JPG').rename(moved/'saved-original');(moved/'A.JPG').write_bytes(b'synthetic-foreign')
  expected=(moved/'A.JPG').read_bytes();arguments={'dst':src,'target':'A.JPG'}
  if operation in {'rename','link'}:arguments={'src':src,'source':'A.JPG','dst':dst,'target':'captured.JPG'}
  elif operation=='mkdir':arguments['target']='new-directory'
  elif operation=='copy':arguments['src']=tree.open_file(private/'A.JPG');arguments['target']='new-copy.JPG'
  elif operation=='json':arguments['value']={'synthetic':True}
  try:tree.native(operation,**arguments);denied=False;code=None
  except OSError as error:denied=error.errno in (errno.EACCES,errno.EPERM,errno.EXDEV);code=error.errno
  assert denied,(operation,code)
  assert (moved/'A.JPG').read_bytes()==expected and not (private/'captured.JPG').exists()
  rows.append({'operation':operation,'uid':os.geteuid(),'landlock_abi':proof['landlock_abi'],'positive_inside_rename':True,'after_last_check':True,'errno':code,'outside_bytes_retained':True,'case':str(case),'result':'PASS'})
(out/'kernel-boundary.json').write_text(json.dumps(rows,indent=2));print('PASS: six real post-check kernel denials; outside bytes unchanged.')
