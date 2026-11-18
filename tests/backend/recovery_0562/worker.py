"""External SIGKILL probe; repository sources are imported read-only."""
from guards import *
import asyncio, hashlib, importlib, signal, traceback, time

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
    os.environ['KAMERA_REGISTRY_DATABASE']=str(locations.get('registry',database_parent/'registry.sqlite3'))
    os.environ['KAMERA_CONFIG']=str(locations.get('config',database_parent/'settings.json'))

from app import main
from app.database import initialize_database,database_connection,create_job,claim_next_job,get_job
from app.library_registry import initialize_library_registry,adopt_main_library,register_library,ensure_library_identity
from app.library_context import resolve_library_context
from app.storage_config import storage_paths
from app.workspace_layout import ensure_workspace_layout

DB=case/'kamera.sqlite3';REG=case/'registry.sqlite3';WS=case/'workspace'
counts={}

def stop(label, *, details=None):
    if label!=boundary:return
    marker={'boundary':label,'pid':os.getpid(),'signal':'SIGSTOP then parent SIGKILL',
            'stack':traceback.format_stack(limit=8), 'details':details}
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
    # Explicit complete legacy installation, before creating its catalogue.
    for name in ['SD-Kartensicherungen','Arbeitsbereiche','Metadatenkorrektur','Papierkorb']:
        (WS/name).mkdir(exist_ok=True)
    from app.managed_directory_names import directory_name
    metadata=WS/'Metadatenkorrektur'
    for kind in ('metadata_general','metadata_multiple'):
        (metadata/directory_name(metadata,kind)).mkdir(exist_ok=True)
    (WS/'Arbeitsbereich').mkdir(exist_ok=True)
    # This is an explicitly provisioned historical installation. Its legacy
    # work folder must never be mistaken for an empty DB-less new bootstrap.
    initialize_database(DB);initialize_library_registry(REG)
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
            # This second workspace represents the same explicit legacy installation
            # as foundation(). Complete its fixture before operating or crashing;
            # recovery must never manufacture the missing administrative roots.
            from app.storage_config import LEGACY_STORAGE_DEFAULTS
            from app.managed_directory_names import directory_name
            for directory in LEGACY_STORAGE_DEFAULTS.values():
                (ws/directory).mkdir(exist_ok=True)
            # This synthetic legacy installation existed before the crash.
            # Prepare every required metadata role *before* taking recovery
            # snapshots; never let startup create missing administrative roots.
            metadata_root=ws/LEGACY_STORAGE_DEFAULTS['metadata_directory_name']
            for role in ('metadata_general','metadata_multiple'):
                (metadata_root/directory_name(metadata_root,role)).mkdir(exist_ok=True)
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
            fixture_settings=json.loads((case/'settings.json').read_text())
            fixture_settings.setdefault('storage',{}).update(LEGACY_STORAGE_DEFAULTS)
            (temp/'settings.json').write_text(json.dumps(fixture_settings))
            # _seed_library already established a registered owner, real F14
            # control and pinned work/archive roots. Never adopt its database
            # into a second registry using different paths after that point.
            data.update(db=str(db),workspace=str(ws),source=str(src),task=task,
                        family=fid,job='JOB',
                        registry=str(temp/'registry.sqlite3'),
                        config=str(temp/'settings.json'))
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
            # The nested historical fixture also needs all established roots.
            for root in storage_paths(ws).values():root.mkdir(exist_ok=True)
            from app.managed_directory_names import directory_name
            metadata_root=storage_paths(ws)['metadata_root']
            for role in ('metadata_general','metadata_multiple'):
                (metadata_root/directory_name(metadata_root,role)).mkdir(exist_ok=True)
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
    REG=Path(data.get('registry',DB.parent/'registry.sqlite3'))
    if DB!=main.DATABASE_FILE:
        # Only environment globals for the established nested fixture, not
        # a replacement recovery routine or changed application source.
        main.DATABASE_FILE=DB;main.DATABASE_DIRECTORY=DB.parent;main.WORKSPACE_PATH=WS;main.REGISTRY_DATABASE_FILE=REG
        config=Path(data.get('config',DB.parent/'settings.json'))
        os.environ['KAMERA_CONFIG']=str(config);main.CONFIG_PATH=config


def instrument(kind):
    from app import trash_selective as ts,metadata_correction as mc,metadata_swap_recovery as ms,sort_apply as sa
    if kind=='trash':
        if boundary.startswith('f11.reserve'):
            from app import trash_import as ti
            hook(ts, '_atomic_json', 'f11.reserve_before', when='before', predicate=lambda p,v: p.name.startswith('TRASH_IMPORT_'))
            hook(ts, '_atomic_json', 'f11.reserve_after', predicate=lambda p,v: p.name.startswith('TRASH_IMPORT_'))
            hook(ti, 'create_job', 'f11.reserve_committed')
        hook(ts,'_move_checked','trash.stage1',nth=1);hook(ts,'_purge_selected','trash.db1',nth=1);hook(ts,'_purge_selected','trash.db2',nth=2)
        hook(ts,'_atomic_json','trash.prepared',predicate=lambda p,v:v.get('state')=='prepared')
        hook(ts,'_atomic_json','trash.committed',predicate=lambda p,v:v.get('state')=='committed')
        hook(ts.trash_fd,'unlink','trash.cleanup1',predicate=lambda p,*a,**kw:'.trash-deletions' in str(p) and p.name=='A.JPG')
        hook(ts,'_restore_catalogue','trash.recover_db1',nth=1)
        hook(ts,'_return_checked','trash.recover_file1',nth=1)
        hook(ts,'_remove_empty_staging','trash.recover_cleanup')
    elif kind in {'metadata','library_metadata','multiple_metadata','reintegrate','metadata_projection'}:
        source=Path(data['source'])
        hook(mc.os,'replace','meta.backup',predicate=lambda s,d,**kw:Path(s)==source)
        hook(mc.os,'replace','meta.swap',predicate=lambda s,d,**kw:Path(d)==source)
        hook(ms,'create_swap_journal','meta.before_journal',when='before')
        hook(ms,'create_swap_journal','meta.journal')
        hook(mc,'_complete_task','meta.db')
        hook(ms,'mark_swap_committed','meta.committed')
        hook(ms,'_finish','meta.cleanup')
        hook(ms,'_rollback','meta.recover_original')
        if kind=='library_metadata':
            import app.metadata_library_recovery as library_recovery
            hook(library_recovery.ro,'_write','library.before-outcome',when='before',predicate=lambda p,v:p.name.startswith('library-metadata-outcome-'))
            hook(library_recovery.ro,'_write','library.outcome',predicate=lambda p,v:p.name.startswith('library-metadata-outcome-'))
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



# Exact between-chunk boundaries follow source statements, not historic line
# numbers. Conditions and original SIGKILL/test assertions remain unchanged.
def pipeline_loop_boundary(function):
    import ast, inspect, textwrap
    source, first = inspect.getsourcelines(function)
    tree = ast.parse(textwrap.dedent(''.join(source)))
    loop = next(node for node in ast.walk(tree) if isinstance(node, ast.While) and any(
        isinstance(child, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'block' for target in child.targets)
        for child in node.body
    ))
    return first + loop.body[0].lineno - 1

from app import pipeline as _pipeline_boundaries
PIPELINE_COPY_BETWEEN_CHUNKS = pipeline_loop_boundary(_pipeline_boundaries.copy_and_verify)
# Earlier release sources still hash inside sha256_file.
PIPELINE_HASH_FUNCTION = getattr(_pipeline_boundaries, 'sha256_stream', _pipeline_boundaries.sha256_file)
PIPELINE_HASH_BETWEEN_CHUNKS = pipeline_loop_boundary(PIPELINE_HASH_FUNCTION)


def trace_probe(frame,event,arg):
    if event != 'line':return trace_probe
    module=frame.f_globals.get('__name__')
    function=frame.f_code.co_name
    loc=frame.f_locals
    if module=='app.pipeline':
        if boundary=='import.copy_chunk' and function=='copy_and_verify' and frame.f_lineno==PIPELINE_COPY_BETWEEN_CHUNKS and len(loc.get('block',b''))>=1024*1024:
            stop(boundary)
        if boundary=='import.hash_chunk' and function==PIPELINE_HASH_FUNCTION.__name__ and frame.f_lineno==PIPELINE_HASH_BETWEEN_CHUNKS:
            path = loc.get('path') or getattr(loc.get('handle'), 'name', '')
            if '.incoming' in str(path) and len(loc.get('block', b'')) >= 1024 * 1024:
                stop(boundary)
    if module=='app.database' and function=='complete_job' and boundary=='import.in_tx' and frame.f_lineno==IMPORT_COMPLETED_IN_TX:
        assert loc['connection'].in_transaction
        assert loc['cursor'].rowcount == 1
        assert loc['connection'].execute('SELECT state FROM jobs WHERE id=?', (loc['job_id'],)).fetchone()[0] == 'completed'
        stop(boundary, details={'in_transaction': True, 'updated_rows': 1, 'uncommitted_state': 'completed'})
    if module=='app.trash_restore' and function=='restore_trash_files' and boundary=='restore.db1':
        # Line after the first explicit per-database commit; resolved below
        # from the unchanged source and recorded in checkpoint stack.
        if frame.f_lineno==RESTORE_COMMIT_NEXT:
            count=counts.get('restore.db1',0)+1;counts['restore.db1']=count
            if count==1:stop(boundary)
    return trace_probe

# Discover the statement after connection.commit() in the restore function.
import ast
# Stop after UPDATE has executed and before leaving its transaction. Resolve
# the cursor.rowcount check structurally; numeric lines inside SQL parameters
# are not stable executable trace boundaries.
_database_tree=ast.parse((source/'app/database.py').read_text())
_complete_func=next(n for n in _database_tree.body if isinstance(n,ast.FunctionDef) and n.name=='complete_job')
_completion_checks=[n for n in ast.walk(_complete_func) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Attribute) and isinstance(n.test.left.value,ast.Name) and n.test.left.value.id=='cursor' and n.test.left.attr=='rowcount']
assert len(_completion_checks)==1
IMPORT_COMPLETED_IN_TX=_completion_checks[0].lineno
_restore_tree=ast.parse((source/'app/trash_restore.py').read_text())
_restore_func=next(n for n in _restore_tree.body if isinstance(n,ast.FunctionDef) and n.name=='restore_trash_files')
RESTORE_COMMIT_NEXT=next(n.lineno for n in ast.walk(_restore_func) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='append' and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='committed')



def r1_instrument():
    import app.trash_restore as tr
    import app.trash_selective as ts
    actual = ts._atomic_json
    def write(path,value):
        selected = path.parent.name == '.trash-restores'
        state = value.get('state')
        if selected and state=='conflict':stop('r1.before_conflict')
        actual(path,value)
        if selected:
            if state=='prepared':
                if any(p.get('target_identity') for p in value.get('plans',[])):stop('r1.receipt')
                else:stop('r1.prepared')
            if state=='rolling_back':stop('r1.rolling_back')
            if state=='conflict':stop('r1.after_conflict')
            if state=='completed':stop('r1.completed')
    ts._atomic_json=write
    actual_check=tr._conflict_invariants
    def validate(*args,**kw):
        value=actual_check(*args,**kw)
        if kw.get('existing'):stop('r1.conflict_rechecked')
        return value
    tr._conflict_invariants=validate
    if boundary=='r1.wait_lock':
        from contextlib import contextmanager
        actual_lock=ts._operation_lock
        @contextmanager
        def waiting(*args,**kwargs):
            (control/'attempt.json').write_text(json.dumps({'pid':os.getpid(),'before':'workspace flock'}))
            with actual_lock(*args,**kwargs):yield
        ts._operation_lock=waiting
    if action=='r1_conflict':
        actual_link=tr.os.link
        def collision(src,dst,*args,**kw):
            if Path(src)==WS/'Papierkorb/A.JPG' and not Path(dst).exists():Path(dst).write_bytes(b'synthetic-foreign-target')
            return actual_link(src,dst,*args,**kw)
        tr.os.link=collision


def startup():
    async def lifecycle():
        async with main.app.router.lifespan_context(main.app):
            await asyncio.sleep(.3)
            if main.DATABASE_INITIALIZATION_ERROR:raise RuntimeError('Startup: '+str(main.DATABASE_INITIALIZATION_ERROR))
            # A queued restore is asynchronous. The worker's first claim can
            # correctly meet the startup admission fence and retry two seconds
            # later. A 300-ms lifespan must not masquerade as a failed restore.
            # Wait only for actually admitted trash imports; unresolved F14
            # effects keep their fence and are never scheduled by this adapter.
            from app.operation_health import inspect as operation_status
            # Allow a bounded 30-second async finish on the loaded CI runner;
            # queued work must still actually reach a terminal state.
            end=time.monotonic()+30
            while operation_status(WS)['writes_allowed']:
                with database_connection(DB) as connection:
                    active=connection.execute("SELECT 1 FROM jobs WHERE operation='trash_import' "
                        "AND state IN ('queued','copying','verifying','backup_verified','analyzing_metadata','organizing') LIMIT 1").fetchone()
                if active is None:break
                if time.monotonic()>=end:raise AssertionError('Admitted asynchronous trash import did not reach a terminal state')
                await asyncio.sleep(.05)
    asyncio.run(lifecycle())
    from app.operation_health import inspect as operation_status
    return {'storage_state':main.api_storage_health()['state'],'operation_health':operation_status(WS)}


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
        if boundary.startswith('r1.') or action in {'r1_conflict','r1_owned'}:r1_instrument()
        if boundary in {'import.copy_chunk','import.hash_chunk','import.in_tx','restore.db1'}:sys.settrace(trace_probe)
        if action=='startup':result=startup()
        elif action=='fence_probe':
            # No media mutation and no SQL row change: prove that the real
            # admission/authorizer rejects the threatened resource in a fresh
            # process, without relying only on a display status or HTTP code.
            from app import root_operations as ro
            import sqlite3
            parent=ro._control_location(WS)
            before={p.name:p.read_bytes() for p in parent.glob('operation-*.json')}
            fs_denied=sql_denied=False
            try:
                with ro.reserve(WS,library_id='main',database=DB,paths=[WS],
                                kind='qa-conflicting-write-probe'):
                    pass
            except ro.RootOperationError:fs_denied=True
            table='metadata_corrections' if data['kind']=='metadata' else 'files'
            try:
                with database_connection(DB) as connection:
                    connection.execute('UPDATE '+table+' SET id=id WHERE 0')
            except sqlite3.DatabaseError as error:
                if getattr(error,'sqlite_errorcode',None)!=sqlite3.SQLITE_AUTH:raise
                sql_denied=True
            after={p.name:p.read_bytes() for p in parent.glob('operation-*.json')}
            assert before and before==after, 'A rejected writer changed the original F14 evidence'
            assert fs_denied and sql_denied, (fs_denied,sql_denied)
            result={'original_reservations_unchanged':True,'filesystem_denied':True,'sqlite_denied':True}
        elif action=='verify_archive':
            from app.archive_transfer import verify_event_archive
            result=verify_event_archive(DB,case/'archive',data['job'],data['event'],workspace_path=WS)
        elif action=='full_empty':result=main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
        elif action=='queue_restore':result=main.api_restore_trash({'relative_paths':['A.JPG']})
        elif action=='operate':result=operate(data['kind'])
        elif action in {'r1_conflict','r1_owned'}:
            from app.trash_restore import restore_trash_files
            result=restore_trash_files([Path(p) for p in data['databases']],WS,relative_paths=['A.JPG'],operation_id='R1_SECOND' if boundary=='r1.wait_lock' else None)
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
