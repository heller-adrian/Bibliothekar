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
NOTICE = '''<script>(() => {
  let status;
  function startupOnly(s) {
    return s.issues.length === 1 && s.issues[0].phase === 'recovery_in_progress'
      && s.reservations.every(reservation => reservation.live === true);
  }
  function renderNotice() {
    if (!status) return;
    let box = document.getElementById('bibliothekar-operation-notice');
    if (status.writes_allowed) {
      box?.remove();
      return;
    }
    const starting = startupOnly(status);
    const de = localStorage.getItem('bibliothekar-language') === 'de';
    // Keep open diagnostics and button focus during status polling.
    if (box && box.dataset.notice === (starting ? 'startup' : 'recovery')
        && box.dataset.language === String(de)) return;
    if (!box) {
      box = document.createElement('aside');
      box.id = 'bibliothekar-operation-notice';
      box.setAttribute('role', 'status');
      box.style.cssText = 'margin:12px;padding:14px;border:2px solid #bf852b;border-radius:10px;overflow-wrap:anywhere';
      document.body.prepend(box);
    }
    box.dataset.notice = starting ? 'startup' : 'recovery';
    box.dataset.language = String(de);
    box.style.borderColor = starting ? 'var(--border, currentColor)' : '#bf852b';
    if (starting) {
      box.textContent = de
        ? 'Bibliothekar wird vorbereitet. Schreibzugriffe werden nach der Startprüfung freigegeben.'
        : 'Bibliothekar is getting ready. Writes will be enabled after startup checks.';
      return;
    }
    const message = document.createElement('p');
    message.textContent = status.workspace_writes_allowed
      ? (de ? 'Ein Vorgang erfordert Prüfung. Nur die ausgewiesenen betroffenen Vorgänge sind angehalten; unabhängige Aktionen bleiben verfügbar.'
            : 'An operation requires review. Only the identified affected operations are paused; independent actions remain available.')
      : (de ? 'Ein Vorgang besitzt noch ungeklärte Schreibwirkungen. Schreibzugriffe sind bis zur Qualifikation gesperrt; Leseansichten und Diagnosen bleiben erreichbar.'
            : 'An operation has unresolved write effects. Writes remain protected until qualification; read views and diagnostics remain available.');
    const details = document.createElement('details');
    const title = document.createElement('summary');
    title.textContent = de ? 'Vorgänge und Diagnose' : 'Operations and diagnosis';
    const pre = document.createElement('pre');
    pre.style.whiteSpace = 'pre-wrap';
    pre.textContent = JSON.stringify(status, null, 2);
    details.append(title, pre);
    const link = document.createElement('button');
    link.type = 'button';
    link.textContent = de ? 'Einstellungen und Wiederherstellung' : 'Settings and recovery';
    link.addEventListener('click', () => document.querySelector('[data-bk-open-settings]')?.click());
    box.replaceChildren(message, details, link);
  }
  async function updateNotice() {
    try {
      const response = await fetch('/api/operations/status', {credentials:'same-origin', cache:'no-store'});
      if (response.ok) {
        status = await response.json();
        renderNotice();
      }
    } catch (_) {}
    if (status && !status.writes_allowed && startupOnly(status)) setTimeout(updateNotice, 1500);
  }
  window.addEventListener('bk-language-changed', renderNotice);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', updateNotice);
  else updateNotice();
})();</script>'''


def trash_catalogue(registry):
    """Recorded trash rows only; never infer physical ownership or auto-adopt."""
    entries=[]
    for library in rows(registry,'SELECT library_id,database_path FROM libraries WHERE COALESCE(is_registered,1)=1'):
        for item in rows(library['database_path'],"SELECT id,current_relative_path,size_bytes,sha256_current,sha256_original FROM files WHERE current_root_kind='trash'"):
            relative=item['current_relative_path']
            entries.append({'entry_type':'file','relative_path':relative,'filename':Path(relative).name,
                'size_bytes':item['size_bytes'],'tracked':True,'library_id':library['library_id'],
                'sha256':item['sha256_current'] or item['sha256_original'],'physical_state':'not_verified'})
    return {'entries':entries,'file_count':len(entries),'entry_count':len(entries),
        'directory_count':0,'total_size_bytes':sum(r['size_bytes'] for r in entries),
        'tracked_file_count':len(entries),'untracked_file_count':0,'adopted_file_count':0,
        'exact_file_count':0,'ambiguous_file_count':0,'read_only':True,
        'inventory_mode':'recorded_only_unverified_physical_state',
        'restore_active':False,'deletion_blocked':True,'restore_conflicts':[],
        'restore_failures':[{'status':'blocked','message':'Operation recovery required; catalogue view only.'}]}
