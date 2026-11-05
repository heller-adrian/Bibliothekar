"""F12 native publication inside F14's real registered import worker."""
from pathlib import Path
import hashlib,json,os
import pytest
from PIL import Image
from app import main,import_publication as pub,root_operations as ro
from app.database import initialize_database,create_job,claim_next_job,get_job,database_connection
from app.library_registry import initialize_library_registry,register_library,ensure_library_identity
from app.library_context import resolve_library_context
from app.storage_config import LEGACY_STORAGE_DEFAULTS,ENGLISH_STORAGE_DEFAULTS,storage_paths
from app.workspace_layout import ensure_workspace_layout
from tests.backend.test_f14_fixed_storage import child,stable

@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('scenario',['normal','late-collision','root-replaced-before-native'])
def test_registered_import_preserves_both_security_contracts(tmp_path,monkeypatch,legacy,scenario):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();db=case/'main.sqlite3';reg=case/'registry.sqlite3';archive=case/'archive';archive.mkdir();card=case/'card';card.mkdir()
    names=LEGACY_STORAGE_DEFAULTS if legacy else ENGLISH_STORAGE_DEFAULTS
    config=case/'settings.json';config.write_text(json.dumps({'storage':{**names,'processing_buffer_percent':0,'safety_reserve_gib':0}}))
    for k,v in {'KAMERA_WORKSPACE':ws,'KAMERA_CONFIG':config,'KAMERA_REGISTRY_DATABASE':reg}.items():monkeypatch.setenv(k,str(v))
    for name in names.values():(ws/name).mkdir()
    if legacy:
        initialize_library_registry(reg)
        from app.managed_directory_names import directory_name
        metadata=storage_paths(ws)['metadata_root']
        for kind in ('metadata_general','metadata_multiple'):(metadata/directory_name(metadata,kind)).mkdir()
    ensure_workspace_layout(ws);initialize_database(db);initialize_library_registry(reg);ensure_library_identity(db,'main')
    work=ws/names['workspaces_directory_name']/'Photos';work.mkdir()
    register_library(reg,library_id='main',display_name='Synthetic',database_path=db,workspace_root=ws,work_root=work,archive_root=archive,is_main=True)
    ctx=resolve_library_context(reg,'main')
    with ro.reserve(ws,library_id='main',database=db,paths=[work,archive,*storage_paths(ws).values()],kind='startup'):pass
    for k,v in {'WORKSPACE_PATH':ws,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':config,'LOG_PATH':case/'logs','MAIN_LIBRARY_CONTEXT':ctx}.items():monkeypatch.setattr(main,k,v)
    source=card/'20261001_120001_Synthetic.JPG';Image.new('RGB',(16,16),(31,61,91)).save(source);digest=hashlib.sha256(source.read_bytes()).hexdigest()
    create_job(db,job_id='WAVE1',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(card))
    native=pub._native_rename;observed={}
    def barrier(sfd,s,dfd,d):
        if not observed and scenario=='late-collision':
            fd=os.open(d,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=dfd)
            try:os.write(fd,b'foreign-original');observed['inode']=os.fstat(fd).st_ino
            finally:os.close(fd)
        elif not observed and scenario=='root-replaced-before-native':
            root=storage_paths(ws)['backup_root'];root.rename(case/'retained-stock');root.mkdir();foreign=root/'foreign.JPG';foreign.write_bytes(b'foreign-original');observed['inode']=foreign.stat().st_ino
        return native(sfd,s,dfd,d)
    monkeypatch.setattr(pub,'_native_rename',barrier)
    job_to_process=claim_next_job(db,operation='folder_import')
    if scenario=='root-replaced-before-native':
        with pytest.raises(ro.RootOperationError,match='verändert|gesperrt'):
            main.process_claimed_job(job_to_process,library_context=ctx)
    else:
        main.process_claimed_job(job_to_process,library_context=ctx)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    job=get_job(db,'WAVE1')
    if scenario=='normal':
        assert job['state']=='completed',job
        assert any(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p in (ws/names['backup_directory_name']).rglob('*.JPG'))
    else:
        assert observed and job['state']!='completed',job
        assert any(p.stat().st_ino==observed['inode'] and p.read_bytes()==b'foreign-original' for p in ws.rglob('*') if p.is_file())
        assert any(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p in case.rglob('*.JPG'))
        assert list(case.rglob('move-journal.json'))
    for n in range(3):
        result=child(case,tmp_path/('restart'+str(n)))
        if scenario=='root-replaced-before-native':assert result['error'],result
        else:assert result['error'] is None,result
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        if scenario!='normal':assert any(p.stat().st_ino==observed['inode'] and p.read_bytes()==b'foreign-original' for p in ws.rglob('*') if p.is_file())
        snapshot=stable(case);(tmp_path/('snapshot'+str(n)+'.json')).write_text(json.dumps(snapshot,indent=2))
        for state in snapshot['databases'].values():assert state['integrity']=='ok' and not state['foreign_keys']
    with database_connection(db) as c:
        if scenario=='normal':
            rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==1 and rows[0]['sha256_original']==digest and rows[0]['sha256_current']==digest
