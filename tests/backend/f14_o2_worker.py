"""Synthetic O2 process barriers and an independent same-UID writer."""
from pathlib import Path
import json,os,signal,sys
case=Path(sys.argv[1]);control=Path(sys.argv[2]);action=sys.argv[3];ws=case/'workspace'
def stop(label):
    with (control/'checkpoint.json').open('w') as f:
        json.dump({'pid':os.getpid(),'boundary':label},f);f.flush();os.fsync(f.fileno())
    os.kill(os.getpid(),signal.SIGSTOP)
if action in {'before-denial','after-denial'}:
    from app import main
    from app.library_context import resolve_library_context
    main.WORKSPACE_PATH=ws;main.DATABASE_FILE=case/'main.sqlite3';main.REGISTRY_DATABASE_FILE=case/'registry.sqlite3';main.CONFIG_PATH=case/'settings.json'
    main.MAIN_LIBRARY_CONTEXT=resolve_library_context(main.REGISTRY_DATABASE_FILE,'main')
    actual=main._set_storage_paths
    def barrier(payload):
        if action=='before-denial':stop('after-api-preflight-before-refusal')
        return actual(payload)
    main._set_storage_paths=barrier
    try:main.api_set_storage_paths({'workspaces_directory_name':'ChangedWork'})
    except main.HTTPException as e:answer={'status':e.status_code,'detail':e.detail}
    else:raise AssertionError('Unattested rename was accepted')
    (control/'answer.json').write_text(json.dumps(answer,indent=2))
    if action=='after-denial':stop('after-refusal-no-mutation')
else:
    external=case/'external';external.mkdir();(external/'original.JPG').write_bytes(b'synthetic-foreign')
    if action.startswith('source-'):
        (ws/'Arbeitsbereiche').rename(ws/'retained-source')
        if action=='source-dir':(ws/'Arbeitsbereiche').mkdir();(ws/'Arbeitsbereiche/foreign.JPG').write_bytes(b'synthetic-foreign')
        else:(ws/'Arbeitsbereiche').symlink_to(external,target_is_directory=True)
    elif action=='parent-dir':
        ws.rename(case/'retained-workspace');ws.mkdir();(ws/'Arbeitsbereiche').mkdir();(ws/'Arbeitsbereiche/foreign.JPG').write_bytes(b'synthetic-foreign')
    elif action=='target-dir':(ws/'ChangedWork').mkdir();(ws/'ChangedWork/foreign.JPG').write_bytes(b'synthetic-foreign')
    elif action=='target-symlink':(ws/'ChangedWork').symlink_to(external,target_is_directory=True)
    else:raise AssertionError(action)
    (control/'external.json').write_text(json.dumps({'uid':os.geteuid(),'pid':os.getpid(),'action':action},indent=2))
