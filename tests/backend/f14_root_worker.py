"""Short-lived synthetic F14 probe, used only by backend regression tests."""
from pathlib import Path
import hashlib,json,os,signal,sys,time
from app import root_operations as ro

workspace=Path(sys.argv[1]);control=Path(sys.argv[2]);action=sys.argv[3]

def stop(label):
    path=control/'checkpoint.json'
    with path.open('w') as f:
        json.dump({'pid':os.getpid(),'boundary':label},f);f.flush();os.fsync(f.fileno())
    os.kill(os.getpid(),signal.SIGSTOP)
    raise AssertionError('Stopped probe resumed')

if action.startswith('reserve-live-'):
    from app.storage_config import storage_paths
    from app.safe_transfer import move_verified_no_overwrite
    library=action.removeprefix('reserve-live-');work=storage_paths(workspace)['workspaces_root']/library
    source=workspace/('staged-'+library+'.JPG');target=work/'moved.JPG'
    with ro.reserve(workspace,library_id=library,paths=[work],kind='synthetic-file-operation',ids={'job':library}):
        with (control/'checkpoint.json').open('w') as f:json.dump({'pid':os.getpid(),'boundary':'reserved-before-real-transfer'},f);f.flush();os.fsync(f.fileno())
        until=time.monotonic()+20
        while not (control/'continue').exists():
            if time.monotonic()>until:raise RuntimeError('Synthetic probe timed out')
            time.sleep(.01)
        ro.validate_active_roots()
        move_verified_no_overwrite(source,target,expected_size=source.stat().st_size,expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
elif action=='reserve-shared':
    with ro.reserve(workspace,library_id='main',paths=[workspace],kind='backup'):
        stop('shared-reservation-durable')
elif action=='reserve':
    with ro.reserve(workspace,library_id='main',paths=[workspace],kind='synthetic-reservation'):
        stop('reservation-persisted-before-filesystem-operation')
elif action.startswith('mutation-'):
    # Generic mutation crash proof uses a library archive namespace; managed
    # storage names no longer have any physical rename implementation.
    source=workspace.parent/'archive-main';target=workspace.parent/'archive-main-moved'
    assert source.is_dir() and not target.exists()
    real=ro._write
    def write(path,value):
        real(path,value)
        if action=='mutation-intent' and path.name=='mutation.json':stop('root-intent-durable')
        if action=='mutation-after-state' and path.name=='state.json':stop('generation-durable-before-intent-cleanup')
    ro._write=write
    with ro.mutate(workspace,changed_paths={source:target}):
        source.rename(target)
        if action=='mutation-after-rename':stop('root-renamed-before-generation-commit')
elif action=='reserve-finished':
    real=ro._write
    def finished(path,value):
        real(path,value)
        if path.name.startswith('finished-'):stop('completion-receipt-durable-before-reservation-removal')
    ro._write=finished
    with ro.reserve(workspace,library_id='main',paths=[workspace],kind='completion-proof'):
        assert workspace.is_dir()
elif action=='retire-finished':
    real=ro._write
    def retire(path,value):
        real(path,value)
        if path.name.startswith('completed-'):stop('retirement-receipt-durable-before-reservation-removal')
    ro._write=retire
    with ro.mutate(workspace):pass
elif action=='probe':
    try:
        ro.assert_workspace_startable(workspace)
        with ro.mutate(workspace):pass
    except ro.RootOperationError as e:
        print(str(e));raise SystemExit(3)
    raise SystemExit(0)
else:raise RuntimeError(action)
