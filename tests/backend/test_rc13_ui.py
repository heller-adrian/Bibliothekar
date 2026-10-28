"""Path presentation and manual-delete advice never authorize archive writes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import main
from app.archive_delete_guidance import qualify_event_folder
from app.workspace_layout import ensure_workspace_layout

@pytest.mark.parametrize('primary',[True,False])
def test_assistant_receives_real_selected_library_paths(tmp_path,monkeypatch,primary):
    context=SimpleNamespace(archive_root=tmp_path/'Businessarchiv',work_root=tmp_path/'workspace/Library Workspaces/business',workspace_root=tmp_path/'workspace',is_main=primary)
    monkeypatch.setattr(main,'current_library_context',lambda:context)
    monkeypatch.setattr(main,'current_archive_root',lambda:context.archive_root)
    monkeypatch.setattr(main,'current_workspace_root',lambda:context.workspace_root)
    monkeypatch.setattr(main,'current_database_file',lambda:tmp_path/'db')
    monkeypatch.setattr(main,'workspace_backup_root',lambda ws:ws/'SD Card Backups')
    monkeypatch.setattr(main,'build_archive_change_assistant',lambda *a,**kw:kw)
    data=json.loads(main.api_get_change_request_assistant('CR').body)
    assert data['archive_display_root']==str(context.archive_root)
    assert data['work_display_root']==str(context.work_root)
    assert data['backup_display_root']==str(context.workspace_root/'SD Card Backups')

@pytest.mark.parametrize('change',[None,'unknown','symlink','changed','copy_missing','untracked_baseline','unknown_directory'])
def test_whole_event_advice_requires_complete_verified_inventory(tmp_path,monkeypatch,change):
    from app.archive_reversal import _manifest_path
    ws=tmp_path/'workspace';ws.mkdir();layout=ensure_workspace_layout(ws)
    archive=tmp_path/'archive';folder=archive/'2026/Event';folder.mkdir(parents=True)
    photo=folder/'A.JPG';photo.write_bytes(b'camera')
    doc=folder/'event.json';doc.write_bytes(b'{}')
    copy=Path(layout['backup_root'])/'Released Archive Files/A.JPG';copy.parent.mkdir();copy.write_bytes(b'camera')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'change_request_id':'CR','delete_event':True,'original_root':'2026/Event','original_directories':['2026/Event'],
              'original_file_paths':['2026/Event/A.JPG','2026/Event/event.json'],
              'event_json':{'relative_path':'2026/Event/event.json','size_bytes':2,'sha256':digest(doc)}}
    path=_manifest_path(ws,'CR');path.parent.mkdir(parents=True);path.write_text(json.dumps(manifest))
    stock={'copy_verified':True,'rows':[{'old_path':'2026/Event/A.JPG','expected_size_bytes':6,'expected_sha256':digest(photo),'workspace_release_path':'Released Archive Files/A.JPG'}]}
    if change=='unknown':(folder/'unknown.txt').write_bytes(b'preserve')
    if change=='symlink':(folder/'link').symlink_to(photo)
    if change=='changed':photo.write_bytes(b'changed')
    if change=='copy_missing':copy.unlink()
    if change=='unknown_directory':(folder/'foreign').mkdir()
    if change=='untracked_baseline':
        manifest['original_file_paths'].append('2026/Event/foreign');path.write_text(json.dumps(manifest))
    before={str(p):p.read_bytes() for p in archive.rglob('*') if p.is_file()}
    result=qualify_event_folder(tmp_path/'db',archive,ws,'CR',stock)
    assert result['qualified'] is (change is None),result
    assert {str(p):p.read_bytes() for p in archive.rglob('*') if p.is_file()}==before
