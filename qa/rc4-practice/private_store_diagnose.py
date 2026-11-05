"""Read-only TrueNAS host inventory for /database and /config qualification.

No application imports, DB opens, media reads, permission changes or repairs.
Run on the TrueNAS host; raw ACLs are evidence, never an automatic qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

CONTAINER='ix-bibliothekar-bibliothekar-1'
WORKSPACE='/workspace'
PROC_PROBE="""import json,os
rows=[]
for p in os.listdir('/proc'):
 if not p.isdigit():continue
 try:
  cmd=open('/proc/'+p+'/cmdline','rb').read()
  if b'uvicorn' not in cmd or b'app.main:app' not in cmd:continue
  fields={k:v.strip() for k,v in (line.split(':',1) for line in open('/proc/'+p+'/status') if ':' in line) if k in ('Uid','Gid','Groups','CapEff','NSpid')}
  fields['pid']=int(p);fields['uid_map']=open('/proc/'+p+'/uid_map').read();fields['gid_map']=open('/proc/'+p+'/gid_map').read();rows.append(fields)
 except (OSError,ValueError):continue
print(json.dumps(rows))
"""


def run_json(argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=20,check=True)
    return json.loads(r.stdout)


def plan(info):
    mounts=info.get('Mounts',[]);roots={};targets=[]
    for destination in ('/database','/config'):
        found=[m for m in mounts if m.get('Destination')==destination]
        if len(found)!=1:raise ValueError('Exactly one existing mount required: '+destination)
        mount=found[0];raw=mount.get('Source','');path=Path(raw)
        if not path.is_absolute() or '..' in path.parts or path==Path('/'):
            raise ValueError('Unbounded mount source: '+destination)
        if mount.get('Type') not in {'bind','volume'}:raise ValueError('Unsupported mount type: '+destination)
        roots[destination]={'source':str(path),'type':mount['Type'],'rw':mount.get('RW')}
        # An ancestor that can replace its child also affects the trust boundary.
        targets.extend(reversed([path,*path.parents]))
    db=Path(roots['/database']['source']);config=Path(roots['/config']['source'])
    control=db/'.bibliothekar-root-control'
    targets.extend([db/'kamera.sqlite3',db/'kamera.sqlite3-wal',db/'kamera.sqlite3-shm',
                    db/'bibliothekar-global.sqlite3',db/'bibliothekar-global.sqlite3-wal',
                    db/'bibliothekar-global.sqlite3-shm',control,
                    control/hashlib.sha256(WORKSPACE.encode()).hexdigest(),config/'settings.json'])
    work=[Path(m['Source']) for m in mounts if m.get('Destination')=='/workspace' and m.get('Source')]
    for value in roots.values():
        p=Path(value['source']);value['inside_shared_workspace']=any(p==w or w in p.parents for w in work)
    return roots,list(dict.fromkeys(map(str,targets)))


def plain_existing(path):
    p=Path(path)
    for component in [*reversed(p.parents),p]:
        s=os.lstat(component)
        if stat.S_ISLNK(s.st_mode):raise ValueError('Symlink component; ACL path not followed: '+str(component))
    return s


def collect(container=CONTAINER,run=run_json,inspect_path=plain_existing):
    data=run(['docker','inspect',container])
    if not isinstance(data,list) or len(data)!=1:raise ValueError('Container is not uniquely identified')
    info=data[0];roots,targets=plan(info)
    result={'container':container,'roots':roots,'qualification':'NOT_PERFORMED',
            'container_user':info.get('Config',{}).get('User'),
            'userns_mode':info.get('HostConfig',{}).get('UsernsMode'),
            'privileged':info.get('HostConfig',{}).get('Privileged'),'paths':[]}
    try:result['web_credentials']=run(['docker','exec',container,'python','-I','-c',PROC_PROBE])
    except (OSError,ValueError,subprocess.SubprocessError) as error:result['web_credentials_error']=str(error)
    for path in targets:
        item={'path':path}
        try:
            s=inspect_path(path)
            item.update(uid=s.st_uid,gid=s.st_gid,mode=oct(stat.S_IMODE(s.st_mode)),dev=s.st_dev,ino=s.st_ino,nlink=s.st_nlink)
            item['acl']=run(['midclt','call','filesystem.getacl',path,'false','true'])
        except (OSError,ValueError,subprocess.SubprocessError) as error:item['unqualified_reason']=str(error)
        result['paths'].append(item)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container',default=CONTAINER)
    print(json.dumps(collect(parser.parse_args().container),ensure_ascii=False,indent=2))
