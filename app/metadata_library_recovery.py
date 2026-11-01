"""Replay one original, pre-commit library swap with its complete frozen family.

No SQL end status or missing journal authorizes completion. A private plan keeps
its original journal/task/nonce across crashes during journal cleanup. Unsupported
multiple/reintegration and committed swaps retain their separate effect fences.
"""
from pathlib import Path
from contextlib import closing
import hashlib,json,os,stat
from app import root_operations as ro,operation_health as health

FUNCTION='app.metadata_correction.apply_metadata_correction'


def refuse(reason):raise health.DomainStartupError('library_metadata_recovery_'+reason)


def qualify(record,owner,parent,metadata):
    from app.metadata_abort_recovery import _binding,_task_rows
    from app.metadata_swap_recovery import _validate,_database_state,_preflight_rollback
    from app.import_recovery import read_record
    def load(path):
        data=read_record(path);_validate(path,data,metadata);return data
    from app.storage_config import storage_paths
    from app.database_diagnostics import inspect
    _binding(record,owner)
    database=Path(owner['database_path']);diagnosis=inspect(database)
    if not diagnosis['consistent'] or not diagnosis['schema_current']:refuse('database_not_qualified')
    task_id=record['ids'].get('correction_id')
    if record['ids']!={'function':FUNCTION,'correction_id':task_id} or not isinstance(task_id,str):refuse('original_key_mismatch')
    rows=_task_rows(database,'id=?',(task_id,))
    if len(rows)!=1 or rows[0]['area']!='library' or rows[0]['status'] not in {'prepared','writing','blocked'}:
        refuse('original_task_not_precommit_library')
    task=rows[0];frozen=json.loads(task['detected_json']);members=frozen.get('members')
    if not isinstance(members,list) or not members:refuse('frozen_family_missing')
    prior=ro._read(parent/('library-metadata-plan-'+record['reservation_id']+'.json'),None)
    directory=metadata/'.swap-journals'
    if directory.is_symlink() or not directory.is_dir() or directory.resolve()!=directory:refuse('journal_directory_unavailable')
    journals=list(directory.iterdir())
    if prior is None:
        if len(journals)!=1:refuse('journal_scope_ambiguous')
        journal=journals[0];data=load(journal)
    else:
        if prior.get('format')!=1 or prior.get('reservation')!=record:refuse('private_plan_mismatch')
        journal=Path(prior['journal']);data=prior['swap']
        _validate(journal,data,metadata)
        if journals and (journals!=[journal] or load(journal)!=data):refuse('journal_changed_after_plan')
        stable={k:v for k,v in task.items() if k not in {'status','updated_at','error_message'}}
        if prior.get('task')!=stable:refuse('frozen_task_changed')
    central=storage_paths(Path(owner['workspace_root']))['backup_root'].absolute()
    if (data['kind']!='library' or data['state']!='prepared' or data['database']!=str(database)
        or data['task_id']!=task_id or data['family_id']!=frozen.get('family_id')
        or data['proposed']!=task['proposed_datetime'] or data['root']!=str(central)):
        refuse('journal_not_original_library_task')
    by_id={m.get('file_id',m.get('id')):m for m in members}
    if len(by_id)!=len(members) or {i['file_id'] for i in data['files']}!=set(by_id) or len(data['files'])!=len(members):
        refuse('incomplete_original_family')
    with closing(health.read_connection(database)) as c:
        family=c.execute('SELECT * FROM file_families WHERE id=?',(data['family_id'],)).fetchone()
        current=[dict(r) for r in c.execute('SELECT * FROM files WHERE family_id=?',(data['family_id'],))]
    if (family is None or family['job_id']!=frozen.get('job_id') or family['family_key']!=frozen.get('family_key')
        or {r['id'] for r in current}!=set(by_id)):refuse('family_identity_changed')
    work=metadata/'.work'/task_id;expected_work={}
    from app.metadata_correction import _safe_relative
    for item in data['files']:
        member=by_id[item['file_id']];row=next(r for r in current if r['id']==item['file_id'])
        relative=_safe_relative(member['current_relative_path'])
        if (item['source']!=str(central/relative) or member['family_id']!=data['family_id']
            or member['job_id']!=frozen['job_id']
            or item['before_sha']!=(member.get('sha256_current') or member.get('sha256_original'))
            or any(row[k]!=member[k] for k in ('job_id','family_id','original_relative_path','current_relative_path','current_root_kind','size_bytes','sha256_original','sha256_current'))):
            refuse('catalogue_or_frozen_member_changed')
        expected_work[work/_safe_relative(member['original_relative_path'])]=item['after_sha']
        for name in ('source','backup','incoming'):
            path=Path(item[name])
            if os.path.lexists(path):
                info=path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or path.resolve()!=path:
                    refuse('unsafe_file_identity: '+str(path))
        # The old library executor owns its auxiliary corrected work copy;
        # retain it, but never qualify an injected copy as disposable work.
    if work.exists() or work.is_symlink():
        if work.is_symlink() or not work.is_dir() or work.resolve()!=work:refuse('unsafe_work_root')
        for path in work.rglob('*'):
            if path.is_symlink():refuse('unsafe_work_entry')
            if path.is_dir():
                if not any(p.is_relative_to(path) for p in expected_work):refuse('unknown_work_directory')
            elif (path not in expected_work or not path.is_file() or path.stat().st_nlink!=1
                  or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_work[path]):
                refuse('unknown_work_bytes')
    if _database_state(data)!='prepared':refuse('commit_requires_separate_proof')
    _preflight_rollback(data)
    if not journals:
        if task['status']!='blocked':refuse('missing_journal_without_verified_task_rollback')
        for item in data['files']:
            if (not Path(item['source']).is_file() or hashlib.sha256(Path(item['source']).read_bytes()).hexdigest()!=item['before_sha']
                or any(os.path.lexists(item[k]) for k in ('backup','incoming'))):refuse('incomplete_retained_plan_rollback')
    stable={k:v for k,v in task.items() if k not in {'status','updated_at','error_message'}}
    plan={'format':1,'reservation':record,'journal':str(journal),'swap':data,'task':stable}
    if prior is not None and prior!=plan:refuse('private_plan_changed')
    return journal,plan


def recover(workspace):
    from app.metadata_abort_recovery import _owner,_binding
    from app.metadata_swap_recovery import metadata_write_guard,recover_swap_journal
    from app.storage_config import storage_paths
    from app.storage_anchors import check_active
    status=health.inspect(workspace);dead=[r for r in status['reservations'] if not r['live']]
    if (len(dead)!=1 or any(r['live'] for r in status['reservations']) or not dead[0]['qualified']
        or dead[0].get('kind')!='metadata' or dead[0].get('ids',{}).get('function')!=FUNCTION):return False
    item=dead[0];record=ro._read(Path(item['path']));owner=_owner(record['database'])
    if not owner:return False
    # General APPLY is handled by the existing stronger General qualifier.
    from app.metadata_abort_recovery import _task_rows
    task=_task_rows(record['database'],'id=?',(record['ids'].get('correction_id'),))
    if len(task)!=1 or task[0]['area']!='library':return False
    parent,_=_binding(record,owner);check_active(workspace,parent)
    metadata=storage_paths(Path(workspace))['metadata_root']
    with metadata_write_guard(metadata):
        journal,plan=qualify(record,owner,parent,metadata)
        stored=parent/('library-metadata-plan-'+record['reservation_id']+'.json')
        if not stored.exists():ro._write(stored,plan)
        intent=parent/('domain-recovery-intent-'+record['reservation_id']+'.json')
        material={'format':1,'reservation':record,'phase':'qualified_recovery_not_finished'}
        old=ro._read(intent,None)
        if old is not None and old!=material:refuse('intent_changed')
        if old is None:ro._write(intent,material)
        with health.qualified_retry(workspace,{item['path']}):
            with ro.reserve(workspace,library_id=record['library'],database=record['database'],kind='metadata',
                            ids=record['ids'],paths=[Path(p) for p in record['bindings']],
                            expected_generation=record['generation'],_recovery_record=record):
                journal,confirmed=qualify(record,owner,parent,metadata)
                if confirmed!=plan:refuse('plan_changed_under_original_lock')
                if journal.exists():
                    if recover_swap_journal(metadata,journal,allowed_databases={Path(record['database'])})!='rolled_back':
                        refuse('unexpected_outcome')
                qualify(record,owner,parent,metadata)
                receipt=parent/('library-metadata-outcome-'+record['reservation_id']+'.json')
                outcome={'format':1,'reservation':record,'plan':plan,'disposition':'verified_original_library_swap_rolled_back'}
                old=ro._read(receipt,None)
                if old is not None and old!=outcome:refuse('outcome_changed')
                ro._check(record['bindings']);check_active(workspace,parent)
                if old is None:ro._write(receipt,outcome)
            health.finish_qualified_retry(workspace)
    return True
