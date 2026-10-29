"""F14: deterministic root leases, stale generations and real process deaths."""
from pathlib import Path
from contextlib import closing
import hashlib,json,os,signal,sqlite3,subprocess,sys,threading,time
import pytest
from app import root_operations as ro
from app import main
from app.library_context import resolve_library_context
from app.library_registry import initialize_library_registry,register_library,update_library_paths,ensure_library_identity,LibraryRegistryError
from app.database import initialize_database,database_connection
from app.storage_config import load_storage_settings,storage_paths


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();reg=case/'registry.sqlite3'
    monkeypatch.setenv('KAMERA_WORKSPACE',str(ws))
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(reg))
    (case/'settings.json').write_text('{}')
    # This fixture represents a known historical installation.
    from app.storage_config import LEGACY_STORAGE_DEFAULTS
    for name in LEGACY_STORAGE_DEFAULTS.values():(ws/name).mkdir(exist_ok=True)
    initialize_library_registry(reg)
    dbs=[]
    for lid in ['main','second']:
        db=case/(lid+'.sqlite3');initialize_database(db);ensure_library_identity(db,lid);dbs.append(db)
        work=storage_paths(ws)['workspaces_root']/lid;work.mkdir();archive=case/('archive-'+lid);archive.mkdir()
        (work/'original.JPG').write_bytes(b'synthetic-'+lid.encode())
        register_library(reg,library_id=lid,display_name=lid,database_path=db,workspace_root=ws,work_root=work,archive_root=archive,is_main=lid=='main')
    context=resolve_library_context(reg,'main')
    for key,value in {'WORKSPACE_PATH':ws,'DATABASE_FILE':dbs[0],'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':case/'settings.json','MAIN_LIBRARY_CONTEXT':context}.items():monkeypatch.setattr(main,key,value)
    ev=tmp_path/'f14-evidence';ev.mkdir()
    (case/'case.json').write_text(json.dumps({'db':str(dbs[0]),'workspace':str(ws),'kind':'trash','job':'synthetic-no-job','databases':list(map(str,dbs)),'expected':{'main':hashlib.sha256(b'synthetic-main').hexdigest(),'second':hashlib.sha256(b'synthetic-second').hexdigest()}}))
    return case,ws,reg,dbs,ev


def snapshot(case,path):
    files=[];dbs={}
    for p in sorted(case.rglob('*')):
        if p.is_symlink():files.append({'path':str(p.relative_to(case)),'link':os.readlink(p)});continue
        if not p.is_file():continue
        files.append({'path':str(p.relative_to(case)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'inode':p.stat().st_ino,'size':p.stat().st_size})
        if p.suffix=='.sqlite3':
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as c:
                c.row_factory=sqlite3.Row
                tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                dbs[str(p.relative_to(case))]={'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':[tuple(r) for r in c.execute('PRAGMA foreign_key_check')],'rows':{t:[dict(r) for r in c.execute('SELECT * FROM "'+t+'"')] for t in tables}}
    value={'files':files,'databases':dbs};path.write_text(json.dumps(value,indent=2,default=str));return value


def settings_change():
    settings=load_storage_settings();settings['workspaces_directory_name']='ChangedWork';return settings


def refuse_managed_change(payload):
    with pytest.raises(main.HTTPException) as exc:main.api_set_storage_paths(payload)
    assert exc.value.status_code==410


def rebind_archive(case,reg,library='main'):
    target=case/('rebound-'+library);target.mkdir()
    update_library_paths(reg,library,archive_root=target)
    return target


@pytest.mark.parametrize('kind',['import','sort','ssd','archive','inventory','recovery'])
def test_f14_active_operation_rejects_root_change(fixture,kind):
    case,ws,reg,dbs,ev=fixture;before=snapshot(case,ev/'before.json');reached=threading.Event();release=threading.Event();results=[]
    work=storage_paths(ws)['workspaces_root']/'main'
    def worker():
        try:
            with ro.reserve(ws,library_id='main',paths=[work],database=dbs[0],kind=kind):
                reached.set();assert release.wait(10)
            results.append('ok')
        except BaseException as e:results.append(repr(e))
    t=threading.Thread(target=worker);t.start();assert reached.wait(10)
    try:
        with pytest.raises(main.HTTPException) as exc:main.api_set_storage_paths(settings_change())
        assert exc.value.status_code==410
        assert work.joinpath('original.JPG').read_bytes()==b'synthetic-main'
        assert not (ws/'ChangedWork').exists()
    finally:release.set();t.join(10)
    assert not t.is_alive() and results==['ok']
    after=snapshot(case,ev/'after.json')
    for db in after['databases'].values():assert db['integrity']=='ok' and not db['foreign_keys']
    refuse_managed_change(settings_change())
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'after-success.json')


def test_f14_independent_library_change(fixture):
    case,ws,reg,dbs,ev=fixture
    new=case/'new-second';new.mkdir()
    with ro.reserve(ws,library_id='main',paths=[storage_paths(ws)['workspaces_root']/'main'],database=dbs[0],kind='import'):
        row=update_library_paths(reg,'second',work_root=new)
        assert row['work_root']==str(new)
        with pytest.raises(LibraryRegistryError):update_library_paths(reg,'main',work_root=new)
    snapshot(case,ev/'independent-library.json')
    assert ro.generation(ws,'second')==(0,1) and ro.generation(ws,'main')==(0,0)


def test_f14_stale_context_is_rejected_before_body(fixture):
    case,ws,reg,dbs,ev=fixture;old=resolve_library_context(reg,'main');seen=[]
    @ro.protect(context_provider=lambda a:a['library_context'])
    def operation(*,library_context):seen.append('mutated')
    rebind_archive(case,reg)
    with pytest.raises(ro.RootOperationError):operation(library_context=old)
    assert seen==[]
    operation(library_context=resolve_library_context(reg,'main'));assert seen==['mutated']
    snapshot(case,ev/'stale-context.json')


def test_f14_stale_generation_between_request_and_reservation(fixture):
    case,ws,reg,dbs,ev=fixture;expected=ro.generation(ws,'main')
    rebind_archive(case,reg)
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',expected_generation=expected):raise AssertionError('stale operation entered')
    snapshot(case,ev/'stale-generation.json')


@pytest.mark.parametrize('component',['workspace','work','archive'])
def test_f14_external_root_replacement_blocks_operation(fixture,component):
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main')
    root={'workspace':ws,'work':ctx.work_root,'archive':ctx.archive_root}[component]
    with ro.reserve(ws,library_id='main',paths=[ctx.work_root,ctx.archive_root],database=dbs[0]):pass
    original=root/'original.JPG'
    if not original.exists():original.write_bytes(b'synthetic-existing')
    before=hashlib.sha256(original.read_bytes()).hexdigest();old=root.with_name(root.name+'-manual');root.rename(old);root.mkdir();foreign=root/'original.JPG';foreign.write_bytes(b'synthetic-foreign')
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',paths=[ctx.work_root,ctx.archive_root],database=dbs[0]):foreign.unlink()
    assert foreign.read_bytes()==b'synthetic-foreign'
    assert hashlib.sha256((old/'original.JPG').read_bytes()).hexdigest()==before
    snapshot(case,ev/'external-replacement.json')


def test_f14_manual_file_edits_remain_allowed(fixture):
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main')
    with ro.reserve(ws,library_id='main',paths=[ctx.work_root],database=dbs[0]):
        p=ctx.work_root/'original.JPG';p.write_bytes(b'external-editor-new-bytes');p.rename(p.with_name('renamed.JPG'));ro.validate_active_roots()
    assert ro.generation(ws,'main')==(0,0)
    refuse_managed_change(settings_change())
    assert (ws/'Arbeitsbereiche/main/renamed.JPG').read_bytes()==b'external-editor-new-bytes'
    snapshot(case,ev/'manual-file-edit.json')


@pytest.mark.parametrize('directory',['.trash-restores','.trash-deletions','.swap-journals'])
def test_f14_unknown_journal_blocks_without_cleanup(fixture,directory):
    case,ws,reg,dbs,ev=fixture;parent=storage_paths(ws)['metadata_root']/directory;parent.mkdir();journal=parent/'synthetic.json';raw=b'{"unknown":"preserve"}';journal.write_bytes(raw)
    for n in (1,2,3):
        with pytest.raises(main.HTTPException):main.api_set_storage_paths(settings_change())
        assert journal.read_bytes()==raw
    assert (storage_paths(ws)['workspaces_root']/'main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'unknown-journal.json')


def spawn(case,ws,reg,ev,action):
    control=ev/action;control.mkdir()
    log=(control/'process.log').open('w')
    env=dict(os.environ,KAMERA_CONFIG=str(case/'settings.json'),KAMERA_REGISTRY_DATABASE=str(reg),PYTHONDONTWRITEBYTECODE='1')
    worker=Path(__file__).with_name('f14_root_worker.py')
    process=subprocess.Popen([sys.executable,str(worker),str(ws),str(control),action],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    deadline=time.monotonic()+15
    while process.poll() is None and time.monotonic()<deadline:
        if (control/'checkpoint.json').exists():
            # The worker creates then writes/fsyncs this test marker. Existence
            # alone can expose an empty/partial JSON document to the controller.
            try: json.loads((control/'checkpoint.json').read_text())
            except json.JSONDecodeError: pass
            else: return process,control,log
        time.sleep(.01)
    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
    log.close();raise AssertionError((control/'process.log').read_text())


@pytest.mark.parametrize('action',['reserve','mutation-intent','mutation-after-rename','mutation-after-state'])
def test_f14_true_sigkill_preserves_reservation_and_blocks_changes(fixture,action):
    case,ws,reg,dbs,ev=fixture;before=snapshot(case,ev/'before-kill.json')
    process,control,log=spawn(case,ws,reg,ev,action)
    try:
        assert json.loads((control/'checkpoint.json').read_text())['pid']==process.pid
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10);assert process.returncode==-9
    finally:log.close()
    parent=ro._control_location(ws)
    for n in (1,2,3):
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('f14_root_worker.py')),str(ws),str(ev), 'probe'],env=dict(os.environ,KAMERA_REGISTRY_DATABASE=str(reg)),capture_output=True,text=True,timeout=15)
        assert result.returncode==3,result.stdout+result.stderr
        from tests.backend import test_0562_process_recovery as recovery
        # The unchanged real application-start worker is used, not just a guard
        # simulation. A root intent blocks startup; an unrelated orphan lease
        # keeps ordinary startup possible while refusing subsequent root changes.
        monkey_env=dict(AUDIT_SCRATCH=str(case.parent),AUDIT_SOURCE=str(Path(__file__).resolve().parents[2]),AUDIT_OUTPUT=str(ev),AUDIT_LABEL='f14-real-start')
        saved={k:os.environ.get(k) for k in monkey_env};os.environ.update(monkey_env)
        try:start=recovery.invoke(case,'startup','none',ev/f'full-application-start{n}')
        finally:
            for k,v in saved.items():
                if v is None:os.environ.pop(k,None)
                else:os.environ[k]=v
        assert (start['returncode']==0)==(action=='reserve'),start
        snapshot(case,ev/f'after-restart{n}.json')
    assert list(parent.glob('operation-*.json')) if action=='reserve' else (parent/'mutation.json').exists()
    originals=list(ws.rglob('original.JPG'));assert len(originals)==2
    assert sorted(p.read_bytes() for p in originals)==[b'synthetic-main',b'synthetic-second']


def test_f14_private_control_access_and_unknown_content(fixture):
    case,ws,reg,dbs,ev=fixture
    with ro.reserve(ws):pass
    parent=ro._control_location(ws);assert parent.stat().st_mode&0o077==0
    assert not parent.is_relative_to(ws)
    (parent/'state.json').write_text('{broken')
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws):raise AssertionError('corrupt state accepted')
    assert (parent/'state.json').read_text()=='{broken'


def test_f14_double_http_change_has_no_second_effect(fixture):
    case,ws,reg,dbs,ev=fixture;payload=settings_change()
    snapshot(case,ev/'reader-warmup.json');g=ro.generation(ws,'main')
    before=snapshot(case,ev/'before-requests.json')
    refuse_managed_change(payload);refuse_managed_change(payload)
    assert ro.generation(ws,'main')==g
    assert snapshot(case,ev/'after-requests.json')==before
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'double-request.json')


def test_f14_two_independent_real_worker_processes(fixture):
    case,ws,reg,dbs,ev=fixture;processes=[]
    for lid in ['main','second']:(ws/('staged-'+lid+'.JPG')).write_bytes(b'transfer-'+lid.encode())
    try:
        for lid in ['main','second']:processes.append(spawn(case,ws,reg,ev,'reserve-live-'+lid))
        with pytest.raises(main.HTTPException):main.api_set_storage_paths(settings_change())
        snapshot(case,ev/'two-workers-reserved.json')
        for process,control,log in processes:(control/'continue').write_text('continue')
        for process,control,log in processes:
            process.wait(timeout=10);assert process.returncode==0,(control/'process.log').read_text()
        for lid in ['main','second']:
            assert (storage_paths(ws)['workspaces_root']/lid/'moved.JPG').read_bytes()==b'transfer-'+lid.encode()
            assert not (ws/('staged-'+lid+'.JPG')).exists()
        refuse_managed_change(settings_change());snapshot(case,ev/'two-workers-completed.json')
    finally:
        for process,control,log in processes:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
            log.close()


def test_f14_duplicate_real_worker_is_rejected(fixture):
    case,ws,reg,dbs,ev=fixture;(ws/'staged-main.JPG').write_bytes(b'only-one-transfer')
    process,control,log=spawn(case,ws,reg,ev,'reserve-live-main');second=ev/'second-worker';second.mkdir()
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('f14_root_worker.py')),str(ws),str(second),'reserve-live-main'],capture_output=True,text=True,timeout=10)
        assert issubclass(ro.RootOperationBusy, ro.RootOperationError)
        assert result.returncode!=0 and 'app.root_operations.RootOperationBusy:' in result.stderr
        assert not (second/'checkpoint.json').exists()
        (second/'result.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2))
        assert (ws/'staged-main.JPG').read_bytes()==b'only-one-transfer'
        (control/'continue').write_text('continue');process.wait(timeout=10);assert process.returncode==0
        assert (storage_paths(ws)['workspaces_root']/'main/moved.JPG').read_bytes()==b'only-one-transfer'
        snapshot(case,ev/'one-transfer-completed.json')
    finally:
        if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
        log.close()
