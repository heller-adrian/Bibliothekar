"""Synthetic RC1 UI regressions. No NAS access or external network."""
import json
import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest
from tests.backend.test_f14_root_operations import fixture


def node(tmp_path, source):
    script = tmp_path / 'probe.cjs'
    script.write_text(source)
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def js_function(source, name, next_name):
    return source[source.index('    function '+name):source.index('    function '+next_name)]


def test_b05_permission_error_is_not_empty_inventory(tmp_path, monkeypatch):
    from app import main
    from fastapi import HTTPException
    root = tmp_path / 'nas'; root.mkdir()
    monkeypatch.setattr(main, '_safe_root', lambda key: root)
    original = Path.iterdir
    def denied(path):
        if path == root: raise PermissionError('synthetic ACL denial')
        return original(path)
    monkeypatch.setattr(Path, 'iterdir', denied)
    with pytest.raises(HTTPException) as error:
        main.api_source_folders('nas', '.')
    assert error.value.status_code == 403
    assert list(root.glob('*')) == []


@pytest.mark.parametrize('name', ['Trip<test>', 'Name?', 'A:B', 'A|B', 'Trip*', 'A"B', 'A\x01B', 'Trip.', 'CON'])
def test_b10_reject_unsafe_new_name(name):
    from app.event_structure import _clean_name, EventPreviewError
    with pytest.raises(EventPreviewError): _clean_name(name, 'Ereignisname')


def test_b10_unicode_and_legacy_names_unchanged():
    from app.event_structure import _clean_name
    from app.event_naming import render_event_folder_name
    assert _clean_name('日本 – Grüße 🎥', 'Ereignisname') == '日本 – Grüße 🎥'
    assert render_event_folder_name(event_name='legacy', start_date='2026-07-23', end_date='2026-07-23',
        start_time=None, end_time=None, uses_time_range=False,
        naming={'mode':'locked', 'locked_folder_name':'07-23 - Old<name>'}) == '07-23 - Old<name>'


def test_b08_selection_mode(tmp_path):
    from app.workspace_ui import WORKSPACE_HTML
    start = WORKSPACE_HTML.index('    function refreshBackupSelection(')
    end = WORKSPACE_HTML.index('    async function loadJobs', start)
    node(tmp_path, 'let selectedJobIds=new Set(["a"]), allActiveBackups=true;\n' + WORKSPACE_HTML[start:end] + '''
const jobs=[{id:'a'},{id:'b'},{id:'old',workflow_status:'archived'}];
refreshBackupSelection(jobs);
if([...selectedJobIds].join()!=='a,b')throw Error('default excludes new backup');
allActiveBackups=false;selectedJobIds=new Set(['a']);refreshBackupSelection(jobs);
if([...selectedJobIds].join()!=='a')throw Error('explicit selection changed');
selectedJobIds.clear();refreshBackupSelection(jobs);
if(selectedJobIds.size)throw Error('explicit empty selection changed');
''')


def test_b08_finished_import_refreshes_once(tmp_path):
    from app.workspace_ui import WORKSPACE_HTML
    start=WORKSPACE_HTML.index('    let observedImports=')
    end=WORKSPACE_HTML.index('    async function loadWorkspace',start)
    node(tmp_path, '''let handler,calls=0;
const window={addEventListener:(name,fn)=>{if(name==='bk-activity-updated')handler=fn}};
const loadJobs=async()=>{calls++};const setStatus=()=>{throw Error('unexpected status error')};
''' + WORKSPACE_HTML[start:end] + '''
(async()=>{
await handler({detail:[{id:'a',kind:'import',active:true}]});
if(calls)throw Error('refresh before completion');
await handler({detail:[]});await handler({detail:[]});
if(calls!==1)throw Error('missing or duplicate completed refresh');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_b09_planned_tree_and_actual_root(tmp_path):
    from app.workspace_ui import WORKSPACE_HTML
    start = WORKSPACE_HTML.index('    function renderStoredEventPreview(')
    end = WORKSPACE_HTML.index('    async function openStoredEventPreview', start)
    node(tmp_path, '''const window={};const structurePreview={classList:{add(){}},innerHTML:''};
const previewBody={};const scheduleTreeFit=()=>{};
const escapeHtml=v=>String(v).replaceAll('<','&lt;');
const formatStoredDateTime=v=>v;const workspaceStatusLabel=v=>v;const bk0511PreviewLabel=(de,en)=>en;
''' + WORKSPACE_HTML[start:end] + '''
const event={name:'User <name>',status:'planned',folder_name:'07-23 - User',start_datetime:'2026-07-23',end_datetime:'2026-07-23'};
renderStoredEventPreview({event,structure_text:'2026/\\n└── 07-23 - User/\\n    └── All/',physical_state:{available:false}});
if(!structurePreview.innerHTML.includes('└── 07-23 - User/'))throw Error('missing planned root');
if(structurePreview.innerHTML.includes('User <name>'))throw Error('unescaped title');
event.status='archived';renderStoredEventPreview({event,structure_text:'WRONG PLAN',physical_state:{available:true,event_prefix:'2026/07-23 - Renamed',tree_text:'All/'}});
if(!structurePreview.innerHTML.includes('2026/07-23 - Renamed'))throw Error('missing physical root');
if(structurePreview.innerHTML.includes('WRONG PLAN'))throw Error('planned tree shown as actual');
''')


def test_b07_actual_inventory_does_not_rewrite_history(tmp_path):
    from app.database import initialize_database, database_connection
    from app.archive_transfer import verify_event_archive, list_archive_candidates
    from app.event_layout import ensure_event_layout_snapshot
    from tests.backend.test_0263_event_inventory import seed_job, seed_event, seed_family, NOW
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    archive=tmp_path/'archive'; root=archive/'2026/07-23 - Trip'; (root/'Alle').mkdir(parents=True)
    photo=root/'Alle/A.JPG'; photo.write_bytes(b'original archive photo')
    with database_connection(db) as c:
        seed_job(c); seed_event(c, status='archived')
        seed_family(c, content=photo.read_bytes(), current_path='2026/07-23 - Trip/Alle/A.JPG')
        ensure_event_layout_snapshot(c,'e',now=NOW)
    verification=verify_event_archive(db,archive,'j','e')
    assert verification['verified']
    def history():
        with database_connection(db) as c:
            return [dict(r) for r in c.execute('SELECT * FROM event_archive_verifications')]
    before=history(); original_hash=hashlib.sha256(photo.read_bytes()).hexdigest()
    (root/'event.json').write_text(json.dumps({'event':{'id':'e'}}))
    root=root.rename(root.with_name('07-23 - Manually renamed'))
    first=list_archive_candidates(db,archive,observe_current=True)['candidates'][0]
    assert first['current_archive']['event_prefix']=='2026/07-23 - Manually renamed'
    assert first['current_archive']['file_count']==1
    assert first['current_archive']['family_count']==1
    assert hashlib.sha256((root/'Alle/A.JPG').read_bytes()).hexdigest()==original_hash
    # A deliberate synthetic external deletion must affect only the observation.
    (root/'Alle/A.JPG').unlink()
    second=list_archive_candidates(db,archive,observe_current=True)['candidates'][0]
    assert second['current_archive']['file_count']==0
    assert second['current_archive']['family_count']==0
    assert second['verification_file_count']==1
    assert history()==before
    with database_connection(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==1
    root.rename(root.with_name('gone'))
    (archive/'2026/gone/event.json').unlink()
    unavailable=list_archive_candidates(db,archive,observe_current=True)['candidates'][0]
    assert unavailable['current_archive']['available'] is False
    assert history()==before


def test_b13_foreign_trash_is_rejected_before_queue(fixture):
    from fastapi.testclient import TestClient
    from app import main
    from app.storage_config import storage_paths
    from app.database import database_connection
    _,ws,_,dbs,_=fixture
    root=storage_paths(ws)['trash_root']; root.mkdir(exist_ok=True)
    photo=root/'unknown.JPG'; photo.write_bytes(b'foreign original')
    identity=(photo.stat().st_dev,photo.stat().st_ino); digest=hashlib.sha256(photo.read_bytes()).hexdigest()
    # This HTTP fixture bypasses startup. Publish the same private lock fence
    # before entering request admission, as a completed bootstrap would do.
    from app.trash_selective import _operation_lock
    with _operation_lock(ws):
        pass
    client=TestClient(main.app,raise_server_exceptions=False)
    try:
        response=client.post('/api/trash/restore',json={'relative_paths':['unknown.JPG']})
        assert response.status_code==409,response.text
        assert 'keiner Sicherung zuzuordnen' in response.json()['detail']
    finally:
        client.close()
    assert (photo.stat().st_dev,photo.stat().st_ino)==identity
    assert hashlib.sha256(photo.read_bytes()).hexdigest()==digest
    for db in dbs:
        with database_connection(db) as c:
            assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='trash_import'").fetchone()[0]==0
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_c_javascript_syntax_and_rendered_pages(tmp_path):
    from app import main
    from app.ui_shell import apply_shell
    from app.workspace_ui import WORKSPACE_HTML
    from app.events_ui import EVENTS_HTML
    from app.transfer_ui import TRANSFER_HTML
    from app.metadata_correction_ui import METADATA_CORRECTION_HTML
    from app.trash_ui import TRASH_HTML
    pages={'workspace':WORKSPACE_HTML,'events':EVENTS_HTML,'archive':TRANSFER_HTML,
           'metadata':METADATA_CORRECTION_HTML,'trash':TRASH_HTML}
    output=Path(os.environ.get('AUDIT_OUTPUT',str(tmp_path)))/'rendered';output.mkdir(exist_ok=True)
    pages={k:apply_shell(v,active_area=k if k in {'metadata','archive','trash'} else 'workspace',subarea='events' if k=='events' else 'captures') for k,v in pages.items()}
    pages['import']=main.index()
    for name,html in pages.items():
        (output/(name+'.html')).write_text(html)
        for index,code in enumerate(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S)):
            script=tmp_path/f'{name}-{index}.js';script.write_text(code)
            result=subprocess.run(['node','--check',str(script)],capture_output=True,text=True,timeout=15)
            assert result.returncode==0,result.stderr


def test_b14_locale_examples_and_protected_data(tmp_path):
    from app.ui_i18n import I18N_UI_JS
    from app.ui_i18n_rc1 import RC1_TRANSLATIONS
    from app.ui_rc13 import workspace_words
    cases={**{key:workspace_words(value) for key,value in RC1_TRANSLATIONS.items()}, '16 freie Familien':'16 available families',
           'ca. 15 Sek.':'approx. 15 sec.', 'ca. 2 Std. 4 Min.':'approx. 2 hr. 4 min.',
           'In Tagesbestand einsortieren (2)':'Add to daily inventory (2)',
           'Datei keiner Sicherung zuzuordnen; Wiederherstellung nicht möglich: Grüße.JPG':
           'File has no backup provenance; restoration is not possible: Grüße.JPG'}
    node(tmp_path, '''globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Metadatenkorrektur',readyState:'loading',documentElement:{dataset:{}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
''' + I18N_UI_JS + '\nconst cases='+json.dumps(cases,ensure_ascii=False)+''';
const t=window.BibliothekarI18n.t;
const mismatches=Object.entries(cases).filter(([raw,en])=>t(raw)!==en).map(([raw,en])=>({raw,actual:t(raw),en}));
if(mismatches.length)throw Error(JSON.stringify(mismatches));
for(const original of ['Sommerurlaub','IMG_5888.JPG','/nas/Aufnahmen/hoch','EV_123']){
if(t(original)!==original)throw Error('data changed: '+original);}
window.BibliothekarI18n.setLocale('de');
if(document.title!=='Metadatenkorrektur')throw Error('German title lost');
''')


def test_b18_page_status_and_user_labels(tmp_path):
    from app.ui_shell import BIBLIOTHEKAR_0444_JS
    s=BIBLIOTHEKAR_0444_JS
    page=s[s.index('  function renderPageActivity('):s.index('\n  let ',s.index('  function renderPageActivity('))]
    # Read complete function up to the next existing declaration.
    page=page[:page.index('\n  }')+4]
    make=s[s.index('  function makeItem('):s.index('  async function refresh()',s.index('  function makeItem('))]
    node(tmp_path, '''const window={BibliothekarI18n:{t:v=>({'hoch':'high','Anwenden':'Apply'})[v]||v}};
const dismissedPageActivities=new Set();
const document={createElement:tag=>({tag,dataset:{},children:[],addEventListener(){},setAttribute(k,v){this[k]=v},append(...xs){this.children.push(...xs)},appendChild(x){this.children.push(x)}})};
const destination=item=>item.id?'/events':'/other';
const location={pathname:'/events'};const pageActivity={replaceChildren(...xs){this.children=xs}};
''' + make + page + '''
const queued={kind:'apply',id:'q',label:'From Trash',status:'queued',active:true};
const done={...queued,id:'d',status:'completed',active:false};
const failed={...queued,id:'f',status:'failed',active:false};
renderPageActivity([queued,done,failed,{kind:'apply',status:'applied',active:false}]);
if(pageActivity.hidden||pageActivity.children.length!==4)throw Error('wrong page status');
const icons=pageActivity.children.slice(1).map(row=>row.children[0].textContent);
if(icons.join(',')!==',✓,!')throw Error('queued treated as completed');
const user=makeItem({kind:'import',label:'hoch',status:'completed',active:false});
if(user.children[1].children[0].textContent!=='hoch')throw Error('user label translated');
const event=makeItem({kind:'apply',job_id:'j',label:'hoch anwenden',status:'applied',active:false});
if(event.children[1].children[0].textContent!=='Apply: hoch')throw Error('event name translated');
''')


def test_b15_b16_b17_b19_ui_contracts():
    from app.workspace_ui import WORKSPACE_HTML
    from app.metadata_correction_ui import METADATA_CORRECTION_HTML
    from app.ui_shell import apply_shell
    assert '<details class="suggestion-help">' in WORKSPACE_HTML
    details=WORKSPACE_HTML[WORKSPACE_HTML.index('<details class="suggestion-files">'):]
    assert 'Herkunft:' in details.split('</details>',1)[0]
    assert 'position:static;max-height:none;overflow:visible' in METADATA_CORRECTION_HTML
    assert 'Verwaltete Pfade · nur zur Information' in apply_shell(WORKSPACE_HTML,active_area='workspace',subarea='captures')
    assert '>Medien</a>' in apply_shell(WORKSPACE_HTML,active_area='workspace',subarea='captures')
