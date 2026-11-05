"""Authenticated diagnostic view. Read-only, never a release authorization."""
from pathlib import Path
from app import root_operations as ro
from app.metadata_transfer_proof import rows


def inspect(workspace,registry):
    from app.storage_bootstrap import key_for
    workspace=Path(workspace).absolute();parent=ro._control_location(workspace)
    report={'mode':'authenticated_read_only','operations_allowed':False,'libraries':[], 'operations':[], 'errors':[]}
    try:
        report['libraries']=rows(registry,'SELECT library_id,display_name,database_path,workspace_root,work_root,archive_root,is_registered FROM libraries ORDER BY library_id')
    except Exception as error:report['errors'].append({'path':str(registry),'reason':str(error)})
    owners={r['library_id']:r for r in report['libraries'] if r['is_registered']}
    for path in sorted(parent.glob('operation-*.json')):
        item={'path':str(path),'scope':'storage_or_unknown','authorized_to_finish':False}
        try:
            record=ro._read(path)
            if path.name!='operation-'+key_for(record)+'.json':raise ValueError('operation filename/key mismatch')
            item.update({k:record.get(k) for k in ('reservation_id','kind','library','generation','ids')})
            owner=owners.get(record.get('library'))
            if owner is not None and record.get('kind')=='metadata':
                from app.metadata_abort_recovery import EXECUTE,APPLY,_binding,_task
                ids=record.get('ids',{})
                if ids.get('function') in (EXECUTE,APPLY):
                    # Positive classification needs unchanged roots and an exact
                    # task. No current hash/transfer proof is inferred here.
                    _binding(record,owner)
                    task,_=_task(record,owner,parent)
                    item.update(scope='single_file_requires_qualification',task={k:task[k] for k in (
                        'id','area','status','source_path','source_relative_path','source_size_bytes','source_sha256',
                        'output_path','output_size_bytes','output_sha256','completed_at','error_message')})
                    item['source_present']=Path(task['source_path']).exists()
                    item['output_present']=bool(task['output_path'] and Path(task['output_path']).exists())
        except Exception as error:item['reason']=str(error)
        report['operations'].append(item)
    return report
