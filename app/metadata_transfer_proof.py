"""Read-only General -> central-stock continuity, never a filename/hash search.

Only an exact completed admission/job/manifest/move-journal/catalogue/immutable
origin chain can substitute for a now absent General output. No media is moved.
"""
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3

from app import root_operations as ro


def fail(reason,path):
    raise ro.RootOperationError('metadata_transfer_'+reason+': '+str(path))


def rows(database,sql,args=()):
    database=Path(database).absolute()
    if not database.is_file() or database.is_symlink():fail('database_unavailable',database)
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('BEGIN')
        return [dict(r) for r in c.execute(sql,args)]


def canonical(value):
    from app.import_recovery import relative
    result=relative(value)
    if result!=value:fail('noncanonical_path',value)
    return result


def timestamp(value):
    try:
        d=datetime.fromisoformat(value)
        if d.tzinfo is None:raise ValueError()
        return d
    except (TypeError,ValueError):fail('timestamp_invalid',value)


def _qualify(task,record,owner,registry,logs):
    from app.library_registry import get_library,read_library_identity
    from app.storage_config import storage_paths
    from app.import_recovery import read_record
    from app.global_library_inventory import family_content_fingerprint
    from app.metadata_abort_recovery import _source_proof
    registry=Path(registry).absolute();workspace=Path(record['workspace'])
    main=get_library(registry,'main',active_only=False)
    if not main or not main.get('is_registered') or main['workspace_root']!=str(workspace):fail('main_authority',registry)
    database=Path(main['database_path'])
    if read_library_identity(database)!='main':fail('database_identity',database)
    central=storage_paths(workspace)['backup_root'].absolute()
    if record['bindings'].get(str(central))!=ro._identity(central):fail('central_binding',central)
    metadata=storage_paths(workspace)['metadata_root'].absolute()
    source_relative=canonical(task['source_relative_path']);sha=task['output_sha256'];size=task['output_size_bytes']
    candidates=[]
    for job in rows(database,"SELECT * FROM jobs WHERE operation='metadata_general_import' ORDER BY id"):
        try:result=json.loads(job['result_json'] or '{}')
        except (ValueError,TypeError):fail('job_result_invalid',job['id'])
        imported=(result.get('organization') or {}).get('imported_source_files') or []
        matches=[e for e in imported if e.get('relative_path')==source_relative and e.get('sha256')==sha and e.get('size_bytes')==size]
        if not matches:continue
        if len(matches)!=1:fail('ambiguous_import_member',job['id'])
        candidates.append((job,result))
    if len(candidates)!=1:fail('admission_missing_or_ambiguous',task['source_path'])
    job,result=candidates[0];job_id=job['id'];stage=metadata/'.general-import'/job_id
    if job['state']!='completed' or job['source_path']!=str(stage) or not result['organization'].get('verified'):
        fail('job_not_completed_or_bound',job_id)
    if timestamp(job['created_at'])<timestamp(task['completed_at']) or timestamp(job['finished_at'])<timestamp(job['created_at']):fail('job_predates_correction',job_id)
    protocol=Path(logs).absolute()/'backups'/job_id
    if (result.get('outputs') or {}).get('protocol')!=str(protocol):fail('protocol_path',job_id)
    manifest=read_record(protocol/'manifest.json');journal=read_record(protocol/'move-journal.json');status=read_record(protocol/'status.json')
    if (manifest.get('schema_version')!=3 or manifest.get('job_id')!=job_id or manifest.get('simulation') is not False
        or manifest.get('source_path')!=str(stage) or manifest.get('import_mode')!='folder'
        or manifest.get('source_signature')!=job['source_signature'] or manifest.get('source_fingerprint')!=job['source_fingerprint']):fail('manifest_identity',protocol)
    if manifest.get('already_imported_file_count') or manifest.get('already_imported_files'):fail('duplicate_admission_not_qualified',job_id)
    entries=manifest.get('files');selection=[]
    if not isinstance(entries,list) or not entries:fail('manifest_empty',protocol)
    for e in entries:
        rel=canonical(e['relative_path'])
        if type(e['size_bytes']) is not int or not isinstance(e['sha256'],str):fail('manifest_member',protocol)
        selection.append((rel,e['size_bytes'],e['sha256']))
    if len({x[0] for x in selection})!=len(selection) or len(entries)!=manifest.get('file_count'):fail('manifest_members_ambiguous',protocol)
    from app.folder_import import manifest_fingerprint
    if manifest.get('total_source_file_count')!=len(entries) or manifest_fingerprint(entries)!=job['source_fingerprint']:fail('manifest_fingerprint',protocol)
    expected='GENERAL_IMPORT_'+hashlib.sha256(json.dumps([owner['library_id'],sorted(selection)],ensure_ascii=False).encode()).hexdigest()[:32]
    if (source_relative,size,sha) not in selection:fail('admission_identity',job_id)
    admission_kind='selection_sha256'
    if job_id!=expected:
        # RC14 recorded a timestamp queue ID, not a hash selection ID. It is
        # accepted only with the full copy/publication/origin chain below and
        # a Main authority; the timestamp alone authorizes nothing.
        if owner['library_id']!='main' or not re.fullmatch(r'GENERAL_IMPORT_[0-9]{8}_[0-9]{6}_[0-9]{6}',job_id):fail('admission_identity',job_id)
        try:admitted=datetime.strptime(job_id,'GENERAL_IMPORT_%Y%m%d_%H%M%S_%f').replace(tzinfo=timestamp(job['created_at']).tzinfo)
        except ValueError:fail('legacy_admission_timestamp',job_id)
        if not timestamp(task['completed_at'])<=admitted<=timestamp(job['created_at']):fail('legacy_admission_timestamp',job_id)
        admission_kind='legacy_verified_copy_chain'
    if status.get('job_id')!=job_id or status.get('state')!='success' or status.get('stage')!='completed' or status.get('source_path')!=str(stage):fail('protocol_incomplete',protocol)
    if status.get('organization')!=result.get('organization'):fail('protocol_result_mismatch',protocol)
    if journal.get('format')!=1 or journal.get('root')!=str(central):fail('publication_root',protocol)
    items=journal.get('files');matches=[e for e in items or [] if e.get('source_relative_path')==source_relative]
    if len(matches)!=1:fail('publication_member_ambiguous',protocol)
    if not isinstance(items,list) or len({e.get('source_relative_path') for e in items})!=len(items) or len({e.get('destination_relative_path') for e in items})!=len(items):fail('publication_plan_ambiguous',protocol)
    imported=result['organization'].get('imported_source_files') or []
    mapping=lambda seq,field:sorted((e[field],e['size_bytes'],e['sha256']) for e in seq)
    if len(items)!=result['organization'].get('file_count') or mapping(items,'source_relative_path')!=mapping(imported,'relative_path'):fail('publication_plan_result',protocol)
    item=matches[0];dest=canonical(item['destination_relative_path'])
    if item.get('sha256')!=sha or item.get('size_bytes')!=size:fail('publication_fingerprint',protocol)
    catalogue=rows(database,"SELECT f.*,ff.family_key FROM files f JOIN file_families ff ON ff.id=f.family_id AND ff.job_id=f.job_id WHERE f.job_id=? AND f.original_relative_path=?",(job_id,source_relative))
    if len(catalogue)!=1:fail('catalogue_member_ambiguous',job_id)
    file=catalogue[0]
    if (file['sha256_original']!=sha or file['sha256_current']!=sha or file['size_bytes']!=size
        or (file['source_size_bytes'] if file['source_size_bytes'] is not None else file['size_bytes'])!=size
        or file['current_relative_path']!=dest or file['current_root_kind']!='shared_workspace'):
        fail('catalogue_fingerprint_or_location',job_id)
    key='main:'+job_id+':'+file['family_key']
    origins=rows(registry,"""SELECT sf.*,cf.content_fingerprint,sb.source_kind,sb.source_identity,sb.backup_path,sb.metadata_json AS backup_metadata
      FROM source_families sf JOIN canonical_families cf USING(canonical_family_id) JOIN source_backups sb USING(backup_id) WHERE sf.source_family_key=?""",(key,))
    if len(origins)!=1:fail('origin_missing',key)
    origin=origins[0]
    if origin['backup_id']!='main:'+job_id or origin['backup_path']!=str(stage) or origin['source_kind']!='import' or origin['source_identity']!=job['source_signature']:fail('origin_identity',key)
    for value in (origin['metadata_json'],origin['backup_metadata']):
        meta=json.loads(value)
        if meta.get('library_id')!='main' or meta.get('job_id')!=job_id:fail('origin_metadata',key)
    members=rows(registry,'SELECT m.* FROM source_media m JOIN source_family_members fm USING(media_id) WHERE fm.source_family_key=? ORDER BY fm.member_order',(key,))
    family=rows(database,'SELECT * FROM files WHERE job_id=? AND family_id=? ORDER BY original_relative_path',(job_id,file['family_id']))
    signature=lambda seq:sorted((r['relative_path'],r['sha256'],r['size_bytes'],r['media_type']) for r in seq)
    live=[{'relative_path':f['original_relative_path'],'sha256':f['sha256_original'],'size_bytes':f['source_size_bytes'] if f['source_size_bytes'] is not None else f['size_bytes'],'media_type':f['media_type']} for f in family]
    if not members or any(m['backup_id']!=origin['backup_id'] for m in members) or signature(members)!=signature(live) or family_content_fingerprint(members)!=origin['content_fingerprint']:fail('immutable_membership',key)
    destination=central/dest
    if destination.resolve()!=destination:fail('target_symlink',destination)
    try:proof=_source_proof(destination,size,sha)
    except FileNotFoundError:fail('target_missing',destination)
    except OSError as error:fail('target_unavailable',str(destination)+' · '+str(error))
    if proof['identity']!=item.get('inode'):fail('publication_inode',destination)
    if os.path.lexists(stage/source_relative):fail('staging_member_remains',stage/source_relative)
    return dict(proof,transfer={'format':1,'kind':'qualified_general_import','admission_kind':admission_kind,'job':job,'file':file,
       'original_general_path':task['output_path'],'protocol':str(protocol),
       'manifest_canonical_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
       'publication_canonical_sha256':hashlib.sha256(json.dumps(journal,sort_keys=True).encode()).hexdigest(),
       'status_canonical_sha256':hashlib.sha256(json.dumps(status,sort_keys=True).encode()).hexdigest(),
       'source_family_key':key,'canonical_family_id':origin['canonical_family_id'],
       'origin_members':members})


def qualify(task,record,owner,registry,logs):
    try:return _qualify(task,record,owner,registry,logs)
    except ro.RootOperationError:raise
    except Exception as error:fail('evidence_unreadable',str(task.get('source_path'))+' · '+str(error))
