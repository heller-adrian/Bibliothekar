from pathlib import Path
import os,json,hashlib,threading,subprocess,sys
import pytest
from test_process_crashes import invoke,snapshot,checks_sql
from app import main
from app.database import database_connection,create_job,claim_next_job

OUT=Path(os.environ['AUDIT_OUTPUT'])

def seed(tmp_path,kind,name,monkeypatch):
    case=tmp_path/'case';case.mkdir();ev=OUT/name;ev.mkdir()
    assert invoke(case,'seed',kind,ev/'seed')['returncode']==0
    data=json.loads((case/'case.json').read_text());db=Path(data['db']);ws=Path(data['workspace'])
    monkeypatch.setenv('KAMERA_CONFIG',str(db.parent/'settings.json'))
    from app.library_context import resolve_library_context
    context=resolve_library_context(db.parent/'registry.sqlite3','main')
    for k,v in dict(DATABASE_FILE=db,REGISTRY_DATABASE_FILE=db.parent/'registry.sqlite3',WORKSPACE_PATH=ws,MAIN_LIBRARY_CONTEXT=context,LOG_PATH=case/'logs').items():monkeypatch.setattr(main,k,v)
    monkeypatch.setattr(main,'current_database_file',lambda:db)
    snapshot(case,ev/'before.json')
    return case,ev,data,db,ws

def finish(case,ev,trace):
    snapshot(case,ev/'after-interleaving.json')
    (ev/'interleaving.json').write_text(json.dumps(trace,indent=2,default=str))
    for n in (1,2,3):
        r=invoke(case,'startup','none',ev/f'restart{n}')
        snapshot(case,ev/f'after-restart{n}.json')
        assert r['returncode']==0,r

def thread_call(fn):
    results=[]
    def run():
        try:results.append({'ok':True,'value':fn()})
        except Exception as e:results.append({'ok':False,'error':repr(e)})
    t=threading.Thread(target=run);t.start();return t,results

def test_full_empty_reservation_race(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P401-full-empty-race',monkeypatch)
    reached=threading.Event();proceed=threading.Event();real=main.empty_trash_filesystem
    def pause(root):
        reached.set();assert proceed.wait(10);return real(root)
    monkeypatch.setattr(main,'empty_trash_filesystem',pause)
    t,deleted=thread_call(lambda:main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION}))
    assert reached.wait(10)
    restored=main.api_restore_trash({'relative_paths':['A.JPG']})
    snapshot(case,ev/'after-reservation.json');proceed.set();t.join(10);assert not t.is_alive()
    finish(case,ev,{'order':['empty checks no reservation and inventories','restore queues A','empty deletes'], 'delete':deleted,'restore':restored['job_id']})
    assert (ws/'Papierkorb/A.JPG').is_file(),'Reserved original removed by concurrent full empty'

@pytest.mark.parametrize('operation',['full','selective'])
def test_reserved_rejected(tmp_path,monkeypatch,operation):
    case,ev,data,db,ws=seed(tmp_path,'trash','P401-reserved-'+operation,monkeypatch)
    queued=main.api_restore_trash({'relative_paths':['A.JPG']})
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        if operation=='full':main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
        else:main.api_empty_trash_selection({'relative_paths':['A.JPG']})
    assert error.value.status_code==409
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    finish(case,ev,{'order':['reserve A','attempt delete'],'rejection':409,'job':queued['job_id']})

@pytest.mark.parametrize('race',[True,False])
def test_import_target(tmp_path,monkeypatch,race):
    import app.folder_import as fi
    case,ev,data,db,ws=seed(tmp_path,'trash','P402-target-'+str(race),monkeypatch)
    root=ws/'SD-Kartensicherungen';original=root/'.incoming/P4/Original';original.mkdir(parents=True)
    src=original/'S.JPG';src.write_bytes(b'synthetic-import');target=root/'2030/T.JPG';target.parent.mkdir()
    plan=[dict(source_relative_path='S.JPG',destination_relative_path='2030/T.JPG',size_bytes=src.stat().st_size,sha256=hashlib.sha256(src.read_bytes()).hexdigest())]
    if race:
        reached=threading.Event();proceed=threading.Event();replace=fi.os.replace
        def pause(s,d):
            if Path(s)==src:reached.set();assert proceed.wait(10)
            return replace(s,d)
        monkeypatch.setattr(fi.os,'replace',pause)
        t,result=thread_call(lambda:fi.move_import_into_workspace(original,root,plan))
        assert reached.wait(10);target.write_bytes(b'synthetic-foreign');snapshot(case,ev/'foreign-before-replace.json');proceed.set();t.join(10);assert not t.is_alive()
    else:
        target.write_bytes(b'synthetic-foreign')
        with pytest.raises(fi.PipelineError):fi.move_import_into_workspace(original,root,plan)
        result=[{'rejected':True}]
    finish(case,ev,{'order':['exists check','competing writer publishes target','replace'] if race else ['foreign target already exists','import rejected'],'result':result})
    assert target.read_bytes()==b'synthetic-foreign','Foreign destination overwritten between check and replace'


def test_archive_change_before_unlink(tmp_path,monkeypatch):
    from app.ssd_release import release_event_ssd
    case,ev,data,db,ws=seed(tmp_path,'ssd','P405-archive-unlink-race',monkeypatch)
    src=ws/'Arbeitsbereich/2026/07-23 - Trip/Alle/A.JPG';archive=case/'archive/2026/07-23 - Trip/Alle/A.JPG'
    old=src.read_bytes();reached=threading.Event();proceed=threading.Event();unlink=Path.unlink
    def pause(path,*a,**k):
        if path==src:reached.set();assert proceed.wait(10)
        return unlink(path,*a,**k)
    monkeypatch.setattr(Path,'unlink',pause)
    t,result=thread_call(lambda:release_event_ssd(db,ws,case/'archive',data['job'],data['event']))
    assert reached.wait(10);archive.write_bytes(b'X'*len(old));snapshot(case,ev/'archive-changed-before-unlink.json');proceed.set();t.join(10);assert not t.is_alive()
    finish(case,ev,{'order':['archive fully verified','source verified and stat checked','archive overwritten in place','SSD unlink'],'result':result})
    assert (src.exists() and src.read_bytes()==old) or archive.read_bytes()==old,'Last matching synthetic original removed after archive changed'


def test_queue_claim_two_threads(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P408-queue-threads',monkeypatch)
    create_job(db,job_id='P4',kind='sd_import',trigger_type='manual',operation='folder_import',source_path=str(case/'card'))
    barrier=threading.Barrier(3);results=[]
    def claim():barrier.wait(timeout=10);return claim_next_job(db)
    a,x=thread_call(claim);b,y=thread_call(claim);barrier.wait(timeout=10);a.join(10);b.join(10)
    assert not a.is_alive() and not b.is_alive()
    results=x+y;assert all(r['ok'] for r in results)
    assert sum(r['value'] is not None for r in results)==1
    finish(case,ev,{'order':['two threads at barrier','BEGIN IMMEDIATE queue claim'],'results':results})


def test_operation_lock_two_processes(tmp_path,monkeypatch):
    from app.trash_selective import _operation_lock,_parent
    case,ev,data,db,ws=seed(tmp_path,'trash','P401-lock-processes',monkeypatch)
    script=case/'lock_probe.py';script.write_text('''from guards import *
import fcntl
from app.trash_selective import _operation_lock,_parent
ws=Path(sys.argv[1])
if sys.argv[2]=='probe':
 fd=os.open(_parent(ws)/'.lock',os.O_RDWR)
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);print('unexpected-acquisition');sys.exit(2)
 except BlockingIOError:print('blocked')
 finally:os.close(fd)
else:
 with _operation_lock(ws):print('acquired')
''')
    env=dict(os.environ);env['PYTHONPATH']=os.environ['AUDIT_SOURCE']+os.pathsep+str(Path(__file__).parent)
    def run(action):return subprocess.run([sys.executable,str(script),str(ws),action],env=env,capture_output=True,text=True,timeout=10)
    with _operation_lock(ws):blocked=run('probe')
    acquired=run('acquire');assert blocked.returncode==acquired.returncode==0,(blocked.stderr,acquired.stderr)
    assert blocked.stdout.strip()=='blocked' and acquired.stdout.strip()=='acquired'
    finish(case,ev,{'order':['parent holds actual operation lock','child probes nonblocking flock','parent releases','child acquires actual lock'],'blocked':blocked.stdout,'acquired':acquired.stdout})
