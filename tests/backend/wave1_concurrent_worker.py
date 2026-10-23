"""Current F14 import barrier on F12's actual post-rename/pre-fsync boundary.

The historical concurrency worker and all preservation assertions stay intact.
"""
from pathlib import Path
import ast,hashlib,json,os,sys,time,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'qa/f14/original'))
from app import import_publication as pub
boundary=sys.argv[3];control=Path(sys.argv[4]);native=pub._native_rename;count=0

def renamed(*args):
    global count
    result=native(*args);count+=1
    if boundary=='import.move'+str(count):
        with (control/'checkpoint.json').open('w') as handle:
            json.dump({'pid':os.getpid(),'boundary':boundary,'primitive':'exclusive native rename before directory fsync','stack':traceback.format_stack(limit=8)},handle);handle.flush();os.fsync(handle.fileno())
        deadline=time.monotonic()+20
        while not (control/'continue').exists():
            if time.monotonic()>deadline:raise RuntimeError('Current concurrency barrier timed out')
            time.sleep(.01)
    return result
pub._native_rename=renamed
# Accept FD keywords only in the two legacy import predicates. The historical
# source, predicates' decisions and native import barrier stay unchanged.
worker=Path(__file__).resolve().parents[2]/'qa/f14/original/worker_concurrent.py'
raw=worker.read_bytes(); tree=ast.parse(raw,filename=str(worker)); adapted=[]
original_assertions=[ast.dump(node) for node in ast.walk(tree) if isinstance(node,ast.Assert)]
for node in ast.walk(tree):
    if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
            and node.func.id=='hook' and len(node.args)>=3
            and isinstance(node.args[2],ast.Constant)
            and node.args[2].value in {'import.move1','import.move2'}):
        predicate=next(k.value for k in node.keywords if k.arg=='predicate')
        assert isinstance(predicate,ast.Lambda) and predicate.args.kwarg is None
        predicate.args.kwarg=ast.arg(arg='_fd_keywords')
        adapted.append(node.args[2].value)
assert sorted(adapted)==['import.move1','import.move2']
assert original_assertions==[ast.dump(node) for node in ast.walk(tree) if isinstance(node,ast.Assert)]
ast.fix_missing_locations(tree)
(control/'adapter-compatibility.json').write_text(json.dumps({
    'historical_sha256':hashlib.sha256(raw).hexdigest(),
    'predicates':adapted,'historical_file_modified':False,
    'assertions_unchanged':True,'native_barrier_unchanged':True},indent=2))
previous_argv0=sys.argv[0];sys.argv[0]=str(worker)
try:
    exec(compile(tree,str(worker),'exec'),{'__name__':'__main__','__file__':str(worker),
         '__package__':'','__spec__':None,'__cached__':None})
finally:
    sys.argv[0]=previous_argv0
