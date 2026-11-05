"""RC4 queue/control tests; small synthetic media, no NAS or real SD devices."""
import hashlib,json,uuid,time,threading,subprocess,sys,os,signal
from pathlib import Path
import pytest
from app import main,sd_recheck as sr
from app.database import database_connection,claim_next_job,get_job,mark_running_jobs_interrupted
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc1_sd_reimport import direct_import_lifecycle,setup_live_import,queue_and_run

@pytest.fixture
def sd(fixture,monkeypatch):
    data=setup_live_import(fixture,monkeypatch)
    case,ws,reg,dbs,source,context=data
    queue_and_run(dbs[0],context)
    return data

def request(token=None):
    response=main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':True,'request_id':token})
    assert response.status_code==202
    return json.loads(response.body)

def process(sd):
    case,ws,reg,dbs,source,context=sd
    job=claim_next_job(dbs[0]);assert job
    main.process_claimed_job(job,library_context=context)
    return get_job(dbs[0],job['id'])

def sql_ok(db):
    with database_connection(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()


def test_complete_no_empty_import_history_and_idempotent_post(sd):
    case,ws,reg,dbs,source,context=sd
    before=source.read_bytes();total=main.api_import_history()['total'];token=str(uuid.uuid4())
    a=request(token);assert request(token)['task_id']==a['task_id']
    done=process(sd);assert done['operation']=='sd_recheck' and done['state']=='completed',done
    assert done['result']['status']=='already_backed_up'
    assert request(token)['task_id']==done['id']
    assert claim_next_job(dbs[0]) is None
    assert main.api_import_history()['total']==total
    assert all(j['operation']!='sd_recheck' for j in main.api_jobs()['jobs'])
    activities=main.api_background_activity()['operations'];assert any(a['id']==done['id'] and a['kind']=='sd_check' and a['status']=='completed' for a in activities)
    main.api_clear_background_activity()
    assert all(a['id']!=done['id'] for a in main.api_background_activity()['operations'])
    assert source.read_bytes()==before;sql_ok(dbs[0])


@pytest.mark.parametrize('mode',['missing','added'])
def test_supplement_real_worker_keeps_original_and_one_child(sd,monkeypatch,mode):
    case,ws,reg,dbs,source,context=sd;original=source.read_bytes()
    if mode=='missing':
        with database_connection(dbs[0]) as c:rel=c.execute('SELECT current_relative_path FROM files LIMIT 1').fetchone()[0]
        target=storage_paths(ws)['backup_root']/rel;target.unlink()
    else:
        from PIL import Image
        new=source.with_name('new.JPG');Image.new('RGB',(8,8),'blue').save(new)
        subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:07:23 10:14:04',str(new)],check=True,capture_output=True)
    token=str(uuid.uuid4());queued=request(token)
    parent=process(sd);assert parent['state']=='completed',parent
    assert parent['result']['status']=='import_queued';child_id=parent['result']['import_job_id']
    assert request(token)['task_id']==queued['task_id']
    child=process(sd);assert child['id']==child_id and child['state']=='completed',child
    assert child['result']['organization']['file_count']==1
    assert child['result']['source']['duplicate_file_count']==(1 if mode=='added' else 0)
    if mode=='missing':assert target.read_bytes()==original
    assert source.read_bytes()==original
    assert claim_next_job(dbs[0]) is None;sql_ok(dbs[0])


def test_parallel_requests_share_one_check(sd):
    barrier=threading.Barrier(5);rows=[];errors=[]
    def click():
        try:barrier.wait(10);rows.append(request(str(uuid.uuid4()))['task_id'])
        except BaseException as e:errors.append(repr(e))
    threads=[threading.Thread(target=click) for _ in range(4)]
    for t in threads:t.start()
    barrier.wait(10)
    for t in threads:t.join(10);assert not t.is_alive()
    assert not errors,errors
    assert len(set(rows))==1
    assert process(sd)['state']=='completed'
    assert claim_next_job(sd[3][0]) is None


@pytest.mark.parametrize('conflict',['corrupt','read-write','replaced'])
def test_conflict_keeps_all_bytes_and_no_child(sd,monkeypatch,conflict):
    case,ws,reg,dbs,source,context=sd;original=source.read_bytes();a=request()
    with database_connection(dbs[0]) as c:rel=c.execute('SELECT current_relative_path FROM files LIMIT 1').fetchone()[0]
    target=storage_paths(ws)['backup_root']/rel
    if conflict=='corrupt':target.write_bytes(b'externally damaged')
    if conflict=='read-write':monkeypatch.setattr(sr,'read_only',lambda p:False)
    if conflict=='replaced':
        card=source.parent;card.rename(card.with_name('OLD'));card.mkdir();(card/source.name).write_bytes(original)
    kept=target.read_bytes();done=process(sd)
    assert done['state']=='failed',done
    assert target.read_bytes()==kept and source.read_bytes()==original
    assert claim_next_job(dbs[0]) is None
    assert main.api_import_history()['total']==1;sql_ok(dbs[0])


def test_5_5_gib_http_returns_before_hash_and_progress_persists(sd,monkeypatch):
    case,ws,reg,dbs,source,context=sd
    actual=sr.source_manifest;called=[];size=int(5.5*1024**3)
    def forbidden(*a,**kw):raise AssertionError('HTTP must never hash source')
    monkeypatch.setattr(sr,'source_manifest',forbidden)
    start=time.monotonic();queued=request();latency=time.monotonic()-start;assert latency<1.5
    # Logical hash workload only: same real SHA as the tiny source; no 5.5GiB copy.
    rows=actual(source.parent);rows[0]['size_bytes']=size
    progress=[]
    def modeled(*a,**kw):
        for n in range(1,12):
            kw['cancellation_callback']();kw['bytes_progress_callback'](min(size,n*512*1024**2),size)
            progress.append(get_job(dbs[0],queued['task_id'])['progress_current'])
        called.append(True);return rows
    monkeypatch.setattr(sr,'source_manifest',modeled)
    import app.sd_recheck
    clock=[0.0]
    def tick():clock[0]+=2;return clock[0]
    monkeypatch.setattr(app.sd_recheck.time,'monotonic',tick)
    done=process(sd);assert done['state']=='completed',done
    assert called and max(progress)>=500 and progress==sorted(progress)
    assert done['result']['source_size_bytes']==size
    assert done['progress_current']==done['progress_total']==1000
    (case/'model-metrics.json').write_text(json.dumps({'logical_bytes':size,'http_seconds':latency,'progress':progress,'physical_source_bytes':source.stat().st_size}))


def child(sd,mode,point,evidence):
    case,ws,reg,dbs,source,context=sd
    (case/'sd-case.json').write_text(json.dumps({'database':str(dbs[0]),'working':str(storage_paths(ws)['backup_root'])}))
    env=dict(os.environ,KAMERA_CONFIG=str(case/'settings.json'),KAMERA_WORKSPACE=str(ws),
             KAMERA_REGISTRY_DATABASE=str(reg),KAMERA_DATABASE_DIR=str(case),
             KAMERA_LOG_DIR=str(case/'logs'),KAMERA_REMOVABLE_ROOT=str(case/'removable'),
             KAMERA_POOL_PROBE=str(ws),KAMERA_ARCHIVE_ROOT=str(context.archive_root))
    cmd=[sys.executable,'-B',str(Path(__file__).parents[2]/'qa/rc4/sd_worker.py'),str(case),mode,point,str(evidence)]
    return subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def test_two_processes_share_one_persistent_check(sd,tmp_path):
    a=child(sd,'enqueue','none',tmp_path/'a');b=child(sd,'enqueue','none',tmp_path/'b')
    ar,ae=a.communicate(timeout=20);br,be=b.communicate(timeout=20)
    assert a.returncode==b.returncode==0,(ae,be)
    assert json.loads(ar)['id']==json.loads(br)['id']
    assert process(sd)['state']=='completed'


@pytest.mark.parametrize('point',['hash','handoff','after_handoff'])
def test_sigkill_real_startup_and_three_independent_restarts(sd,tmp_path,point):
    case,ws,reg,dbs,source,context=sd;original=source.read_bytes()
    with database_connection(dbs[0]) as c:rel=c.execute('SELECT current_relative_path FROM files LIMIT 1').fetchone()[0]
    target=storage_paths(ws)['backup_root']/rel
    if point!='hash':
        # Model a previously archived and released original. Legacy shared-work
        # projections without either copy intentionally block startup migration.
        archived=context.archive_root/rel;archived.parent.mkdir(parents=True,exist_ok=True)
        target.rename(archived)
        for db in dbs:
            with database_connection(db) as c:c.execute("UPDATE files SET current_root_kind='camera_archive'")
        archived.unlink()  # Controlled synthetic archive loss; SD original stays.
    snapshot(case,tmp_path/'before.json')
    queued=request();evidence=tmp_path/'kill'
    process_=child(sd,'operate',point,evidence)
    deadline=time.monotonic()+20
    while not (evidence/'reached').exists() and process_.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not (evidence/'reached').exists():
        stdout,stderr=process_.communicate(timeout=2);pytest.fail(stdout+stderr)
    process_.kill();stdout,stderr=process_.communicate(timeout=5)
    assert process_.returncode==-signal.SIGKILL
    (tmp_path/'kill.log').write_text(stdout+stderr)
    snapshot(case,tmp_path/'after-kill.json')
    with database_connection(dbs[0]) as c:
        children=c.execute("SELECT id FROM jobs WHERE id LIKE 'FOLDER_IMPORT_SD_RECHECK_%'").fetchall()
        assert len(children)==(1 if point=='after_handoff' else 0)
    for n in range(3):
        restarted=child(sd,'restart','none',tmp_path/f'restart{n}')
        stdout,stderr=restarted.communicate(timeout=30)
        (tmp_path/f'restart{n}.log').write_text(stdout+stderr)
        assert restarted.returncode==0,stdout+stderr
        assert source.read_bytes()==original;sql_ok(dbs[0])
        snapshot(case,tmp_path/f'after-restart{n}.json')
    done=get_job(dbs[0],queued['task_id']);assert done['state']=='completed',done
    with database_connection(dbs[0]) as c:
        children=c.execute("SELECT id,state FROM jobs WHERE id LIKE 'FOLDER_IMPORT_SD_RECHECK_%'").fetchall()
    assert len(children)==(0 if point=='hash' else 1)
    if children:
        assert children[0]['state']=='completed'
        assert target.read_bytes()==original
    assert main.api_import_history()['total']==(1 if point=='hash' else 2)


def test_browser_disconnect_after_202_does_not_cancel_or_duplicate(sd):
    from fastapi.testclient import TestClient
    token=str(uuid.uuid4());payload={'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':True,'request_id':token}
    client=TestClient(main.app)  # No lifespan; the fixture schedules the worker.
    response=client.post('/api/jobs/folder-import',json=payload);assert response.status_code==202
    task_id=response.json()['task_id'];client.close()
    done=process(sd);assert done['id']==task_id and done['state']=='completed'
    replacement=TestClient(main.app)
    assert replacement.get('/api/sd-rechecks/'+task_id).json()['result']['status']=='already_backed_up'
    assert replacement.post('/api/jobs/folder-import',json=payload).json()['task_id']==task_id
    replacement.close()
    assert claim_next_job(sd[3][0]) is None


def test_ui_persists_request_before_post_and_resumes_polling(tmp_path):
    from tests.backend.test_rc3_mobile import node
    html=main.index()
    start=html.index('    const sdRecheckTasks =');end=html.index('    refreshButton.addEventListener',start)
    script=r'''
const store={},timers=[],posts=[];let task={state:'verifying',progress_current:250,progress_total:1000,progress_message:'Checking'};
const localStorage={getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]};
const noticeElement={textContent:'',classList:{toggle(){},add(){},remove(){}}};
const folderImportButton={},sdImportButton={},deviceImportButton={},driveFolderImportButton={};
const window={dispatchEvent(){}},crypto={getRandomValues:bytes=>{bytes.fill(0);bytes[15]=1;return bytes}};
const bk0511ImportLabel=(de,en)=>en,importUiText=v=>v;
const loadJobs=async()=>{},loadSourceDevices=async()=>{},updateDriveControls=()=>{},currentFolderPath='CARD';
const setTimeout=f=>timers.push(f);
let drop=true;
const fetch=async(url,options)=>{
 if(options){const payload=JSON.parse(options.body);posts.push(payload);
  if(!store['bk-sd-recheck:CARD'])throw Error('identity was not persisted before POST');
  if(drop){drop=false;throw Error('browser connection closed after request');}
  return {ok:true,json:async()=>({status:'sd_check',accepted:true,task_id:'SD_RECHECK_00000000000040008000000000000001'})};
 }
 return {ok:true,status:200,json:async()=>task};
};
''' + html[start:end] + r'''
(async()=>{
 await startFolderImportSelection('removable','CARD','SD Card','sd_card',true);
 await startFolderImportSelection('removable','CARD','SD Card','sd_card',true);
 if(posts.length!==2||posts[0].request_id.replaceAll('-','')!==posts[1].request_id.replaceAll('-',''))throw Error('lost-response retry changed identity');
 await new Promise(resolve=>setImmediate(resolve));
 if(!noticeElement.textContent.includes('25%')||sdRecheckTasks.size!==1)throw Error('progress missing');
 // Model a reloaded page: storage survives, in-memory task map/timers do not.
 sdRecheckTasks.clear();timers.length=0;
 const saved=store['bk-sd-recheck:CARD'];
 // Enumerating real Storage exposes keys; use the saved record directly here.
 await followSdRecheck(saved,'CARD');
 if(sdRecheckTasks.size!==1||timers.length!==1)throw Error('resume missing');
 task={state:'completed',progress_current:1000,progress_total:1000,progress_message:'All recordings are already backed up.'};
 await timers.shift()();
 if(sdRecheckTasks.size||store['bk-sd-recheck:CARD']||!noticeElement.textContent.includes('already backed up'))throw Error('completion missing');
 // A failed task remains visible, and a deliberate next attempt gets a fresh identity.
 localStorage.setItem('bk-sd-recheck:CARD',saved);task={state:'failed',progress_current:12,progress_total:1000,error_message:'Copy damaged'};
 await followSdRecheck(saved,'CARD');if(noticeElement.textContent!=='Copy damaged')throw Error('failure hidden');
 if(store['bk-sd-recheck:CARD'])throw Error('retry blocked');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    node(tmp_path,script)
    assert 'resumeSdRechecks();' in html
    assert 'sdVerifyButton.addEventListener' not in html


def test_unconfirmed_direct_request_cannot_bypass_active_check(sd):
    task=request()
    response=main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card'})
    # The unconfirmed quick path can report the existing completed backup, but
    # must never enqueue a competing normal import while the check is active.
    assert response.status_code in (200,202)
    with database_connection(sd[3][0]) as c:
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]==1
    assert process(sd)['id']==task['task_id']


def test_real_mount_flag_is_required(monkeypatch,tmp_path):
    from types import SimpleNamespace
    # Exercise the production probe (other synthetic lifecycle tests explicitly
    # model RO). This is not a positive native Linux/TrueNAS mount proof.
    original=__import__('importlib').reload(sr).read_only
    monkeypatch.setattr(sr.os,'statvfs',lambda p:SimpleNamespace(f_flag=0))
    assert original(tmp_path) is False
    monkeypatch.setattr(sr.os,'statvfs',lambda p:SimpleNamespace(f_flag=os.ST_RDONLY))
    assert original(tmp_path) is True
