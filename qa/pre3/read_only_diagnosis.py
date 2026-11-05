"""Print evidence only. Persistent NAS files are opened O_RDONLY; SQLite opens
verified temporary copies under /tmp, never the live databases. No authority to
complete an operation. Run inside the existing container as web UID 568.
"""
from contextlib import ExitStack
import hashlib,json,os,re,shutil,sqlite3,stat,tempfile
from pathlib import Path
import app  # Configure environment defaults only; no app.main or startup import.

workspace=Path(os.environ.get('KAMERA_WORKSPACE','/workspace')).absolute()
registry=Path(os.environ.get('KAMERA_REGISTRY_DATABASE','/appdata/database/bibliothekar-global.sqlite3')).absolute()
control=registry.parent/'.bibliothekar-root-control'/hashlib.sha256(str(workspace).encode()).hexdigest()
report={'diagnostic_only':True,'authorization':False,'workspace':str(workspace),'control':str(control),'errors':[]}


def signature(path):
    try:s=path.lstat()
    except FileNotFoundError:return None
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise RuntimeError('not a single-link regular file: '+str(path))
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


def read(path,limit=32*1024*1024):
    if path.resolve()!=path:raise RuntimeError('symlink path refused: '+str(path))
    before=signature(path)
    if before is None:return None
    if before[2]>limit:raise RuntimeError('diagnostic size limit: '+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        chunks=[]
        while block:=os.read(fd,1048576):chunks.append(block)
    finally:os.close(fd)
    if signature(path)!=before:raise RuntimeError('evidence changed during read: '+str(path))
    return b''.join(chunks)


def record(path):
    data=read(path)
    return None if data is None else json.loads(data)


def disk(path):
    path=Path(path).absolute();result={'path':str(path),'diagnostic_only':True}
    try:
        if not path.is_relative_to(workspace) or path.resolve()!=path:raise RuntimeError('outside workspace or symlink')
        info=signature(path)
        if info is None:return dict(result,exists=False)
        result.update(exists=True,identity=list(info[:2]),size_bytes=info[2],mtime_ns=info[3],ctime_ns=info[4])
        digest=hashlib.sha256();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            while block:=os.read(fd,1048576):digest.update(block)
        finally:os.close(fd)
        if signature(path)!=info:raise RuntimeError('file changed during hashing')
        result['sha256']=digest.hexdigest()
    except Exception as error:result['error']=str(error)
    return result


with tempfile.TemporaryDirectory(prefix='bibliothekar-read-diagnosis-',dir='/tmp') as temporary,ExitStack() as stack:
    cache={}
    def database(path):
        path=Path(path).absolute()
        if path in cache:return cache[path]
        names=[path,Path(str(path)+'-wal'),Path(str(path)+'-shm')]
        initial={p:signature(p) for p in names}
        if initial[path] is None:raise RuntimeError('database missing: '+str(path))
        if sum(v[2] for v in initial.values() if v)>shutil.disk_usage(temporary).free:
            raise RuntimeError('insufficient isolated /tmp space; persistent storage will not be changed')
        target=Path(temporary)/(str(len(cache))+'.sqlite3');hashes={}
        for source,info in initial.items():
            if info is None:continue
            data=read(source,limit=512*1024*1024)
            if data is None:raise RuntimeError('database sidecar disappeared: '+str(source))
            suffix=str(source)[len(str(path)):];Path(str(target)+suffix).write_bytes(data)
            hashes[source]=hashlib.sha256(data).hexdigest()
        if any(signature(p)!=v for p,v in initial.items()):raise RuntimeError('database changed while copying; retry during idle: '+str(path))
        for p,sha in hashes.items():
            if hashlib.sha256(read(p,limit=512*1024*1024)).hexdigest()!=sha:raise RuntimeError('database snapshot is not stable: '+str(path))
        c=sqlite3.connect(target);stack.callback(c.close);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('copied database is inconsistent: '+str(path))
        cache[path]=c;return c
    try:
        report['state']=record(control/'state.json')
        libraries=[dict(r) for r in database(registry).execute('SELECT * FROM libraries ORDER BY library_id')]
        report['libraries']=libraries;allowed={str(Path(r['database_path']).absolute()) for r in libraries}
        operations=[]
        for path in sorted(control.glob('operation-*.json')):
            item={'path':str(path)}
            try:
                value=record(path);item['record']=value
                nonce=value.get('reservation_id','')
                if len(nonce)==32 and all(x in '0123456789abcdef' for x in nonce):
                    item['receipts']={prefix:record(control/(prefix+nonce+'.json')) for prefix in ('finished-','metadata-intent-','metadata-outcome-','metadata-location-')}
                db=value.get('database')
                if db in allowed:
                    c=database(db);ids=value.get('ids') or {}
                    if ids.get('correction_id'):tasks=c.execute('SELECT * FROM metadata_corrections WHERE id=?',(ids['correction_id'],)).fetchall()
                    elif ids.get('area')=='general' and ids.get('relative_path'):tasks=c.execute("SELECT * FROM metadata_corrections WHERE area='general' AND source_relative_path=?",(ids['relative_path'],)).fetchall()
                    else:tasks=[]
                    item['metadata_tasks']=[dict(t) for t in tasks]
                    if ids.get('job_id'):item['job']=[dict(r) for r in c.execute('SELECT * FROM jobs WHERE id=?',(ids['job_id'],))]
            except Exception as error:item['error']=str(error)
            operations.append(item)
        report['operations']=operations
        wanted={t['source_relative_path'] for o in operations for t in o.get('metadata_tasks',[])}
        report['metadata_files']=[disk(p) for p in sorted({t[k] for o in operations for t in o.get('metadata_tasks',[]) for k in ('source_path','output_path') if t.get(k)})]
        report['bound_roots']=[]
        for path,expected in (report.get('state') or {}).get('bindings',{}).items():
            row={'path':path,'expected_identity':expected}
            try:
                info=Path(path).lstat();row.update(actual_identity=[info.st_dev,info.st_ino],mode=stat.S_IMODE(info.st_mode),uid=info.st_uid,gid=info.st_gid)
            except Exception as error:row['error']=str(error)
            report['bound_roots'].append(row)
        main=next((r for r in libraries if r['library_id']=='main'),None)
        if main:
            c=database(main['database_path'])
            jobs=[dict(r) for r in c.execute("SELECT * FROM jobs WHERE operation='metadata_general_import' ORDER BY created_at LIMIT 2001")]
            if len(jobs)>2000:raise RuntimeError('more than 2000 General import records; request a narrower diagnosis')
            for job in jobs:
                job['files']=[dict(r) for r in c.execute('SELECT f.*,ff.family_key FROM files f JOIN file_families ff ON f.family_id=ff.id AND f.job_id=ff.job_id WHERE f.job_id=?',(job['id'],))]
                if not re.fullmatch(r'GENERAL_IMPORT_(?:[0-9a-f]{32}|[0-9]{8}_[0-9]{6}_[0-9]{6})',job['id']):raise RuntimeError('unexpected General job identifier: '+job['id'])
                logs=Path(os.environ.get('KAMERA_LOG_DIR','/appdata/logs'))/'backups'/job['id']
                job['protocol']={}
                if logs.resolve()!=logs:raise RuntimeError('protocol symlink: '+str(logs))
                for name in ('manifest.json','move-journal.json','status.json'):job['protocol'][name]=record(logs/name)
                journal=job['protocol'].get('move-journal.json') or {}
                job['candidate_destination_files']=[disk(Path(journal['root'])/entry['destination_relative_path'])
                    for entry in journal.get('files',[]) if entry.get('source_relative_path') in wanted and journal.get('root')]
            report['general_imports']=jobs
    except Exception as error:report['errors'].append(str(error))
print(json.dumps(report,ensure_ascii=False,indent=2))
