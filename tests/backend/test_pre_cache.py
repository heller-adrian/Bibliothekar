import json,shutil,subprocess
from pathlib import Path
from app.workspace_ui import WORKSPACE_HTML
from app import view_cache


def test_large_workspace_snapshot_reentry_uses_latest_view(tmp_path):
    source=WORKSPACE_HTML
    a=source.index('    async function loadWorkspace(');b=source.index('    function renderEventSuggestions()',a)
    helper=''
    try:
        from app.ui_workspace_cache import WORKSPACE_CACHE_JS
        helper=WORKSPACE_CACHE_JS
    except ImportError:pass
    program='''const assert=require('node:assert/strict');
const window={__bkLibraryId:'main'},sessionStorage={data:new Map(),getItem(k){return this.data.get(k)||null},setItem(k,v){this.data.set(k,v)},removeItem(k){this.data.delete(k)}};
let workspace=null,eventSuggestions=[],globalFolderLayout={},workspaceLoadSerial=0;
const jobs=[{id:'J'}],selectedJobIds=new Set(['J']),selectedDays=new Set(),jobSelect={value:'J'};
const statusElement={classList:{add(){},remove(){}}};let rendered=[];
const renderSummary=()=>rendered.push(workspace.statistics.file_count),renderEventSuggestions=()=>{},renderDays=()=>{},renderPlannedActions=()=>{},renderSelection=()=>{},updateTechnicalAnchor=()=>{},setStatus=()=>{};
let result={statistics:{file_count:88},planning_overview:{timeline_groups:[]}};
let pending;const getJson=async()=>result;
'''+helper+'\n'+source[a:b]+'''
(async()=>{
await loadWorkspace();
result={statistics:{file_count:3980},planning_overview:{timeline_groups:[]},padding:'camera-data'.repeat(190000)};
await loadWorkspace();
workspace=null;rendered=[];
const prior=getJson;
// Pause the network after a warm browser navigation. The saved view itself
// must now be 3,980, not the old 88-file view left by RC14's size guard.
getJson=()=>new Promise(resolve=>pending=resolve);
const loading=loadWorkspace();await new Promise(r=>setTimeout(r,150));
assert.equal(rendered.at(-1),3980);
pending(result);await loading;
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    program=program.replace('const getJson=async()=>result','let getJson=async()=>result')
    path=tmp_path/'probe.cjs';path.write_text(program)
    result=subprocess.run([shutil.which('node'),str(path)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_cache_rejects_result_computed_before_database_change(tmp_path):
    db=tmp_path/'db';db.write_bytes(b'old')
    stamp=view_cache.database_stamp(db)
    db.write_bytes(b'new catalogue state')
    accepted=view_cache.put_snapshot(db,'workspace',{'count':88},observed_stamp=stamp)
    assert accepted is False
    assert view_cache.get_snapshot(db,'workspace') is None


def test_out_of_order_workspace_responses_cannot_restore_old_count(tmp_path):
    source=WORKSPACE_HTML
    a=source.index('    async function loadWorkspace(');b=source.index('    function renderEventSuggestions()',a)
    from app.ui_workspace_cache import WORKSPACE_CACHE_JS
    program='''const assert=require('node:assert/strict');const window={__bkLibraryId:'main'};
const sessionStorage={getItem:()=>null,removeItem(){},setItem(){}};
let workspace=null,eventSuggestions=[],globalFolderLayout={},workspaceLoadSerial=0;
const jobs=[{id:'J'}],selectedJobIds=new Set(['J']),selectedDays=new Set(),jobSelect={value:'J'},statusElement={classList:{add(){},remove(){}}};
const renderSummary=()=>{},renderEventSuggestions=()=>{},renderDays=()=>{},renderPlannedActions=()=>{},renderSelection=()=>{},updateTechnicalAnchor=()=>{},setStatus=()=>{};
let pending=[];const getJson=()=>new Promise(resolve=>pending.push(resolve));
'''+WORKSPACE_CACHE_JS+'\n'+source[a:b]+'''
(async()=>{const old=loadWorkspace();await new Promise(r=>setImmediate(r));const latest=loadWorkspace();await new Promise(r=>setImmediate(r));
pending[1]({statistics:{file_count:3980},planning_overview:{}});await latest;
pending[0]({statistics:{file_count:88},planning_overview:{}});await old;
assert.equal(workspace.statistics.file_count,3980);})().catch(e=>{console.error(e);process.exitCode=1});'''
    p=tmp_path/'race.cjs';p.write_text(program)
    r=subprocess.run([shutil.which('node'),str(p)],capture_output=True,text=True,timeout=10)
    assert r.returncode==0,r.stderr
