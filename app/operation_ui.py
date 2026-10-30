"""Authenticated operation diagnostics, embedded in the normal application shell.

The shell and ordinary read APIs remain available. This module supplies only an
additional diagnostic panel and explicit read-only catalogue fallback, never a
replacement for every application page.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
from fastapi.responses import JSONResponse


def rows(database, sql, args=()):
    path = Path(database).absolute()
    if not path.is_file() or path.resolve() != path:
        raise ValueError('catalogue unavailable: ' + str(path))
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        return [dict(row) for row in connection.execute(sql, args)]


def catalogue(registry, library, offset=0):
    libraries = rows(registry, 'SELECT * FROM libraries WHERE COALESCE(is_registered,1)=1 ORDER BY library_id')
    owner = next((row for row in libraries if row['library_id'] == library), None)
    if owner is None:
        raise ValueError('unknown registered library: ' + library)
    database = owner['database_path']
    return {
        'library': owner['library_id'], 'libraries': libraries,
        'files': rows(database, 'SELECT id,job_id,original_relative_path,current_relative_path,current_root_kind,sha256_original,sha256_current,size_bytes FROM files ORDER BY id LIMIT 100 OFFSET ?', (max(0, offset),)),
        'total_files': rows(database, 'SELECT COUNT(*) AS count FROM files')[0]['count'],
        'tasks': rows(database, 'SELECT id,area,status,source_relative_path,output_path,error_message,completed_at FROM metadata_corrections ORDER BY created_at DESC LIMIT 100'),
        'jobs': rows(database, 'SELECT id,operation,state,stage,error_message FROM jobs ORDER BY created_at DESC LIMIT 100'),
        'read_only': True,
    }


def response_for(request, workspace, registry, status):
    if request.method != 'GET':
        return JSONResponse({'detail': 'operation_recovery_required', 'storage_state': 'READY', 'operations': status}, status_code=409)
    if request.url.path == '/api/operations/status':
        return JSONResponse(status)
    if request.url.path == '/api/operations/catalogue':
        try:
            return JSONResponse(catalogue(registry, request.query_params.get('library_id', 'main'), int(request.query_params.get('offset', '0'))))
        except (ValueError, sqlite3.Error) as error:
            return JSONResponse({'detail': str(error)}, status_code=409)
    return JSONResponse({'detail': 'operation_endpoint_unknown'}, status_code=404)


# Displayed on the existing pages. No navigation replacement or auth bypass.
NOTICE = '''<script>(()=>{async function updateOperationNotice(){
try{const r=await fetch('/api/operations/status',{credentials:'same-origin'});if(!r.ok)return;const s=await r.json();
let box=document.getElementById('bibliothekar-operation-notice');if(s.writes_allowed){if(box)box.remove();return}
if(!box){box=document.createElement('aside');box.id='bibliothekar-operation-notice';box.setAttribute('role','status');box.style.cssText='margin:12px;padding:14px;border:2px solid #bf852b;border-radius:10px;overflow-wrap:anywhere';document.body.prepend(box)}
box.textContent='';const de=localStorage.getItem('bibliothekar-language')==='de';const message=document.createElement('p');
message.textContent=de?'Ein Vorgang erfordert Prüfung. Schreibvorgänge im betroffenen Arbeitsbereich sind angehalten. Leseansichten bleiben erreichbar.':'An operation requires review. Writes in the affected workspace are paused. Read views remain available.';
box.append(message);const details=document.createElement('details');const title=document.createElement('summary');title.textContent=de?'Vorgänge und Diagnose':'Operations and diagnosis';details.append(title);const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent=JSON.stringify(s,null,2);details.append(pre);box.append(details);
const link=document.createElement('a');link.href='/settings';link.textContent=de?'Einstellungen und Wiederherstellung':'Settings and recovery';box.append(link);
}catch(_){}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',updateOperationNotice);else updateOperationNotice();})();</script>'''
