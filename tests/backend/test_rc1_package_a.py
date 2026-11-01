"""Synthetic RC1 B02/B03/B06 regressions; no NAS access."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.database import initialize_database, database_connection
from app.workspace_layout import ensure_workspace_layout
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot
from app.event_structure_changes import detect_event_structure_change, prepare_archived_structure_change, verify_archived_structure_change
from tests.backend.test_0263_event_inventory import seed_job, seed_event, seed_family, NOW


def archived_change(tmp_path):
    db = tmp_path/'db.sqlite3'; ws = tmp_path/'workspace'; ws.mkdir()
    initialize_database(db); ensure_workspace_layout(ws)
    archive = tmp_path/'archive'; root = archive/'2026/07-23 - Trip'
    (root/'Alle').mkdir(parents=True); (root/'Export').mkdir()
    (root/'Alle/A.JPG').write_bytes(b'original camera bytes')
    with database_connection(db) as c:
        seed_job(c); seed_event(c, status='archived')
        seed_family(c, content=b'original camera bytes', current_path='2026/07-23 - Trip/Alle/A.JPG')
        ensure_event_layout_snapshot(c, 'e', now=NOW)
    (root/'event.json').write_text(json.dumps({'event': {'id':'e'}}))
    root = root.rename(root.with_name('07-23 - Renamed'))
    scan_event_inventory(db, archive, 'j', 'e', root_kind='camera_archive', persist=True, fast_refresh=False)
    change = detect_event_structure_change(db, 'e')
    assert change and not change['detected']['blocked']
    prepared = prepare_archived_structure_change(db, ws, change['id'], input_path='Alle', app_version='1.0.0-rc.1')
    (root/'event.json').write_bytes(Path(prepared['prepared_event_json_path']).read_bytes())
    return db, ws, archive, root, change, prepared


def test_b02_archived_root_rename(tmp_path):
    db, ws, archive, root, change, _ = archived_change(tmp_path)
    before = hashlib.sha256((root/'Alle/A.JPG').read_bytes()).hexdigest()
    result = verify_archived_structure_change(db, archive, ws, change['id'])
    assert result['status'] == 'completed'
    for _ in range(3):
        initialize_database(db)
        with database_connection(db) as c:
            assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
            assert not c.execute('pragma foreign_key_check').fetchall()
            assert c.execute("select folder_name from events where id='e'").fetchone()[0] == root.name
            assert c.execute("select current_relative_path from files").fetchone()[0] == '2026/'+root.name+'/Alle/A.JPG'
            assert c.execute('select status from event_structure_changes where id=?',(change['id'],)).fetchone()[0] == 'completed'
    assert hashlib.sha256((root/'Alle/A.JPG').read_bytes()).hexdigest() == before


@pytest.mark.parametrize('proposed,offset', [('2026-10-23T20:45:07','+02:00'), ('2026-12-23T20:45:07','+01:00'), ('2026-07-22T10:14:04+03:00','+03:00')])
def test_b03_written_timestamps_agree(tmp_path, proposed, offset):
    from app.metadata_correction import write_metadata_datetime, verify_metadata_datetime, scan_metadata_area, metadata_area_paths
    from app.metadata import analyze_tree
    ws=tmp_path/'workspace';ws.mkdir();ensure_workspace_layout(ws)
    root=metadata_area_paths(area='general',workspace_root=ws,library_id='main',create=True)['input_root']
    p=root/'20260722_101404_Synthetic.JPG';Image.new('RGB',(8,8),'red').save(p)
    subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:07:22 10:14:04','-EXIF:OffsetTimeOriginal=+03:00',str(p)],check=True,capture_output=True)
    write_metadata_datetime(p,'image',proposed);verify_metadata_datetime(p,proposed)
    row=analyze_tree(root,include_other=False)['files'][0]
    assert row['selected_capture_time'] == proposed[:19]+offset
    assert row['capture_time_confidence'] != 'conflict'
    scan=scan_metadata_area(area='general',workspace_root=ws,library_id='main')['files'][0]
    assert scan['preferred_suggestion']['datetime'][:19] == proposed[:19]


def test_b06_error_remains_in_archive_dialog():
    import app.events_ui as ui
    source = Path(ui.__file__).read_text()
    start=source.index('    async function deleteEvent(')
    end=source.index('    eventEditClose.addEventListener',start+10)
    function=source[start:end]
    script=r'''
const assert=require('node:assert/strict');
const currentEvents=[{id:'e',_job_id:'j',status:'archived',name:'Trip'}];
const window={BibliothekarI18n:{confirmAsync:async()=>true}};
const changeRequestTitle={},changeRequestSubtitle={},changeRequestBody={};
const changeRequestDialog={open:false,showModal(){this.open=true},close(){this.open=false}};
const statusElement={classList:{remove(){}}};
function setEventOperationBusy(){};
async function requestJson(){throw new Error('Open structure journal <synthetic>')};
''' + function + r'''
(async()=>{try{await deleteEvent('e','j')}catch(error){assert.equal(error.message,'Open structure journal <synthetic>')}
assert.equal(changeRequestDialog.open,true);
assert.ok((changeRequestBody.textContent||'').includes('Open structure journal <synthetic>'));
})();
'''
    result=subprocess.run(['node','-e',script],text=True,capture_output=True)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('conflict', ['duplicate','wrong-document','missing-document','changed-photo','symlink','replaced-root'])
def test_b02_rejects_unverified_archive(tmp_path, monkeypatch, conflict):
    import shutil
    import app.event_structure_changes as changes
    db, ws, archive, root, change, prepared = archived_change(tmp_path)
    original = (root/'Alle/A.JPG').read_bytes()
    if conflict=='duplicate': shutil.copytree(root,root.with_name('Other'))
    elif conflict=='wrong-document': (root/'event.json').write_text('{"event":{"id":"foreign"}}')
    elif conflict=='missing-document': (root/'event.json').unlink()
    elif conflict=='changed-photo': (root/'Alle/A.JPG').write_bytes(b'externally changed')
    elif conflict=='symlink':
        saved=root.rename(root.with_name('Moved'));root.symlink_to(saved,target_is_directory=True)
    else:
        original_scan=changes.scan_event_inventory
        def replacement(*args,**kwargs):
            inventory=original_scan(*args,**kwargs)
            moved=root.rename(root.with_name('Moved'))
            shutil.copytree(moved,root)
            return inventory
        monkeypatch.setattr(changes,'scan_event_inventory',replacement)
    with pytest.raises(changes.EventStructureChangeError):
        changes.verify_archived_structure_change(db,archive,ws,change['id'])
    assert Path(prepared['prepared_event_json_path']).is_file()
    with database_connection(db) as c:
        assert c.execute('select status from event_structure_changes where id=?',(change['id'],)).fetchone()[0]=='prepared'
        assert c.execute("select folder_name from events where id='e'").fetchone()[0]=='07-23 - Trip'
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not c.execute('pragma foreign_key_check').fetchall()
    if conflict!='changed-photo': assert (root/'Alle/A.JPG').read_bytes()==original


def test_b06_delete_gate_opens_only_after_verification(tmp_path):
    from app.database import delete_planned_event
    db,ws,archive,root,change,prepared=archived_change(tmp_path)
    original=(root/'Alle/A.JPG').read_bytes()
    with pytest.raises(ValueError,match='Manuelle Ereignisänderung'):
        delete_planned_event(db,'j','e',archive_root=archive)
    assert (root/'Alle/A.JPG').read_bytes()==original
    verify_archived_structure_change(db,archive,ws,change['id'])
    result=delete_planned_event(db,'j','e',archive_root=archive)
    assert result['change_request_id']
    assert (root/'Alle/A.JPG').read_bytes()==original


@pytest.mark.parametrize('candidate_choice',[False,True])
def test_b03_real_correction_rescan_and_original_backup(tmp_path,monkeypatch,candidate_choice):
    import app.metadata_correction as m
    from app.metadata import analyze_tree
    ws=tmp_path/'workspace';ws.mkdir();ensure_workspace_layout(ws)
    db=tmp_path/'db.sqlite3';initialize_database(db)
    root=m.metadata_area_paths(area='general',workspace_root=ws,library_id='main',create=True)['input_root']
    p=root/'20260722_101404_Synthetic.JPG';Image.new('RGB',(8,8),'red').save(p)
    raw=root/p.with_suffix('.RAF').name;raw.write_bytes(b'untouched synthetic RAW')
    subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:07:22 10:14:04','-EXIF:OffsetTimeOriginal=+03:00',str(p)],check=True,capture_output=True)
    original=p.read_bytes();raw_before=raw.read_bytes()
    kwargs={}; proposed='2026-12-23T14:15:16'
    if candidate_choice:
        scan=m.scan_metadata_area(area='general',workspace_root=ws,library_id='main',database_path=db)
        row=next(x for x in scan['files'] if x['relative_path']==p.name)
        candidate=next(x for x in row['metadata_candidates'] if x['confidence']=='low' and x['usable'])
        proposed=candidate['normalized_datetime'][:19]
        kwargs['proposal_source_tag']=candidate['tag_name']
    backup_checks=[]
    complete=m._complete_task
    def complete_with_original(*args,**kwargs):
        # The original is mandatory until the verified SQLite commit. Normal
        # committed recovery subsequently removes this temporary swap backup.
        assert any(f.is_file() and f.read_bytes()==original for f in ws.rglob('*'))
        backup_checks.append(True)
        return complete(*args,**kwargs)
    monkeypatch.setattr(m,'_complete_task',complete_with_original)
    result=m.execute_metadata_correction(db,area='general',relative_path=p.name,proposed_datetime=proposed,workspace_root=ws,library_id='main',**kwargs)
    assert result['status']=='completed'
    scan=m.scan_metadata_area(area='general',workspace_root=ws,library_id='main',database_path=db)
    row=next(x for x in scan['files'] if x['relative_path']==p.name)
    assert row['capture_time_confidence']!='conflict'
    assert row['preferred_suggestion']['datetime'][:19]==proposed
    assert raw.read_bytes()==raw_before
    assert backup_checks == [True]
    task=m.get_metadata_correction(db,result['id'])
    assert task['verification']['matching_tags']
    with database_connection(db) as c:
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not c.execute('pragma foreign_key_check').fetchall()
    # Separate interpreter starts read the persisted task and output, with no
    # test monkeypatch or reused SQLite connection carrying transient state.
    code='''import sys,hashlib
from pathlib import Path
from app.database import initialize_database,database_connection
p=Path(sys.argv[1]);initialize_database(p)
with database_connection(p) as c:
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 assert not c.execute('pragma foreign_key_check').fetchall()
 assert c.execute('select status from metadata_corrections where id=?',(sys.argv[2],)).fetchone()[0]=='completed'
assert hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()==sys.argv[4]
'''
    import sys
    for _ in range(3):
        subprocess.run([sys.executable,'-c',code,str(db),result['id'],str(p),hashlib.sha256(p.read_bytes()).hexdigest()],check=True,capture_output=True,text=True)


def test_b03_verifier_rejects_conflicting_written_xmp(tmp_path):
    from app.metadata_correction import write_metadata_datetime, verify_metadata_datetime, MetadataCorrectionError
    p=tmp_path/'photo.jpg';Image.new('RGB',(8,8),'blue').save(p)
    proposed='2026-10-23T20:45:07'
    write_metadata_datetime(p,'jpeg',proposed)
    subprocess.run(['exiftool','-overwrite_original','-XMP-exif:DateTimeOriginal=2026:10:23 20:45:07+03:00',str(p)],check=True,capture_output=True)
    before=p.read_bytes()
    with pytest.raises(MetadataCorrectionError): verify_metadata_datetime(p,proposed)
    assert p.read_bytes()==before


def test_b03_library_real_write_then_explicit_reintegration(tmp_path):
    import app.metadata_correction as m
    from app.storage_config import storage_paths
    from tests.backend.test_0331_patch import _insert_undated_family
    from tests.backend.registered_metadata_fixture import registered_metadata_fixture
    db,ws,_registry=registered_metadata_fixture(tmp_path)
    paths=storage_paths(ws)
    source=paths['backup_root']/'Ohne_Datum/IMG_0001.JPG'
    source.parent.mkdir(parents=True,exist_ok=True)
    Image.new('RGB',(8,8),'green').save(source)
    before=source.read_bytes()
    family,file_id=_insert_undated_family(db,payload=before)
    with database_connection(db) as c:
        digest=hashlib.sha256(before).hexdigest()
        c.execute('update files set sha256_original=?,sha256_current=? where id=?',(digest,digest,file_id))
    completed=m.execute_metadata_correction(db,area='library',relative_path='Ohne_Datum/IMG_0001.JPG',family_id=family,proposed_datetime='2026-12-23T14:15:16',workspace_root=ws,library_id='main',allowed_job_ids={'JOB'})
    assert completed['status']=='completed' and source.exists()
    after=hashlib.sha256(source.read_bytes()).hexdigest()
    scan=m.scan_metadata_area(area='library',workspace_root=ws,library_id='main',database_path=db,allowed_job_ids={'JOB'})
    assert scan['files'][0]['reintegration_ready']
    result=m.reintegrate_library_metadata_family(db,workspace_root=ws,library_id='main',family_id=family)
    assert result['family_id']==family and not source.exists()
    with database_connection(db) as c:
        row=c.execute('select current_relative_path,sha256_current,selected_capture_time from files where id=?',(file_id,)).fetchone()
        assert row['selected_capture_time'].startswith('2026-12-23T14:15:16')
        assert hashlib.sha256((paths['backup_root']/row['current_relative_path']).read_bytes()).hexdigest()==after
        assert row['sha256_current']==after
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not c.execute('pragma foreign_key_check').fetchall()


@pytest.mark.parametrize('boundary',['before-commit','after-commit'])
def test_b02_sigkill_retry_preserves_original_and_journal(tmp_path,boundary):
    import sys
    from app.event_structure_changes import cleanup_completed_archived_structure_helpers
    db,ws,archive,root,change,prepared=archived_change(tmp_path)
    original=(root/'Alle/A.JPG').read_bytes()
    code='''import sys,os,signal
from pathlib import Path
import app.event_structure_changes as m
boundary=sys.argv[1]
if boundary=='before-commit':
 real=m._apply_confirmed_state
 def stop(*a,**kw):
  real(*a,**kw);os.kill(os.getpid(),signal.SIGKILL)
 m._apply_confirmed_state=stop
else:
 def stop(*a,**kw):os.kill(os.getpid(),signal.SIGKILL)
 m.cleanup_completed_archived_structure_helpers=stop
m.verify_archived_structure_change(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),sys.argv[5])
'''
    child=subprocess.run([sys.executable,'-c',code,boundary,str(db),str(archive),str(ws),change['id']],capture_output=True,text=True)
    assert child.returncode==-9,child.stderr
    assert (root/'Alle/A.JPG').read_bytes()==original
    assert Path(prepared['prepared_event_json_path']).is_file()
    with database_connection(db) as c:
        expected='prepared' if boundary=='before-commit' else 'completed'
        assert c.execute('select status from event_structure_changes where id=?',(change['id'],)).fetchone()[0]==expected
    if boundary=='before-commit':verify_archived_structure_change(db,archive,ws,change['id'])
    else:cleanup_completed_archived_structure_helpers(db,ws,change_id=change['id'])
    check='''import sys,hashlib
from pathlib import Path
from app.database import initialize_database,database_connection
p=Path(sys.argv[1]);initialize_database(p)
with database_connection(p) as c:
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 assert not c.execute('pragma foreign_key_check').fetchall()
 assert c.execute('select status from event_structure_changes where id=?',(sys.argv[2],)).fetchone()[0]=='completed'
 assert c.execute("select folder_name from events where id='e'").fetchone()[0]=='07-23 - Renamed'
assert hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()==sys.argv[4]
'''
    for _ in range(3):subprocess.run([sys.executable,'-c',check,str(db),change['id'],str(root/'Alle/A.JPG'),hashlib.sha256(original).hexdigest()],check=True,capture_output=True,text=True)
    assert not Path(prepared['prepared_event_json_path']).exists()
