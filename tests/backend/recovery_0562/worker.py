"""External SIGKILL probe; repository sources are imported read-only."""
from guards import *
import asyncio, hashlib, importlib, signal, traceback

case=Path(sys.argv[1]);action=sys.argv[2];boundary=sys.argv[3];control=Path(sys.argv[4])
# These are generated test paths, never persisted project configuration.
for key,value in {
 'KAMERA_CONFIG':case/'settings.json','KAMERA_WORKSPACE':case/'workspace',
 'KAMERA_DATABASE_DIR':case,'KAMERA_REGISTRY_DATABASE':case/'registry.sqlite3',
 'KAMERA_LOG_DIR':case/'logs','KAMERA_POOL_PROBE':case/'workspace',
 'KAMERA_ARCHIVE_ROOT':case/'archive','KAMERA_IMPORT_ROOT':case/'card',
 'KAMERA_REMOVABLE_ROOT':case/'removable','KAMERA_NAS_SOURCE_ROOT':case/'nas',
 'KAMERA_REMOVABLE_MOUNT_ROOT':case/'removable','KAMERA_DEVICE_NODE_ROOT':case/'devices',
}.items():os.environ[key]=str(value)

# Existing fixture locations become environment values before app import.
# No project configuration or recovery function is replaced for startup.
if (case/'case.json').exists():
    locations=json.loads((case/'case.json').read_text())
    database_parent=Path(locations['db']).parent
    os.environ['KAMERA_DATABASE_DIR']=str(database_parent)
    os.environ['KAMERA_WORKSPACE']=locations['workspace']
    os.environ['KAMERA_REGISTRY_DATABASE']=str(database_parent/'registry.sqlite3')
    os.environ['KAMERA_CONFIG']=str(database_parent/'settings.json')

from app import main
from app.database import initialize_database,database_connection,create_job,claim_next_job,get_job
from app.library_registry import initialize_library_registry,adopt_main_library,register_library,ensure_library_identity
from app.library_context import resolve_library_context
from app.storage_config import storage_paths
from app.workspace_layout import ensure_workspace_layout

DB=case/'kamera.sqlite3';REG=case/'registry.sqlite3';WS=case/'workspace'
counts={}

def stop(label):
    if label!=boundary:return
    marker={'boundary':label,'pid':os.getpid(),'signal':'SIGSTOP then parent SIGKILL',
            'stack':traceback.format_stack(limit=8)}
    path=control/'checkpoint.json'
    with path.open('w') as f:json.dump(marker,f,indent=2);f.flush();os.fsync(f.fileno())
    os.kill(os.getpid(),signal.SIGSTOP)
    raise RuntimeError('Probe resumed unexpectedly; audit invalid')


def hook(module,name,label,*,when='after',nth=1,predicate=None):
    real=getattr(module,name)
    def wrapped(*args,**kwargs):
        selected=predicate is None or predicate(*args,**kwargs)
        if selected:
            counts[label]=counts.get(label,0)+1
            selected=counts[label]==nth
        if selected and when=='before':stop(label)
        result=real(*args,**kwargs)
        if selected and when=='after':stop(label)
        return result
    setattr(module,name,wrapped)


def foundation():
    case.mkdir(exist_ok=True)
    (case/'settings.json').write_text(json.dumps({'storage':{'processing_buffer_percent':0,'safety_reserve_gib':0}}))
    for p in (WS,case/'archive',case/'logs',case/'card'):p.mkdir(exist_ok=True)
    (WS/'Arbeitsbereich').mkdir(exist_ok=True)
    ensure_workspace_layout(WS,configured_main_work_root=WS/'Arbeitsbereich')
    initialize_database(DB);initialize_library_registry(REG)
    adopt_main_library(REG,database_path=DB,workspace_root=WS,work_root=WS/'Arbeitsbereich',archive_root=case/'archive')


def second_libraries(n=2):
    databases=[]
    for number in range(1,n+1):
        db=case/f'second{number}.sqlite3';initialize_database(db)
        lid=f'second{number}';ensure_library_identity(db,lid)
        work=WS/'Arbeitsbereiche'/lid;work.mkdir(parents=True,exist_ok=True)
        archive=case/f'archive{number}';archive.mkdir(exist_ok=True)
        register_library(REG,library_id=lid,display_name=lid,database_path=db,workspace_root=WS,work_root=work,archive_root=archive)
        databases.append(str(db))
    return databases


def seed(kind):
    foundation();data={'kind':kind,'db':str(DB),'workspace':str(WS),'job':'J','expected':{}}
    from tests.backend.test_0440_trash import _file
    if kind in {'trash','restore'}:
        data['databases']=[str(DB)]+second_libraries(1)
        for db in data['databases']:
            create_job(Path(db),job_id='J',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(case/'card'))
            for name in ('A.JPG','B.JPG'):_file(Path(db),name,('synthetic-trash-'+name).encode())
            with database_connection(Path(db)) as c:c.execute("UPDATE jobs SET state='completed',stage='organized_verified'")
        from app.trash import reconcile_trash_inventory
        for name in ('A.JPG','B.JPG'):
            p=storage_paths(WS)['trash_root']/name;p.write_bytes(('synthetic-trash-'+name).encode());data['expected'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
        for db in data['databases']:reconcile_trash_inventory(Path(db),WS)
        if kind=='restore':
            from app.trash_import import queue_trash_restore
            q=queue_trash_restore(DB,WS,['A.JPG','B.JPG']);data['restore_job']=q['job_id']
    elif kind=='metadata':
        from PIL import Image
        from app import metadata_correction as mc
        root=mc.metadata_area_paths(area='general',workspace_root=WS,library_id='main')['root']
        p=root/'synthetic.JPG';Image.new('RGB',(16,16),(51,102,153)).save(p)
        data['source']=str(p);data['expected'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        task=mc.create_metadata_correction(DB,area='general',relative_path=p.name,proposed_datetime='2026-10-01T12:34:56',workspace_root=WS,library_id='main',_prevalidated_row={'relative_path':p.name,'filename':p.name,'media_type':'jpeg'},_prevalidated_source=p)
        data['task']=task['id']
    elif kind in {'library_metadata','multiple_metadata','reintegrate','metadata_projection'}:
        from PIL import Image
        from app import metadata_correction as mc
        if kind in {'library_metadata','reintegrate','metadata_projection'}:
            from tests.backend.test_0500_metadata_swap_recovery import _seed_library,_seed_reintegration
            temp=case/'fixture';temp.mkdir()
            if kind in {'library_metadata','metadata_projection'}:db,ws,src,fid,task=_seed_library(temp)
            else:
                db,ws,src,fid=_seed_reintegration(temp);task='META_BA12_TEST'
            Image.new('RGB',(16,16),(30,60,90)).save(src)
            if kind=='reintegrate':mc.write_metadata_datetime(src,'jpeg','2026-07-20T14:15:30')
            digest=hashlib.sha256(src.read_bytes()).hexdigest();size=src.stat().st_size
            with database_connection(db) as c:
                c.execute('UPDATE files SET size_bytes=?,source_size_bytes=?,sha256_original=?,sha256_current=?',(size,size,digest,digest))
                row=c.execute('SELECT detected_json FROM metadata_corrections WHERE id=?',(task,)).fetchone()
                detected=json.loads(row[0])
                for member in detected['members']:
                    member.update(size_bytes=size,source_size_bytes=size,sha256_original=digest,sha256_current=digest)
                c.execute('UPDATE metadata_corrections SET source_size_bytes=?,source_sha256=?,detected_json=? WHERE id=?',(size,digest,json.dumps(detected),task))
                c.execute("UPDATE jobs SET state='completed',stage='organized_verified',operation='folder_import'")
            (ws/'Arbeitsbereich').mkdir(exist_ok=True)
            (temp/'settings.json').write_text((case/'settings.json').read_text())
            initialize_library_registry(temp/'registry.sqlite3')
            adopt_main_library(temp/'registry.sqlite3',database_path=db,workspace_root=ws,work_root=ws/'Arbeitsbereich',archive_root=case/'archive')
            data.update(db=str(db),workspace=str(ws),source=str(src),task=task,family=fid,job='JOB')
            data['expected']={src.name:digest}
            if kind=='metadata_projection':
                from app.global_stock import project_import_job
                data['databases']=[str(db)]
                for number in (1,2):
                    target=temp/f'second{number}.sqlite3';initialize_database(target);ensure_library_identity(target,f'second{number}')
                    work=ws/'Arbeitsbereiche'/f'second{number}';work.mkdir(parents=True,exist_ok=True)
                    target_archive=case/f'projection-archive{number}';target_archive.mkdir()
                    register_library(temp/'registry.sqlite3',library_id=f'second{number}',display_name=f'second{number}',database_path=target,workspace_root=ws,work_root=work,archive_root=target_archive)
                    project_import_job(db,target,'JOB');data['databases'].append(str(target))
        else:
            root=mc.metadata_area_paths(area='multiple',workspace_root=WS,library_id='main')['root']
            import subprocess
            for number,name in enumerate(('A.JPG','B.JPG')):
                src=root/name;Image.new('RGB',(16,16),(30+number*30,60,90)).save(src)
                subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:10:01 12:00:0'+str(number),str(src)],check=True,capture_output=True)
                data['expected'][name]=hashlib.sha256(src.read_bytes()).hexdigest()
            data['source']=str(root/'A.JPG')
            preview=mc.preview_multiple_metadata_correction(workspace_root=WS,library_id='main',reference_relative_path='A.JPG',proposed_datetime='2026-10-01T12:34:56')
            data['preview']=preview['preview_fingerprint']
    elif kind in {'import','multi','claims'}:
        from PIL import Image
        for i in range(1,4):
            p=case/'card'/f'20261001_12000{i}_Synthetic.JPG';Image.new('RGB',(16,16),(i*30,60,90)).save(p)
            # Real JPEG/ExifTool metadata. Distinct bytes, one file per family.
            import subprocess
            subprocess.run(['exiftool','-overwrite_original',f'-DateTimeOriginal=2026:10:01 12:00:0{i}',str(p)],check=True,capture_output=True)
            if i==1:
                with p.open('ab') as f:f.write(b'AUDIT-SYNTHETIC-PADDING'*150000)
            data['expected'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        data['databases']=[str(DB)]+second_libraries(2 if kind in {'multi','claims'} else 0)
        create_job(DB,job_id='J',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(case/'card'))
        data['source']=str(case/'card')
        if kind=='claims':
            from tests.backend.test_0311_global_stock import _preview
            from app.database import create_planned_event
            main.process_claimed_job(claim_next_job(DB,operation='folder_import'),library_context=resolve_library_context(REG,'main'))
            data['events']={}
            for index,db in enumerate(data['databases']):
                with database_connection(Path(db)) as c:
                    families=c.execute("SELECT id FROM file_families ORDER BY id").fetchall()
                assert len(families)==3
                event=create_planned_event(Path(db),'J',_preview(families[index]['id'],'2026-10-01','Claims'+str(index)))
                data['events'][db]=event['parent_event']['id']
    elif kind in {'sort','reconcile'}:
        if kind=='reconcile':
            # Use the established synthetic fixture, in a separate subdirectory.
            from tests.backend.test_0500_reconcile_crash import _seed_reconcile
            temp=case/'fixture';temp.mkdir()
            db,ws,plan,run=_seed_reconcile(temp)
            # Keep actual fixture paths; startup uses the same db via directory env.
            data.update(db=str(db),workspace=str(ws),job=run['job_id'],plan=plan,run=run['id'])
            (case/'fixture'/'settings.json').write_text((case/'settings.json').read_text())
            initialize_library_registry(case/'fixture'/'registry.sqlite3')
            adopt_main_library(case/'fixture'/'registry.sqlite3',database_path=db,workspace_root=ws,work_root=ws/'Arbeitsbereich',archive_root=case/'archive')
        else:
            from tests.backend.test_0250_continuous import setup,create,payload
            from tests.backend.test_0168_deep_workflows import add_file
            from app.sort_plan import build_event_sort_plan
            from app.sort_apply import prepare_sort_run,CONFIRMATION_PHRASE
            setup(DB,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
            event=create(DB,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
            with database_connection(DB) as c:
                families=[dict(r) for r in c.execute('SELECT * FROM file_families')]
            for family in families:
                add_file(DB,family['id'],'2026/2026-07-23/'+str(family['id'])+'.JPG',payload=('synthetic-sort-'+str(family['id'])).encode())
            with database_connection(DB) as c:
                c.execute("UPDATE files SET current_root_kind='shared_workspace'")
                rows=[dict(r) for r in c.execute('SELECT * FROM files')]
                c.execute("UPDATE jobs SET state='completed',stage='organized_verified',operation='folder_import'")
            central=storage_paths(WS)['backup_root']
            for row in rows:
                p=central/row['current_relative_path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('synthetic-sort-'+str(row['family_id'])).encode())
            plan=build_event_sort_plan(DB,'j',event['id'],WS)
            assert plan['summary']['ready'],plan
            run=prepare_sort_run(DB,'j',event['id'],WS,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
            data.update(job='j',plan=plan,run=run['id'],event=event['id'])
        if kind=='reconcile':data['event']=run['event_id']
        data['expected']={str(item['file_id']):item['expected_sha256'] if 'expected_sha256' in item else item.get('sha256') for item in data['plan']['files']}
    elif kind=='ssd':
        from tests.backend.test_0263_event_inventory import seed_job,seed_event,seed_family,seed_file_for_family
        with database_connection(DB) as c:
            seed_job(c);seed_event(c,status='applied');rel='2026/07-23 - Trip/Alle/'
            fid,first=seed_family(c,content=b'synthetic-A',current_path=rel+'A.JPG')
            seed_file_for_family(c,family_id=fid,content=b'synthetic-B',current_path=rel+'B.JPG',filename='B.JPG')
            c.execute("UPDATE files SET current_root_kind='shared_workspace'")
        for name in ('A.JPG','B.JPG'):
            value=('synthetic-'+name[0]).encode()
            for root in (WS/'Arbeitsbereich',case/'archive'):
                p=root/rel/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
            data['expected'][name]=hashlib.sha256(value).hexdigest()
        data.update(job='j',event='e')
    (case/'case.json').write_text(json.dumps(data,indent=2,default=str));return data


def configure_fixture(data):
    global DB,WS,REG
    DB=Path(data['db']);WS=Path(data['workspace'])
    REG=DB.parent/'registry.sqlite3'
    if DB!=main.DATABASE_FILE:
        # Only environment globals for the established nested fixture, not
        # a replacement recovery routine or changed application source.
        main.DATABASE_FILE=DB;main.DATABASE_DIRECTORY=DB.parent;main.WORKSPACE_PATH=WS;main.REGISTRY_DATABASE_FILE=REG
        os.environ['KAMERA_CONFIG']=str(DB.parent/'settings.json');main.CONFIG_PATH=DB.parent/'settings.json'


def instrument(kind):
    from app import trash_selective as ts,metadata_correction as mc,metadata_swap_recovery as ms,sort_apply as sa
    if kind=='trash':
        hook(ts,'_move_checked','trash.stage1',nth=1);hook(ts,'_purge_selected','trash.db1',nth=1);hook(ts,'_purge_selected','trash.db2',nth=2)
        hook(ts,'_atomic_json','trash.prepared',predicate=lambda p,v:v['state']=='prepared')
        hook(ts,'_atomic_json','trash.committed',predicate=lambda p,v:v['state']=='committed')
        hook(Path,'unlink','trash.cleanup1',predicate=lambda p,*a,**kw:'.trash-deletions' in str(p) and p.name=='A.JPG')
        hook(ts,'_restore_catalogue','trash.recover_db1',nth=1)
        hook(ts,'_return_checked','trash.recover_file1',nth=1)
        hook(ts,'_remove_empty_staging','trash.recover_cleanup')
    elif kind in {'metadata','library_metadata','multiple_metadata','reintegrate','metadata_projection'}:
        source=Path(data['source'])
        hook(mc.os,'replace','meta.backup',predicate=lambda s,d:Path(s)==source)
        hook(mc.os,'replace','meta.swap',predicate=lambda s,d:Path(d)==source)
        hook(ms,'create_swap_journal','meta.before_journal',when='before')
        hook(ms,'create_swap_journal','meta.journal')
        hook(mc,'_complete_task','meta.db')
        hook(ms,'mark_swap_committed','meta.committed')
        hook(ms,'_finish','meta.cleanup')
        hook(ms,'_rollback','meta.recover_original')
        hook(ms,'_recover_preparation','meta.preparation_cleanup')
        hook(ms,'create_preparation_journal','meta.preparation_owned')
        hook(mc,'_mark_task_blocked','meta.recover_task')
        if kind=='metadata_projection':
            from contextlib import contextmanager
            import app.global_stock as gs
            actual=gs.database_connection
            @contextmanager
            def after_projection_commit(path):
                with actual(path) as c:yield c
                if Path(path)==Path(data['databases'][1]):stop('metadata.projection1')
            gs.database_connection=after_projection_commit
    elif kind in {'sort','reconcile'}:
        hook(sa,'_move_without_overwrite','sort.move1',nth=1);hook(sa,'_move_without_overwrite','sort.move2',nth=2)
        hook(sa,'_finalize_database','sort.before_db',when='before');hook(sa,'_finalize_database','sort.db')
        hook(sa,'_rollback_one','sort.recover1',nth=1)
        if kind=='reconcile':
            import app.workspace_reconcile as wr, app.obsolete_structure as obs
            hook(wr,'_move_without_overwrite','reconcile.move1',nth=1)
            hook(wr,'_move_without_overwrite','reconcile.move2',nth=2)
            import app.event_mutation as em
            hook(em,'mark_job_mutation_completed','reconcile.before_db',when='before')
            hook(obs,'cleanup_obsolete_structure','reconcile.db',when='before')
    elif kind=='claims':
        import app.global_library_inventory as gi
        hook(gi,'claim_source_family','claims.one',nth=1)
        hook(gi,'claim_source_family','claims.two',nth=2)
    elif kind in {'import','multi','claims'}:
        import app.pipeline as pl,app.folder_import as fi,app.global_stock as gs
        hook(fi,'copy_and_verify','import.before_copy',when='before');hook(fi,'copy_and_verify','import.copy_verify')
        hook(pl,'sha256_file','import.hash1',predicate=lambda p,*a,**kw:'.incoming' in str(p),nth=1)
        # Preserve the same post-publication crash boundaries and assertions;
        # the unsafe os.replace primitive was removed by the F12 patch.
        import app.import_publication as publication
        # Stop immediately AFTER the rename, BEFORE directory fsync, exactly
        # as the former os.replace hooks did. This helper only moves import
        # media, so journal replacements cannot consume these counters.
        hook(publication,'_native_rename','import.move1',nth=1)
        hook(publication,'_native_rename','import.move2',nth=2)
        hook(publication,'_native_rename','import.publish_before',when='before')
        hook(publication,'_native_rename','import.publish_after')
        if boundary=='import.rollback_after':
            def fail_import_paths(*a,**k):raise RuntimeError('synthetic callback failure before SQLite completion')
            main.update_import_file_paths=fail_import_paths
            # The first rollback publishes back into Original. Keep the same
            # atomic primitive and stop only after the actual reverse rename.
            real_rollback=fi.rollback_import_file
            def rollback_and_stop(*a,**k):
                result=real_rollback(*a,**k);stop('import.rollback_after');return result
            fi.rollback_import_file=rollback_and_stop
        hook(main,'update_import_file_paths','import.paths')
        hook(Path,'unlink','import.discard1',predicate=lambda p,*a,**k: str(p).startswith(str(WS/'SD-Kartensicherungen')) and '.incoming' not in str(p) and p.suffix=='.JPG')
        hook(main,'complete_job','import.before_complete',when='before');hook(main,'complete_job','import.complete')
        hook(gs,'_insert_row','multi.in_tx',predicate=lambda conn,table,*a,**kw:table=='files',nth=1)
        hook(main,'project_import_job','multi.project1',nth=1);hook(main,'project_import_job','multi.project2',nth=2)
        hook(main,'backfill_library_inventory','multi.inventory1',nth=1)
        hook(gs,'project_import_job','multi.startup_project1',nth=1)
        import app.library_registry as lr
        import app.global_library_inventory as gi
        hook(gi,'register_source_family','multi.source_family1',nth=1)
    elif kind=='ssd':
        import app.ssd_release as sr
        hook(sr,'verify_event_archive','ssd.archive_verified')
        hook(sr,'_verify_regular_file','ssd.rehash1',predicate=lambda p,*a,**k:str(p).startswith(str(case/'archive')),nth=1)
        hook(Path,'unlink','ssd.unlink1',predicate=lambda p,*a,**k:str(p).startswith(str(WS/'Arbeitsbereich')) and p.suffix=='.JPG',nth=1)
        hook(Path,'unlink','ssd.unlink2',predicate=lambda p,*a,**k:str(p).startswith(str(WS/'Arbeitsbereich')) and p.suffix=='.JPG',nth=2)
        hook(sr,'_finalize_release','ssd.before_finalize',when='before');hook(sr,'_finalize_release','ssd.finalized')
    elif kind=='restore':
        import app.trash_restore as tr
        hook(tr,'_move_checked','restore.move1',nth=1)
        hook(tr,'_preflight_restore','restore.preflight')
        # Runtime trace below covers per-database commits in the inline loop.



def trace_probe(frame,event,arg):
    if event != 'line':return trace_probe
    module=frame.f_globals.get('__name__')
    function=frame.f_code.co_name
    loc=frame.f_locals
    if module=='app.pipeline':
        if boundary=='import.copy_chunk' and function=='copy_and_verify' and frame.f_lineno==408 and len(loc.get('block',b''))>=1024*1024:
            stop(boundary)
        if boundary=='import.hash_chunk' and function=='sha256_file' and frame.f_lineno==67 and '.incoming' in str(loc.get('path','')) and len(loc.get('block',b''))>=1024*1024:
            stop(boundary)
    if module=='app.database' and function=='complete_job' and boundary=='import.in_tx' and frame.f_lineno==1001:
        assert loc['connection'].in_transaction
        stop(boundary)
    if module=='app.trash_restore' and function=='restore_trash_files' and boundary=='restore.db1':
        # Line after the first explicit per-database commit; resolved below
        # from the unchanged source and recorded in checkpoint stack.
        if frame.f_lineno==RESTORE_COMMIT_NEXT:
            count=counts.get('restore.db1',0)+1;counts['restore.db1']=count
            if count==1:stop(boundary)
    return trace_probe

# Discover the statement after connection.commit() in the restore function.
import ast
_restore_tree=ast.parse((source/'app/trash_restore.py').read_text())
_restore_func=next(n for n in _restore_tree.body if isinstance(n,ast.FunctionDef) and n.name=='restore_trash_files')
RESTORE_COMMIT_NEXT=next(n.lineno for n in ast.walk(_restore_func) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='append' and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='committed')

def startup():
    async def lifecycle():
        async with main.app.router.lifespan_context(main.app):
            await asyncio.sleep(.3)
            if main.DATABASE_INITIALIZATION_ERROR:raise RuntimeError('Startup: '+str(main.DATABASE_INITIALIZATION_ERROR))
    asyncio.run(lifecycle())


def operate(kind):
    if kind=='trash':
        from app.trash_selective import delete_selected_trash_files
        return delete_selected_trash_files([Path(p) for p in data['databases']],WS,['A.JPG','B.JPG'])
    if kind=='metadata':
        from app.metadata_correction import apply_metadata_correction
        return apply_metadata_correction(DB,data['task'],workspace_root=WS,library_id='main')
    if kind=='metadata_projection':
        from app.metadata_correction import apply_metadata_correction
        task=apply_metadata_correction(DB,data['task'],workspace_root=WS,library_id='main')
        return main._sync_completed_library_metadata_correction(resolve_library_context(REG,'main'),task)
    if kind=='library_metadata':
        from app.metadata_correction import apply_metadata_correction
        return apply_metadata_correction(DB,data['task'],workspace_root=WS,library_id='main')
    if kind=='reintegrate':
        from app.metadata_correction import reintegrate_library_metadata_family
        return reintegrate_library_metadata_family(DB,workspace_root=WS,library_id='main',family_id=data['family'])
    if kind=='multiple_metadata':
        from app.metadata_correction import apply_multiple_metadata_correction
        return apply_multiple_metadata_correction(workspace_root=WS,library_id='main',reference_relative_path='A.JPG',proposed_datetime='2026-10-01T12:34:56',expected_preview_fingerprint=data['preview'])
    if kind=='sort':
        from app.sort_apply import execute_sort_run
        return execute_sort_run(DB,data['run'],WS)
    if kind=='reconcile':
        from app.workspace_reconcile import execute_workspace_reconcile_run
        return execute_workspace_reconcile_run(DB,data['run'],WS)
    if kind=='claims':
        from app.global_library_inventory import backfill_library_claims
        for lid,db in zip(('main','second1','second2'),data['databases']):
            backfill_library_claims(REG,database_path=Path(db),library_id=lid)
        return {'claims':'updated'}
    if kind in {'import','multi'}:
        job=claim_next_job(DB,operation='folder_import');assert job
        return main.process_claimed_job(job,library_context=resolve_library_context(REG,'main'))
    if kind=='ssd':
        from app.ssd_release import release_event_ssd
        return release_event_ssd(DB,WS,case/'archive',data['job'],data['event'])
    if kind=='restore':
        from app.trash_import import prepare_queued_trash_restore
        job=claim_next_job(DB,operation='trash_import')
        return prepare_queued_trash_restore(DB,[Path(p) for p in data['databases']],WS,data['restore_job'])


try:
    if action=='seed':result=seed(boundary)
    else:
        data=json.loads((case/'case.json').read_text());configure_fixture(data);instrument(data['kind'])
        if boundary in {'import.copy_chunk','import.hash_chunk','import.in_tx','restore.db1'}:sys.settrace(trace_probe)
        if action=='startup':result=startup()
        elif action=='verify_archive':
            from app.archive_transfer import verify_event_archive
            result=verify_event_archive(DB,case/'archive',data['job'],data['event'],workspace_path=WS)
        elif action=='operate':result=operate(data['kind'])
        elif action=='control_restore':
            job=claim_next_job(DB,operation='trash_import');assert job
            result=main.process_claimed_job(job,library_context=resolve_library_context(REG,'main'))
        elif action=='sync_metadata':
            from app.metadata_correction import get_metadata_correction
            result=main._sync_completed_library_metadata_correction(resolve_library_context(REG,'main'),get_metadata_correction(DB,data['task']))
        elif action=='discard':result=main._discard_terminal_import_job('J')
        elif action=='manual_recover':
            from app.sort_apply import mark_incomplete_sort_runs_interrupted,recover_interrupted_sort_runs
            mark_incomplete_sort_runs_interrupted(DB);result=recover_interrupted_sort_runs(DB)
        elif action=='retry':
            if data['kind'] in {'sort','reconcile'}:
                import app.sort_apply as sa
                if data['kind']=='sort':
                    from app.sort_plan import build_event_sort_plan
                    plan=build_event_sort_plan(DB,data['job'],data['event'],WS)
                    run=sa.prepare_sort_run(DB,data['job'],data['event'],WS,expected_plan_token=plan['plan_token'],confirmation_phrase=sa.CONFIRMATION_PHRASE)
                    result=sa.execute_sort_run(DB,run['id'],WS)
                else:
                    import app.workspace_reconcile as wr
                    plan=wr.build_workspace_reconcile_plan(DB,data['job'],data['event'],WS)
                    run=wr.prepare_workspace_reconcile_run(DB,data['job'],data['event'],WS,expected_plan_token=plan['plan_token'],confirmation_phrase=sa.CONFIRMATION_PHRASE)
                    result=wr.execute_workspace_reconcile_run(DB,run['id'],WS)
            else:result=operate(data['kind'])
        else:raise ValueError(action)
    (control/'result.json').write_text(json.dumps({'status':'ok','result':result},default=str,indent=2))
except BaseException as error:
    (control/'result.json').write_text(json.dumps({'status':'error','error':repr(error),'traceback':traceback.format_exc()},indent=2))
    raise
