"""Owner-only useful read views while an operation's write scope is fenced."""
from contextlib import closing
from pathlib import Path
import json,sqlite3
from fastapi.responses import HTMLResponse,JSONResponse


def rows(database,sql,args=()):
    p=Path(database).absolute()
    if not p.is_file() or p.resolve()!=p:raise ValueError('catalogue unavailable: '+str(p))
    with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        return [dict(r) for r in c.execute(sql,args)]


def catalogue(registry,library,offset=0):
    libs=rows(registry,'SELECT * FROM libraries WHERE COALESCE(is_registered,1)=1 ORDER BY library_id')
    owner=next((r for r in libs if r['library_id']==library),None)
    if owner is None:raise ValueError('unknown registered library: '+library)
    database=owner['database_path']
    return {'library':owner['library_id'],'libraries':libs,
        'files':rows(database,'SELECT id,job_id,original_relative_path,current_relative_path,current_root_kind,sha256_original,sha256_current,size_bytes FROM files ORDER BY id LIMIT 100 OFFSET ?',(max(0,offset),)),
        'total_files':rows(database,'SELECT COUNT(*) AS count FROM files')[0]['count'],
        'tasks':rows(database,'SELECT id,area,status,source_relative_path,output_path,error_message,completed_at FROM metadata_corrections ORDER BY created_at DESC LIMIT 100'),
        'jobs':rows(database,'SELECT id,operation,state,stage,error_message FROM jobs ORDER BY created_at DESC LIMIT 100'),
        'read_only':True}


HTML='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bibliothekar · Operations</title>
<style>main{max-width:1100px;margin:24px auto;padding:16px}section{margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #8884;text-align:left;overflow-wrap:anywhere}select,button{padding:12px;min-height:44px}#notice{border:2px solid #e9a23b;padding:16px;border-radius:12px}code{overflow-wrap:anywhere}</style></head>
<body><main><h1 data-en="Library and operation overview" data-de="Bibliotheken und Vorgänge">Library and operation overview</h1>
<div id="notice"><b>Storage: READY</b><p data-en="An operation requires review. Affected writes are paused; library history and diagnoses remain available. No evidence is reset." data-de="Ein Vorgang muss geprüft werden. Betroffene Schreibvorgänge sind angehalten; Bestandshistorie und Diagnosen bleiben erreichbar. Nachweise werden nicht zurückgesetzt."></p></div>
<section><label data-en="Library" data-de="Bibliothek"></label> <select id="library"></select> <button id="refresh" data-en="Refresh read view" data-de="Leseansicht aktualisieren"></button> <button id="recheck" data-en="Run qualified recovery" data-de="Geprüfte Wiederherstellung ausführen"></button></section>
<section><h2 data-en="Catalogue (recorded paths; no file scan)" data-de="Katalog (gespeicherte Pfade; kein Dateiscan)"></h2><div id="files"></div><button id="previous">←</button><button id="next">→</button></section>
<section><h2 data-en="Metadata tasks" data-de="Metadatenaufträge"></h2><div id="tasks"></div></section>
<section><h2 data-en="Jobs" data-de="Aufträge"></h2><div id="jobs"></div></section>
<details><summary data-en="Protected operations and technical diagnosis" data-de="Geschützte Vorgänge und technische Diagnose"></summary><pre id="diagnosis"></pre></details><p id="result" role="status"></p></main>
<script>
(()=>{const $=x=>document.getElementById(x);let offset=0;const lang=()=>localStorage.getItem('bibliothekar-language')==='de'?'de':'en';
function translate(){document.querySelectorAll('[data-en]').forEach(e=>e.textContent=e.dataset[lang()])}translate();
async function get(url){const r=await fetch(url,{credentials:'same-origin'});const v=await r.json();if(!r.ok)throw Error(JSON.stringify(v));return v}
function table(id,items,keys){const root=$(id);root.textContent='';const t=document.createElement('table');for(const item of items){const tr=document.createElement('tr');for(const key of keys){const td=document.createElement('td');td.textContent=String(item[key]??'');tr.append(td)}t.append(tr)}root.append(t)}
async function load(){try{const status=await get('/api/operations/status');$('diagnosis').textContent=JSON.stringify(status,null,2);if(status.writes_allowed){location.reload();return}
const data=await get('/api/operations/catalogue?library_id='+encodeURIComponent($('library').value||'main')+'&offset='+offset);
if(!$('library').options.length)for(const l of data.libraries){const o=document.createElement('option');o.value=l.library_id;o.textContent=l.display_name;$('library').append(o)}
table('files',data.files,['id','current_relative_path','sha256_current']);table('tasks',data.tasks,['source_relative_path','status','error_message']);table('jobs',data.jobs,['id','operation','state','error_message']);$('result').textContent=data.total_files+' catalogue records';$('previous').disabled=offset===0;$('next').disabled=offset+100>=data.total_files;
}catch(e){$('result').textContent=e.message}}
$('library').onchange=()=>{offset=0;load()};$('previous').onclick=()=>{offset=Math.max(0,offset-100);load()};$('next').onclick=()=>{offset+=100;load()};$('refresh').onclick=load;
$('recheck').onclick=async e=>{e.target.disabled=true;try{const c=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('bibliothekar_csrf='));const r=await fetch('/api/settings/storage-recheck',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Bibliothekar-CSRF':c?decodeURIComponent(c.split('=').slice(1).join('=')):''},body:'{}'});const v=await r.json();if(!r.ok)throw Error(JSON.stringify(v));location.reload()}catch(x){$('result').textContent=x.message}finally{e.target.disabled=false}};load();})();
</script></body></html>'''


def response_for(request,workspace,registry,status):
    path=request.url.path
    def main_database():
        owners=rows(registry,"SELECT database_path FROM libraries WHERE library_id='main'")
        if len(owners)!=1:raise ValueError('main catalogue authority missing')
        return Path(owners[0]['database_path'])
    if request.method=='GET':
        try:
            if path=='/api/operations/status':return JSONResponse(status)
            if path=='/api/operations/catalogue':return JSONResponse(catalogue(registry,request.query_params.get('library_id','main'),int(request.query_params.get('offset','0'))))
            if path=='/api/libraries':
                data=rows(registry,'SELECT * FROM libraries WHERE COALESCE(is_registered,1)=1 ORDER BY library_id')
                return JSONResponse({'libraries':data,'count':len(data)})
            if path=='/api/jobs':
                data=rows(main_database(),'SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100')
                return JSONResponse({'jobs':data})
            if path.startswith('/api/jobs/') and path.count('/')==3:
                data=rows(main_database(),'SELECT * FROM jobs WHERE id=?',(path.rsplit('/',1)[1],))
                return JSONResponse(data[0] if data else {'detail':'job not found'},status_code=200 if data else 404)
            if not path.startswith('/api/'):
                from app.ui_shell import apply_shell
                return HTMLResponse(apply_shell(HTML,active_area='tasks'))
        except (ValueError,sqlite3.Error) as error:return JSONResponse({'detail':str(error),'operations':status},status_code=409)
    return JSONResponse({'detail':'operation_recovery_required','storage_state':'READY','operations':status},status_code=409)
