"""Real ExifTool correction → durable catalogue → reintegration, synthetic media."""
from pathlib import Path
import hashlib,json,subprocess
import pytest
from PIL import Image
from app import metadata_correction as mc
from app.database import database_connection
from tests.backend.test_0500_metadata_swap_recovery import _seed_library


def real_family(tmp_path,stamp):
    db,ws,source,family,task=_seed_library(tmp_path)
    Image.new('RGB',(8,8),'blue').save(source)
    mc.write_metadata_datetime(source,'jpeg',stamp)
    raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    with database_connection(db) as c:
        c.execute('UPDATE files SET size_bytes=?,source_size_bytes=?,sha256_original=?,sha256_current=?',(len(raw),len(raw),sha,sha))
        row=c.execute('SELECT detected_json FROM metadata_corrections WHERE id=?',(task,)).fetchone()
        detected=json.loads(row[0])
        for member in detected['members']:member.update(size_bytes=len(raw),source_size_bytes=len(raw),sha256_original=sha,sha256_current=sha)
        c.execute('UPDATE metadata_corrections SET source_size_bytes=?,source_sha256=?,proposed_datetime=?,proposal_source=?,detected_json=? WHERE id=?',(len(raw),sha,stamp,'metadata',json.dumps(detected),task))
    return db,ws,source,family,task


@pytest.mark.parametrize('stamp',['2025-12-07T15:04:37+13:00','2025-12-07T15:04:37+01:00','2025-12-07T15:04:37+00:00','2025-07-07T15:04:37+02:00','2025-12-07T15:04:37'])
def test_offset_survives_correction_and_reintegration(tmp_path,stamp):
    db,ws,source,family,task=real_family(tmp_path,stamp)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    mc.apply_metadata_correction(db,task,workspace_root=ws,library_id='main')
    mc.verify_metadata_datetime(source,stamp)
    result=mc.reintegrate_library_metadata_family(db,workspace_root=ws,library_id='main',family_id=family)
    assert result['selected_capture_time']==stamp
    with database_connection(db) as c:
        row=c.execute('SELECT * FROM files').fetchone()
        assert row['selected_capture_time']==stamp
        assert row['sha256_original']==before
        destination=ws/'SD-Kartensicherungen'/row['current_relative_path']
        assert destination.is_file() and not source.exists()
        assert hashlib.sha256(destination.read_bytes()).hexdigest()==row['sha256_current']
        assert '2025/2025-' in row['current_relative_path']
    mc.verify_metadata_datetime(destination,stamp)


@pytest.mark.parametrize('proof',['valid','missing','wrong_hash','wrong_job'])
def test_rc14_truncated_catalogue_requires_exact_completed_receipt(tmp_path,proof):
    stamp='2025-12-07T15:04:37+13:00'
    db,ws,source,family,task=real_family(tmp_path,stamp)
    mc.apply_metadata_correction(db,task,workspace_root=ws,library_id='main')
    # Reproduce RC14's durable catalogue; the real correction task retained +13.
    with database_connection(db) as c:
        c.execute('UPDATE file_families SET selected_capture_time=?',(stamp[:19],))
        c.execute('UPDATE files SET selected_capture_time=?',(stamp[:19],))
        if proof=='missing':c.execute("UPDATE metadata_corrections SET status='blocked'")
        if proof in ('wrong_hash','wrong_job'):
            row=c.execute('SELECT verification_json FROM metadata_corrections').fetchone()
            receipt=json.loads(row[0])
            if proof=='wrong_hash':receipt['members'][0]['output_sha256']='f'*64
            else:receipt['job_id']='foreign-job'
            c.execute('UPDATE metadata_corrections SET verification_json=?',(json.dumps(receipt),))
    before=source.read_bytes()
    if proof=='valid':
        result=mc.reintegrate_library_metadata_family(db,workspace_root=ws,library_id='main',family_id=family)
        assert result['selected_capture_time']==stamp
    else:
        with pytest.raises(mc.MetadataCorrectionError):
            mc.reintegrate_library_metadata_family(db,workspace_root=ws,library_id='main',family_id=family)
        assert source.read_bytes()==before


def test_conflicting_xmp_is_not_silently_repaired_on_reintegration(tmp_path):
    stamp='2025-12-07T15:04:37+13:00'
    db,ws,source,family,task=real_family(tmp_path,stamp)
    mc.apply_metadata_correction(db,task,workspace_root=ws,library_id='main')
    subprocess.run(['exiftool','-overwrite_original','-XMP:CreateDate=2025:12:07 15:04:37+01:00',str(source)],check=True,capture_output=True)
    raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    # Model an independently catalogued file with contradictory tags, not a hash bypass.
    with database_connection(db) as c:c.execute('UPDATE files SET sha256_current=?,size_bytes=?',(sha,len(raw)))
    with pytest.raises(mc.MetadataCorrectionError,match='Expected:.*Observed:'):
        mc.reintegrate_library_metadata_family(db,workspace_root=ws,library_id='main',family_id=family)
    assert source.read_bytes()==raw


@pytest.mark.parametrize('stamp',['2025-03-30T02:30:00','2025-10-26T02:30:00'])
def test_ambiguous_or_nonexistent_local_time_needs_explicit_offset(tmp_path,stamp):
    p=tmp_path/'untouched.JPG';p.write_bytes(b'never submit invalid local time to ExifTool')
    before=p.read_bytes()
    with pytest.raises(mc.MetadataCorrectionError,match='UTC-Offset'):
        mc.write_metadata_datetime(p,'jpeg',stamp)
    assert p.read_bytes()==before
