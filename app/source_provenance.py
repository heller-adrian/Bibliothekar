"""Validate immutable origin against live inventory and explicit loss evidence.

This is a read-only qualification, not a repair of the source registry. F14 owns
startup exclusion. A missing member is never inferred from the filesystem alone.
"""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from app.database import database_connection
from app.library_registry import LibraryRegistryError


def registry_origins(path: Path, library_id: str):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as c:
        c.row_factory=sqlite3.Row
        c.execute('BEGIN')
        families=[]
        for row in c.execute('''SELECT sf.*,cf.content_fingerprint,sb.source_identity,sb.source_kind,sb.backup_path
             FROM source_families sf JOIN canonical_families cf USING(canonical_family_id)
             JOIN source_backups sb ON sb.backup_id=sf.backup_id ORDER BY source_family_key'''):
            data=dict(row)
            # Namespace selection is exact; metadata must independently agree.
            if not (data['source_family_key'].startswith(library_id+':') or data['backup_id'].startswith(library_id+':')):continue
            data['members']=[dict(m) for m in c.execute('''SELECT m.* FROM source_media m
                JOIN source_family_members fm USING(media_id) WHERE fm.source_family_key=?
                ORDER BY fm.member_order,m.relative_path''',(data['source_family_key'],))]
            families.append(data)
        return families


def _conflict(source, reason):
    raise LibraryRegistryError('source_inventory_conflict: '+source+': '+reason)


def qualify_origins(registry_path, database_path, library_id, grouped, fingerprint):
    origins=registry_origins(Path(registry_path).absolute(),library_id)
    if not origins:return set()
    with database_connection(database_path) as c:
        audit=[dict(r) for r in c.execute('''SELECT * FROM audit_log WHERE entity_type='file'
            AND action IN ('central_file_deletion_confirmed','manual_file_deletion_confirmed',
                           'trash_file_permanently_deleted') ORDER BY id''')]
        jobs={str(r['id']):dict(r) for r in c.execute('SELECT * FROM jobs')}
    qualified=set()
    for origin in origins:
        source=origin['source_family_key']
        try: meta=json.loads(origin['metadata_json'])
        except (ValueError,TypeError):_conflict(source,'invalid origin metadata')
        if not isinstance(meta,dict):_conflict(source,'invalid origin metadata')
        job=str(meta.get('job_id') or '')
        family=str(origin['family_key'])
        if (meta.get('library_id')!=library_id or not job
            or source!=f'{library_id}:{job}:{family}' or origin['backup_id']!=f'{library_id}:{job}'):
            _conflict(source,'origin namespace mismatch')
        # Deleted backup jobs retain their source history; they are not projected
        # into live inventory. Backup deletion has its own F14 recovery protocol.
        if job not in jobs:
            _conflict(source,'missing import job')
        job_row=jobs[job]
        identity=str(job_row.get('source_signature') or job_row.get('source_fingerprint')
                     or job_row.get('source_device_id') or job_row.get('source_path') or job)
        attempt=f"reimport:{job}:{identity}" if job_row.get('duplicate_of_job_id') else identity
        expected_identity=attempt if library_id=='main' else f'{library_id}:{attempt}'
        if (origin['source_identity']!=expected_identity
            or origin['source_kind']!=('import' if library_id=='main' else 'existing_library')
            or origin['backup_path']!=str(job_row.get('source_path') or job)):
            _conflict(source,'backup source identity, kind or path changed')
        live=grouped.get((job,family),[])
        members=origin['members']
        # A crash during first registration may leave the exact canonical family
        # before all member inserts. Only the complete original fingerprint can
        # authorize completion of that registration, never a shortened inventory.
        if not members:
            if live and fingerprint(live)==origin['content_fingerprint']:continue
            if not live and _unfinished_import(registry_path,database_path,library_id,job,job_row):
                # Retain the exact incomplete origin. No membership/claim is
                # completed here; the original import reservation stays open.
                continue
            _conflict(source,'origin members missing')
        if fingerprint(members)!=origin['content_fingerprint']:
            _conflict(source,'canonical fingerprint disagrees with origin members')
        known={m['relative_path']:m for m in members}
        if len(known)!=len(members):_conflict(source,'ambiguous origin paths')
        present=set()
        for row in live:
            rel=str(row['original_relative_path'])
            old=known.get(rel)
            if old is None or rel in present:_conflict(source,'unknown or duplicate live member: '+rel)
            if (str(row['sha256_original']).lower()!=str(old['sha256']).lower()
                or int(row['size_bytes'])!=int(old['size_bytes'])
                or str(row['media_type'] or '')!=str(old['media_type'] or '')):
                _conflict(source,'live member hash, size or type changed: '+rel)
            present.add(rel)
        evidence=Counter()
        reference=meta.get('projection_origin')
        projected_missing=meta.get('projected_missing_members',[])
        if reference:
            if library_id=='main' or reference!=f'main:{job}:{family}':_conflict(source,'invalid projection origin')
            from app.library_registry import get_library
            from app.global_library_inventory import _database_family_rows
            main=get_library(registry_path,'main',active_only=False)
            if main is None:_conflict(source,'projection authority missing')
            main_db=Path(main['database_path'])
            groups={}
            for row in _database_family_rows(main_db):groups.setdefault((str(row['job_id']),str(row['family_key'])),[]).append(row)
            qualify_origins(registry_path,main_db,'main',groups,fingerprint)
            authority=next((o for o in registry_origins(Path(registry_path).absolute(),'main') if o['source_family_key']==reference),None)
            if authority is None or authority['canonical_family_id']!=origin['canonical_family_id']:
                _conflict(source,'projection canonical origin changed')
            def member_signature(items):
                return sorted((m['relative_path'],m['sha256'],m['size_bytes'],m['media_type']) for m in items)
            if member_signature(authority['members'])!=member_signature(members):
                _conflict(source,'projection member origin changed')
            authority_members={m['media_id']:m for m in authority['members']}
            for media_id in projected_missing:
                member=authority_members.get(media_id)
                if member is None or member['relative_path'] not in known:_conflict(source,'unknown projected loss')
                evidence[member['relative_path']]+=1
        elif projected_missing:_conflict(source,'projection loss has no authority')
        for entry in audit:
            if str(entry['job_id'] or '')!=job:continue
            try:data=json.loads(entry['details_json'])
            except (ValueError,TypeError):continue
            if not isinstance(data,dict):continue
            if data.get('library_id',library_id)!=library_id:continue
            if any(str(row.get('file_id'))==str(entry['entity_id']) for row in live):continue
            if live and data.get('family_id') is not None and any(
                int(row.get('family_id',data['family_id']))!=int(data['family_id']) for row in live):continue
            if entry['action']!='trash_file_permanently_deleted':
                if data.get('family_key')!=family or int(data.get('confirmed_after_scans') or 0)<2:continue
            elif data.get('family_key',family)!=family:continue
            sha=str(data.get('sha256_original') or data.get('sha256') or '').lower()
            if entry['action']=='trash_file_permanently_deleted' and not data.get('family_key'):
                matching=[(o['source_family_key'],m['relative_path']) for o in origins
                          if o['backup_id']==origin['backup_id'] for m in o['members']
                          if str(m['sha256']).lower()==sha]
                if len(matching)!=1:continue
            candidates=[m for m in members if str(m['sha256']).lower()==sha]
            rel=data.get('original_relative_path')
            if rel:candidates=[m for m in candidates if m['relative_path']==rel]
            # RC12 lacks original paths in loss audits. Accept only a unique
            # hash within this exact job/family, with the existing two-scan proof.
            if len(candidates)!=1:continue
            item=candidates[0]
            if data.get('source_size_bytes') is not None and int(data['source_size_bytes'])!=int(item['size_bytes']):continue
            evidence[item['relative_path']]+=1
        for rel in known.keys()-present:
            if not evidence[rel]:_conflict(source,'missing member has no matching confirmed loss: '+rel)
        qualified.add((job,family))
    return qualified


def projection_origin(registry_path, database_path, library_id, job, family, current):
    """A new projection copies an already qualified origin, never invents one.

    The exact set absent at projection time is recorded as a reference to the
    original main loss evidence. This cannot excuse later unaudited local loss.
    """
    if library_id=='main':return None
    from app.library_registry import get_library
    from app.global_library_inventory import _database_family_rows, family_content_fingerprint
    main=get_library(registry_path,'main',active_only=False)
    if main is None:return None
    main_db=Path(main['database_path'])
    if main_db.resolve()==Path(database_path).resolve():_conflict(f'{library_id}:{job}:{family}','projection database aliases main')
    candidates=registry_origins(Path(registry_path).absolute(),'main')
    origin=next((o for o in candidates if o['source_family_key']==f'main:{job}:{family}'),None)
    if origin is None:return None
    groups={}
    for row in _database_family_rows(main_db):groups.setdefault((str(row['job_id']),str(row['family_key'])),[]).append(row)
    qualify_origins(registry_path,main_db,'main',groups,family_content_fingerprint)
    def signature(rows):
        return sorted((str(r['original_relative_path']),str(r['sha256_original']),int(r['size_bytes']),str(r['media_type'] or '')) for r in rows)
    if signature(current)!=signature(groups.get((job,family),[])):
        _conflict(f'{library_id}:{job}:{family}','new projection differs from authoritative main inventory')
    present={r['original_relative_path'] for r in current}
    return {**origin,'projected_missing_members':[m['media_id'] for m in origin['members'] if m['relative_path'] not in present]}


def _unfinished_import(registry_path,database_path,library_id,job,job_row):
    """Recognize, without authorizing or completing, an interrupted publication."""
    if library_id!='main' or job_row.get('state') not in {
        'queued','copying','verifying','backup_verified','analyzing_metadata','organizing','interrupted'}:
        return False
    from app.library_registry import get_library
    from app.root_operations import _control_location,_read,_identity
    from app.storage_bootstrap import key_for
    library=get_library(registry_path,library_id,active_only=False)
    if library is None:return False
    workspace=Path(library['workspace_root'])
    parent=_control_location(workspace)
    state=_read(parent/'state.json',{})
    if state.get('format') not in (1,2,3) or state.get('workspace')!=_identity(workspace):return False
    with database_connection(database_path) as c:
        if c.execute('SELECT 1 FROM files WHERE job_id=? LIMIT 1',(job,)).fetchone():return False
    for path in parent.glob('operation-*.json'):
        record=_read(path,{})
        if record.get('kind')!='import' or record.get('ids')!={'function':'app.main.process_claimed_job','job_id':job}:continue
        nonce=record.get('reservation_id','')
        if (record.get('format')!=1 or record.get('library')!=library_id
            or record.get('workspace')!=str(workspace) or record.get('database')!=str(Path(database_path).absolute())
            or record.get('generation')!=[state.get('generation'),state.get('libraries',{}).get(library_id,0)]
            or len(nonce)!=32 or any(ch not in '0123456789abcdef' for ch in nonce)
            or path.name!='operation-'+key_for(record)+'.json'):
            return False
        if (parent/('finished-'+nonce+'.json')).exists():return False
        bindings=record.get('bindings',{})
        if bindings.get(str(workspace))!=_identity(workspace):return False
        if any(identity is not None and (state.get('bindings',{}).get(p)!=identity or _identity(p)!=identity)
               for p,identity in bindings.items()):return False
        return True
    return False
