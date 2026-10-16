"""Disposable Linux runner proof, invoking a separately unprivileged writer.
The supervisor uses sudo only to drop the child to nobody; the app does not.
"""
import errno,json,os,subprocess,sys,tempfile
from pathlib import Path
from app.trash_path_safety import DirectoryTree
from app.storage_config import load_storage_settings

out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
case=Path(tempfile.mkdtemp(prefix='f24-uid-',dir='/tmp'));case.chmod(0o755)
# Ancestors supplied by this CI-only disposable case must be traversable.
ws=case/'workspace';ws.mkdir(mode=0o755);trash=ws/'trash';trash.mkdir(mode=0o777);trash.chmod(0o777)
meta=ws/'metadata';meta.mkdir(mode=0o755)
private=meta/'.trash-deletions';private.mkdir(mode=0o700)
stage=private/'operation';stage.mkdir(mode=0o700)
file=stage/'A.JPG';file.write_bytes(b'synthetic-private-original');file.chmod(0o600)
with DirectoryTree(ws) as tree:tree.directory(private,private=True);tree.directory(stage,private=True);tree.qualify_filesystem(tree.directory(stage))
program=r'''import errno,json,os,sys
from pathlib import Path
os.setgroups([]);os.setgid(65534);os.setuid(65534)
public=Path(sys.argv[1]);private=Path(sys.argv[2]);rows=[]
(public/'external-can-write').write_bytes(b'synthetic-public-writer')
for name,fn in [
 ('read',lambda:(private/'A.JPG').read_bytes()),
 ('write',lambda:(private/'A.JPG').write_bytes(b'changed')),
 ('unlink',lambda:(private/'A.JPG').unlink()),
 ('replace',lambda:os.replace(public/'external-can-write',private/'A.JPG')),
 ('create',lambda:(private/'foreign.JPG').write_bytes(b'foreign')),
 ('rename',lambda:(private/'A.JPG').rename(private/'renamed.JPG'))]:
 try:fn();rows.append({'operation':name,'denied':False})
 except OSError as e:rows.append({'operation':name,'denied':e.errno in (errno.EACCES,errno.EPERM),'errno':e.errno})
cap=next(l.split(':',1)[1].strip() for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:'))
print(json.dumps({'uid':os.geteuid(),'gid':os.getegid(),'cap_eff':cap,'public_write_succeeded':True,'operations':rows}))
'''
# Runner has passwordless sudo. No mounts, devices, services or host data.
child=subprocess.run(['sudo','-n',sys.executable,'-c',program,str(trash),str(stage)],text=True,capture_output=True,timeout=10)
assert child.returncode==0,child.stderr
record=json.loads(child.stdout);assert record['uid']!=os.geteuid() and record['uid']!=0 and int(record['cap_eff'],16)==0
assert all(r['denied'] for r in record['operations']) and record['public_write_succeeded']
assert file.read_bytes()==b'synthetic-private-original'
(out/'distinct-uid.json').write_text(json.dumps({'app_uid':os.geteuid(),'mode':oct(stage.stat().st_mode&0o777),'case':str(case),'writer':record,'result':'PASS'},indent=2))
print('PASS: distinct unprivileged UID can write public trash; six private-stage operations denied.')
