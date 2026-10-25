"""RC3 R01-R06: isolated source, language and responsive UI regressions."""
import hashlib,json,subprocess
from pathlib import Path
import pytest
from app import main
from app.database import database_connection,get_job,claim_next_job
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import direct_import_lifecycle,setup_live_import,queue_and_run


def backup_request(confirmed=False):
    return main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD',
        'source_mode':'sd_card','confirm_reimport':confirmed})


@pytest.mark.parametrize("where", ["workspace", "archive"])
def test_r01_complete_card_does_not_create_another_import(fixture,monkeypatch,where):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context)
    original=source.read_bytes()
    if where == 'archive':
        with database_connection(dbs[0]) as c:
            relative=c.execute('SELECT current_relative_path FROM files WHERE job_id=?',(first['id'],)).fetchone()[0]
        saved=storage_paths(ws)['backup_root']/relative
        archived=context.archive_root/relative;archived.parent.mkdir(parents=True,exist_ok=True);saved.rename(archived)
        for db in dbs:
            with database_connection(db) as c:c.execute("UPDATE files SET current_root_kind='camera_archive' WHERE job_id=?",(first['id'],))
        assert archived.read_bytes()==original and not saved.exists()
    with database_connection(dbs[0]) as c:
        before=[tuple(r) for r in c.execute('SELECT id,state,result_json FROM jobs ORDER BY id')]
    response=backup_request()
    assert response.status_code==200
    data=json.loads(response.body)
    assert data['status']=='already_backed_up' and not data['accepted']
    assert data['integrity_verified'] is False  # presence/history is not a fresh SHA proof
    assert data['media_file_count']==1
    with database_connection(dbs[0]) as c:
        assert [tuple(r) for r in c.execute('SELECT id,state,result_json FROM jobs ORDER BY id')]==before
    assert source.read_bytes()==original


def test_r01_missing_copy_requires_explicit_verified_recovery(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context);data=source.read_bytes()
    with database_connection(dbs[0]) as c:
        rel=c.execute('SELECT current_relative_path FROM files WHERE job_id=?',(first['id'],)).fetchone()[0]
    target=storage_paths(ws)['backup_root']/rel;target.unlink()
    response=backup_request();status=json.loads(response.body)
    assert response.status_code==200 and status['status']=='verification_required' and not status['accepted']
    assert not target.exists() and source.read_bytes()==data
    second=queue_and_run(dbs[0],context,confirmed=True)
    assert second['duplicate_of_job_id']==first['id']
    assert second['result']['organization']['file_count']==1
    assert target.read_bytes()==data and source.read_bytes()==data
    for _ in range(3):
        from app.database import initialize_database
        initialize_database(dbs[0])
        with database_connection(dbs[0]) as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()


def test_r01_explicit_integrity_check_still_hashes_and_rejects_corruption(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context);original=source.read_bytes()
    with database_connection(dbs[0]) as c:rel=c.execute('SELECT current_relative_path FROM files WHERE job_id=?',(first['id'],)).fetchone()[0]
    target=storage_paths(ws)['backup_root']/rel
    damaged=bytes([original[0]^1])+original[1:];target.write_bytes(damaged)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error: backup_request(True)
    assert error.value.status_code==409
    assert claim_next_job(dbs[0]) is None
    assert source.read_bytes()==original and target.read_bytes()==damaged


def node(tmp_path, script):
    target=tmp_path/'rc3.js';target.write_text(script)
    result=subprocess.run(['node',str(target)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_r01_click_contract_and_explicit_integrity(tmp_path):
    from app.main import index
    html=index();start=html.index('    async function confirmSdIntegrity()');end=html.index('    deviceSelect.addEventListener',start)
    node(tmp_path,'''let calls=[],confirmed=0,selectedSdDevice={mounted:true,read_only:true,device_id:'CARD',label:'User <name>'};
let sdSourceSummary={has_import_history:true,new_file_count:0,changed_file_count:0,unknown_file_count:0};
const window={BibliothekarI18n:{confirmAsync:async()=>{confirmed++;return true}}};
const sdImportButton={addEventListener(){}},sdVerifyButton={addEventListener(){}};
const showError=error=>{throw error};
const startFolderImportSelection=async(...args)=>calls.push(args);
''' + html[start:end] + '''
(async()=>{
await requestSdBackup();if(confirmed!==1||calls.at(-1)[4]!==true)throw Error('repeat did not verify through unified path');
await requestSdBackup(true);if(confirmed!==2||calls.at(-1)[4]!==true)throw Error('explicit integrity unavailable');
sdSourceSummary.new_file_count=1;await requestSdBackup();if(confirmed!==3||!calls.at(-1)[4])throw Error('new files not verified');
selectedSdDevice.read_only=false;let denied=false;try{await requestSdBackup()}catch(e){denied=true};if(!denied||calls.length!==3)throw Error('RO guard');
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_r02_complete_language_matrix_and_opaque_data(tmp_path):
    from app.ui_i18n import I18N_UI_JS
    from app.main import index
    html=index();start=html.index('    async function confirmSdIntegrity()');end=html.index('    async function requestSdBackup',start)
    cases={
        'SD-Karte wurde sicher ausgeworfen.':'SD card safely ejected.',
        'Erneut sichern':'Back up again','Integrität prüfen':'Check backup integrity',
        'ca. 8 Min.':'approx. 8 min.','fertig':'done',
        'Ordnerimport erfolgreich abgeschlossen. 18 Mediendateien wurden verifiziert.':'Import completed. 18 media files verified.',
        'Ordnerimport, Metadatenanalyse und Übernahme in den zentralen Tagesbestand sind abgeschlossen.':'Import, metadata analysis and transfer to the central daily inventory are complete.',
        'Zum archivierten Ereignis hinzufügen':'Add to archived event',
    }
    node(tmp_path,'''globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Import',readyState:'loading',documentElement:{dataset:{}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
''' + I18N_UI_JS + '\nconst cases='+json.dumps(cases,ensure_ascii=False)+''';
const t=window.BibliothekarI18n.t;
for(const [raw,en] of Object.entries(cases))if(t(raw)!==en)throw Error(raw+' => '+t(raw));
for(const value of ['Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01','Test 2','Test 5','< & Test','DSCF0603.JPG','2026/07-20 - < & Test/All','stage: event_sort_applied']){
if(t(value)!==value)throw Error('opaque data changed: '+value);}
window.BibliothekarI18n.confirmAsync=async raw=>{if(!t(raw).startsWith('This source was processed before.'))throw Error('untranslated confirmation');return true};
''' + html[start:end] + '\nconfirmSdIntegrity().catch(e=>{console.error(e);process.exitCode=1});')


def test_r03_r04_browser_bundle_and_css(tmp_path):
    """Export actual renderer/CSS for the separate isolated Chromium DOM probe."""
    import os,re
    import tinycss2
    from app.workspace_ui import WORKSPACE_HTML
    from app.transfer_ui import TRANSFER_HTML
    from app.ui_i18n import I18N_UI_JS
    from app.main import index
    output=Path(os.environ.get('AUDIT_OUTPUT',str(tmp_path)))
    def part(source,start,end):return source[source.index(start):source.index(end,source.index(start))]
    for name,page in {'workspace':WORKSPACE_HTML,'archive':TRANSFER_HTML,'import':index()}.items():
        for css in re.findall(r'<style[^>]*>(.*?)</style>',page,re.S):
            rules=tinycss2.parse_stylesheet(css,skip_comments=True,skip_whitespace=True)
            assert not [r for r in rules if r.type=='error']
    from app.ui_shell import apply_shell
    bundle={'shellWorkspace':apply_shell(WORKSPACE_HTML,active_area='workspace',subarea='captures'),'shellArchive':apply_shell(TRANSFER_HTML,active_area='archive'),'workspace':WORKSPACE_HTML,'archive':TRANSFER_HTML,'import':index(),'i18n':I18N_UI_JS,
        'preview':part(WORKSPACE_HTML,'    const mobilePreviewButton =','    function setSelectedPreviewEvent'),
        'stored':part(WORKSPACE_HTML,'    function renderStoredEventPreview(','    async function openStoredEventPreview'),
        'history':part(TRANSFER_HTML,'  function archiveHistoryCounts(','  function syncArchiveHistoryDetails('),
        'historyMedia':part(TRANSFER_HTML,'  function syncArchiveHistoryDetails(','  function renderArchive('),
        'jobs':part(index(),'    const activeStates =','    async function loadHealth()')}
    (output/'browser-bundle.json').write_text(json.dumps(bundle))


def test_r01_incremental_real_worker_preserves_duplicate(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context);original=source.read_bytes()
    # Separate synthetic image bytes; family admission and SHA checks remain real.
    from PIL import Image
    added=source.with_name('new.JPG');Image.new('RGB',(8,8),'blue').save(added)
    subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:07:23 10:14:04',str(added)],check=True,capture_output=True)
    second=queue_and_run(dbs[0],context,confirmed=True)
    assert second['result']['organization']['file_count']==1
    assert second['result']['source']['duplicate_file_count']==1
    assert source.read_bytes()==original
    with database_connection(dbs[0]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('SELECT state FROM jobs WHERE id=?',(first['id'],)).fetchone()[0]=='completed'
