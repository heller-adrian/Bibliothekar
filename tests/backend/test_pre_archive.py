from pathlib import Path
import hashlib,pytest
from app.archive_rename_guidance import qualify_rename


@pytest.mark.parametrize('fault',[None,'unknown','empty_dir','symlink','changed','target','nonrename','mixed','missing_doc'])
def test_rename_guidance_requires_complete_live_inventory(tmp_path,fault):
    archive=tmp_path/'archive';work=tmp_path/'work';(archive/'2026/Old/All').mkdir(parents=True);work.mkdir()
    photo=archive/'2026/Old/All/A.JPG';photo.write_bytes(b'original')
    doc=archive/'2026/Old/event.json';doc.write_bytes(b'{"old":true}')
    prepared=work/'event.json';prepared.write_bytes(b'{"new":true}')
    meta=lambda p:{'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    row={'action':'move','old_path':'2026/Old/All/A.JPG','new_path':'2026/New/All/A.JPG','expected_size_bytes':8,'expected_sha256':meta(photo)['sha256']}
    original_doc={'relative_path':'2026/Old/event.json',**meta(doc)}
    if fault=='unknown':(photo.parent/'foreign.txt').write_bytes(b'preserve')
    if fault=='symlink':(photo.parent/'link').symlink_to(photo)
    if fault=='changed':photo.write_bytes(b'foreign')
    if fault=='target':(archive/'2026/New').mkdir()
    if fault=='nonrename':row['new_path']='2026/New/Other/A.JPG'
    if fault=='empty_dir':(archive/'2026/Old/unrecorded').mkdir()
    if fault=='mixed':row['action']='delete'
    if fault=='missing_doc':original_doc=None
    before={str(p):p.read_bytes() for p in archive.rglob('*') if p.is_file()}
    result=qualify_rename(archive,[row],current_document=original_doc,replacement=prepared,replacement_meta=meta(prepared),document_target='2026/New/event.json',archive_label='/real-archive',work_root=work,work_label='/real-work')
    assert bool(result)==(fault is None)
    assert {str(p):p.read_bytes() for p in archive.rglob('*') if p.is_file()}==before
    if result:assert [op['kind'] for op in result]==['rename_archive_folder','replace_event_document']
