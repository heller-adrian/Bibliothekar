"""RC4 practice: isolated failure evidence and presentation regressions."""
import hashlib,json
from pathlib import Path
import pytest
from app import main,trash_import as ti,trash_failure as tf
from app.database import database_connection,claim_next_job,get_job
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot
from tests.backend.test_rc4_nas_legacy import failed_restore
from tests.backend.test_rc1_sd_reimport import direct_import_lifecycle


def test_fresh_unknown_restore_failure_evidence(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture
    root=storage_paths(ws)['trash_root']
    for ext in ['JPG','RAF']:(root/('unknown.'+ext)).write_bytes(('original '+ext).encode())
    queued=ti.queue_trash_restore(dbs[0],ws,['unknown.JPG','unknown.RAF'])
    monkeypatch.setattr(main,'LOG_PATH',case/'logs')
    monkeypatch.setattr(main,'POOL_PROBE_PATH',ws)
    import app.folder_import as fi
    def fail_before_media(*a,**kw):raise fi.PipelineError('Synthetic source preflight failure')
    monkeypatch.setattr(fi,'preflight_folder_import',fail_before_media)
    job=claim_next_job(dbs[0]);assert job['id']==queued['job_id']
    main.process_claimed_job(job,library_context=main.MAIN_LIBRARY_CONTEXT)
    result=get_job(dbs[0],job['id'])
    (ev/'job.json').write_text(json.dumps(result,indent=2))
    snapshot(case,ev/'after.json')
    assert result['state']=='failed',result
    assert not ti.protected_trash_paths(None,ws)
    assert tf.validate_finalized(None,ws,job['id'])
    assert result['error_message']=='Synthetic source preflight failure'
    incoming=storage_paths(ws)['backup_root']/'.incoming'/job['id']
    assert incoming.is_dir()
    data=tf.read_journal(ws,job['id'])
    for item in data['files']:
        assert hashlib.sha256((ti.stage_parent(ws)/job['id']/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
    assert all((root/('unknown.'+ext)).read_bytes()==('original '+ext).encode() for ext in ['JPG','RAF'])


def protocol_failure(fixture):
    db,ws,jid,journal,data=failed_restore(fixture)
    incoming=storage_paths(ws)['backup_root']/'.incoming'/jid
    protocol=incoming/'Protocol';protocol.mkdir(parents=True)
    status=protocol/'status.json'
    status.write_text(json.dumps({'schema_version':3,'job_id':jid,'state':'failed','stage':'failed',
        'simulation':False,'import_mode':'folder','source_path':str(ti.stage_parent(ws)/jid),
        'lifecycle':{'temporary_backup':str(incoming/'Original'),'central_stock':str(incoming.parent.parent)}}))
    return db,ws,jid,journal,data,incoming,status


@pytest.mark.parametrize('conflict',['photo','move-journal','other-job','other-source','success','manifest','symlink','hardlink','writable','catalogue','partition','active','corrupt-copy'])
def test_protocol_residue_is_not_a_blanket_release(fixture,conflict):
    import os
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    if conflict=='photo':(incoming/'Original').mkdir();(incoming/'Original/A.JPG').write_bytes(b'partial')
    if conflict=='move-journal':(incoming/'move-journal.json').write_text('{}')
    if conflict=='manifest':(status.parent/'manifest.json').write_text('{}')
    if conflict in ('other-job','other-source','success'):
        value=json.loads(status.read_text());value[{'other-job':'job_id','other-source':'source_path','success':'state'}[conflict]]='foreign';status.write_text(json.dumps(value))
    if conflict=='symlink':status.rename(status.with_name('kept'));status.symlink_to(status.with_name('kept'))
    if conflict=='hardlink':os.link(status,status.with_name('alias'))
    if conflict=='writable':status.chmod(0o666)
    if conflict=='catalogue':
        with database_connection(db) as c:c.execute('INSERT INTO file_families(job_id,family_key) VALUES (?,?)',(jid,'partial'))
    if conflict=='partition':data['files'].pop();journal.write_text(json.dumps(data))
    if conflict=='active':
        with database_connection(db) as c:c.execute("UPDATE jobs SET state='copying' WHERE id=?",(jid,))
    if conflict=='corrupt-copy':(ti.stage_parent(ws)/jid/data['relative_paths'][0]).write_bytes(b'changed')
    raw=journal.read_bytes();tf.recover_failed_restores(db,ws)
    assert journal.read_bytes()==raw and ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    assert all((storage_paths(ws)['trash_root']/r['relative_path']).read_bytes()==('original '+Path(r['relative_path']).suffix[1:]).encode() for r in data['files'])


def test_protocol_completion_revalidates_retained_evidence(fixture):
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    original=status.read_bytes();assert tf.recover_failed_restores(db,ws)[0]['status']=='finalized'
    assert status.read_bytes()==original and not ti.protected_trash_paths(None,ws)
    (incoming/'unexpected.JPG').write_bytes(b'foreign')
    assert ti.protected_trash_paths(None,ws)==set(data['relative_paths'])
    with database_connection(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()

@pytest.mark.parametrize('language',['de','en'])
def test_new_source_labels_are_canonical_and_old_references_stay(fixture,monkeypatch,language):
    monkeypatch.setenv('BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE',language)
    org={'devices':[{'name':'camera A'},{'name':'camera B'}],'capture_start_date':'2026-07-19','capture_end_date':'2026-10-01'}
    label=main.folder_import_display_label({'trigger_type':'approved_sd','source_volume_label':'unchanged device'},org)
    assert label=='Multiple cameras - 2026.07.19 - 2026.10.01'
    custom='Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01'
    assert main.folder_import_display_label({'trigger_type':'manual','source_volume_label':custom},org)==custom
    db=fixture[3][0]
    from app.database import create_job
    create_job(db,job_id='HISTORY',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path='/synthetic/card',source_volume_label=custom,source_device_id='unchanged-device-id')
    assert get_job(db,'HISTORY')['source_volume_label']==custom
    assert get_job(db,'HISTORY')['source_device_id']=='unchanged-device-id'


def test_single_diagnostic_view_and_new_visible_messages(tmp_path):
    from tests.backend.rc4_locale_probe import assert_technical_presentation
    from tests.backend.test_rc3_mobile import node
    from app.ui_i18n import I18N_UI_JS
    assert_technical_presentation(main.index(),tmp_path)
    prefix="""globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Trash',readyState:'loading',documentElement:{dataset:{bkLocale:'en'}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};globalThis.CustomEvent=function(){};
"""
    node(tmp_path,prefix+I18N_UI_JS+"""
const t=window.BibliothekarI18n.t;
if(t('36/36 verwaltete Dateien bestätigt.')!=='36/36 managed files verified.')throw Error('counter');
const path='/workspace/SD Card Backups/.incoming/TRASH_IMPORT_X';
if(t('Ungeklärter Import-Zwischenbestand bleibt erhalten: '+path)!=='Unresolved intermediate import data is retained: '+path)throw Error('path/prefix');
window.BibliothekarI18n.setLocale('de');if(t('36/36 verwaltete Dateien bestätigt.')!=='36/36 verwaltete Dateien bestätigt.')throw Error('German counter');
""")


@pytest.mark.parametrize('boundary',['journal_prepared','before_db_commit','db_committed','journal_committed'])
def test_automatic_protocol_failure_sigkill_and_startup(fixture,tmp_path,boundary):
    import subprocess,sys,time,signal
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    with database_connection(db) as c:error=c.execute('SELECT error_message FROM jobs WHERE id=?',(jid,)).fetchone()[0]
    case=tmp_path/'failure.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'job_id':jid,'error':error}))
    marker=tmp_path/'checkpoint';worker=Path(__file__).parents[2]/'qa/rc4-practice/failure_worker.py'
    p=subprocess.Popen([sys.executable,'-B',str(worker),str(case),boundary,str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+20
    while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not marker.exists():
        p.kill();out,err=p.communicate(timeout=5);pytest.fail(out+err)
    p.kill();out,err=p.communicate(timeout=5);assert p.returncode==-signal.SIGKILL
    (tmp_path/'killed.log').write_text(out+err)
    assert bool(ti.protected_trash_paths(None,ws)) is (boundary!='journal_committed')
    statuses=[]
    for n in range(3):
        r=subprocess.run([sys.executable,'-B',str(worker),str(case),'none',str(marker)],capture_output=True,text=True,timeout=30)
        (tmp_path/f'restart{n}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
        assert json.loads(r.stdout)['audit_count']==1
        statuses.append(journal.read_bytes())
        for item in data['files']:
            assert hashlib.sha256((storage_paths(ws)['trash_root']/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
            assert hashlib.sha256((ti.stage_parent(ws)/jid/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
        snapshot(fixture[0],tmp_path/f'start{n}.json')
    assert statuses[0]==statuses[1]==statuses[2] and status.exists()


def test_browser_bundle(tmp_path):
    import os
    from tests.backend.test_rc3_mobile import test_r03_r04_browser_bundle_and_css
    from app.ui_shell import apply_shell,BIBLIOTHEKAR_JS,BIBLIOTHEKAR_0444_JS
    from app.trash_ui import TRASH_HTML
    test_r03_r04_browser_bundle_and_css(tmp_path)
    target=Path(os.environ.get('AUDIT_OUTPUT',str(tmp_path)))/'browser-bundle.json'
    bundle=json.loads(target.read_text())
    bundle['shellImport']=apply_shell(main.index(),active_area='import')
    start=BIBLIOTHEKAR_JS.index('  const bkTitleHelpTriggers =')
    bundle['titleHelp']=BIBLIOTHEKAR_JS[start:BIBLIOTHEKAR_JS.index('  const currentLibraryName =',start)]
    start=TRASH_HTML.index('  function renderRestoreFailures(')
    bundle['failureRender']=TRASH_HTML[start:TRASH_HTML.index('  function render(data)',start)]
    bundle['trash']=apply_shell(TRASH_HTML,active_area='trash')
    target.write_text(json.dumps(bundle))


def test_sd_activity_only_in_dock_and_local_notice(tmp_path):
    from app.ui_shell import BIBLIOTHEKAR_0444_JS as code
    from tests.backend.test_rc3_mobile import node
    start=code.index('  function renderPageActivity(');end=code.index('  box.append',start)
    node(tmp_path,"""const location={pathname:'/'};
const pageActivity={hidden:false,replaceChildren(...xs){this.children=xs}},destination=v=>v.kind==='trash_restore'?'/trash':'/';
const makeItem=v=>v,dismissedPageActivities=new Set(),window={};
const document={createElement(){return {setAttribute(){},addEventListener(){}}}};
"""+code[start:end]+"""
const records=[{id:'old',kind:'sd_check',status:'completed'},{id:'new',kind:'sd_check',status:'queued'}];
const raw=JSON.stringify(records);renderPageActivity(records);
if(!pageActivity.hidden||pageActivity.children.length||raw!==JSON.stringify(records))throw Error('duplicate banner or modified history');
location.pathname='/trash';renderPageActivity([{id:'t',kind:'trash_restore'}]);
if(!pageActivity.hidden||pageActivity.children.length)throw Error('duplicate trash banner');
location.pathname='/';renderPageActivity([{id:'i',kind:'import'}]);
if(pageActivity.hidden||pageActivity.children.filter(v=>v.id==='i').length!==1||pageActivity.children[0].className!=='bk-page-activity-dismiss')throw Error('unrelated task visibility changed');
""")


@pytest.mark.parametrize('language',['en','de'])
def test_first_real_sd_import_persists_english_generated_label(fixture,monkeypatch,language):
    import subprocess
    from PIL import Image
    from tests.backend.test_rc1_sd_reimport import setup_live_import,queue_and_run
    monkeypatch.setenv('BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE',language)
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    second=source.with_name('B.JPG');Image.new('RGB',(8,8),'blue').save(second)
    for path,model in [(source,'Camera A'),(second,'Camera B')]:
        subprocess.run(['exiftool','-overwrite_original','-Make=Synthetic','-Model='+model,'-DateTimeOriginal=2026:07:22 10:14:04',str(path)],check=True,capture_output=True)
    originals={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,second]}
    result=queue_and_run(dbs[0],context)
    assert result['source_volume_label'].startswith('Multiple cameras - '),result['source_volume_label']
    assert result['source_device_id']=='CARD'
    assert main.api_import_history()['total']==1
    for path in [source,second]:assert hashlib.sha256(path.read_bytes()).hexdigest()==originals[path.name]
    with database_connection(dbs[0]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


def test_generated_label_display_preserves_history_and_raw(tmp_path):
    from tests.backend.test_rc3_mobile import node
    html=main.index();a=html.index('    function importSourceLabel(');b=html.index('    function renderJob(',a)
    node(tmp_path,"""const document={documentElement:{dataset:{bkLocale:'de'}}},bk0511ImportLabel=(de,en)=>de;
"""+html[a:b]+"""
const job={trigger_type:'approved_sd',source_volume_label:'Multiple cameras - 2026.07.19 - 2026.10.01',result:{organization:{devices:[{},{}],capture_start_date:'2026-07-19',capture_end_date:'2026-10-01'}}};
const raw=JSON.stringify(job);
if(importSourceLabel(job)!=='Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01')throw Error('German generated label');
if(JSON.stringify(job)!==raw)throw Error('persisted label mutated');
job.source_volume_label='Mehrere Aufnahmegeräte - historical';if(importSourceLabel(job)!==job.source_volume_label)throw Error('historical label changed');
document.documentElement.dataset.bkLocale='en';if(importSourceLabel(job)!==job.source_volume_label)throw Error('historical label translated');
""")


def test_two_processes_finalize_once(fixture,tmp_path):
    import subprocess,sys
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    with database_connection(db) as c:error=c.execute('SELECT error_message FROM jobs WHERE id=?',(jid,)).fetchone()[0]
    case=tmp_path/'parallel.json';case.write_text(json.dumps({'db':str(db),'workspace':str(ws),'job_id':jid,'error':error}))
    worker=Path(__file__).parents[2]/'qa/rc4-practice/failure_worker.py'
    from app import root_operations as ro
    # A running application has already initialized its protected root context.
    with ro.reserve(ws,library_id='main',database=db,kind='trash'):pass
    marker=tmp_path/'release'
    cmd=[sys.executable,'-B',str(worker),str(case),'recover',str(marker)]
    processes=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    import time
    deadline=time.monotonic()+15
    while not all(Path(str(marker)+'.'+str(p.pid)).exists() for p in processes) and time.monotonic()<deadline:time.sleep(.02)
    assert all(Path(str(marker)+'.'+str(p.pid)).exists() for p in processes)
    marker.write_text('release both initialized processes')
    results=[]
    for n,p in enumerate(processes):
        out,err=p.communicate(timeout=30);(tmp_path/f'parallel{n}.log').write_text(out+err)
        assert p.returncode==0,out+err
        value=json.loads(out);results.append(value['result'])
        if value['result']['status']=='finalized':assert value['audit_count']==1
        else:assert value['result']['message']=='Ein anderer Vorgang verwendet diesen Bereich. Bitte kurz warten und erneut versuchen.'
    assert any(r['status']=='finalized' for r in results)
    with database_connection(db) as c:assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]==1
    assert tf.validate_finalized(None,ws,jid) and not ti.protected_trash_paths(None,ws)
    for r in data['files']:assert hashlib.sha256((storage_paths(ws)['trash_root']/r['relative_path']).read_bytes()).hexdigest()==r['sha256']


@pytest.mark.parametrize('value',[[],{},'invalid',{'lifecycle':[]}])
def test_malformed_protocol_blocks_without_global_start_error(fixture,value):
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    status.write_text(json.dumps(value));raw=journal.read_bytes()
    assert tf.recover_failed_restores(db,ws)[0]['status']=='blocked'
    assert journal.read_bytes()==raw and ti.protected_trash_paths(None,ws)
