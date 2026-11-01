"""BA-12: crash/restart recovery of synthetic metadata corrections.

All test data is generated under tmp_path. In particular, never touch NAS
photographs, production SQLite, real TrueNAS mounts or import directories.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.database import database_connection, initialize_database
from app.metadata_correction import apply_metadata_correction
from app.metadata_swap_recovery import recover_metadata_swaps, assert_no_pending_swaps
from app.storage_config import storage_paths
from tests.backend.test_0331_patch import _insert_undated_family
from tests.backend.registered_metadata_fixture import registered_metadata_fixture

PROPOSED = "2026-07-20T14:15:30"
OLD = b"synthetic-camera-original"


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _seed_library(tmp_path, *, two_files=False):
    db,ws,_registry = registered_metadata_fixture(tmp_path)
    root = ws / "SD-Kartensicherungen"
    source = root / "Ohne_Datum" / "IMG_0001.JPG"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(OLD)
    family_id, fid = _insert_undated_family(db, payload=OLD)
    with database_connection(db) as conn:
        conn.execute(
            "UPDATE files SET sha256_original=?,sha256_current=? WHERE id=?",
            (_hash(OLD), _hash(OLD), fid),
        )
        if two_files:
            side = source.with_suffix(".XMP")
            side.write_bytes(b"synthetic-sidecar")
            conn.execute(
                """INSERT INTO files(
                  job_id,family_id,original_relative_path,current_relative_path,
                  current_root_kind,original_filename,extension,media_type,
                  size_bytes,source_size_bytes,sha256_original,sha256_current,
                  capture_time_confidence,review_status,metadata_write_status,
                  created_at,updated_at
                ) VALUES ('JOB',?,'DCIM/IMG_0001.XMP',
                  'Ohne_Datum/IMG_0001.XMP','shared_workspace',
                  'IMG_0001.XMP','.XMP','xmp',?,?,?,?,
                  'missing','required','not_requested','now','now')""",
                (family_id,len(b"synthetic-sidecar"),len(b"synthetic-sidecar"),
                 _hash(b"synthetic-sidecar"),_hash(b"synthetic-sidecar")),
            )
        rows = [
            {**dict(r), "file_id": int(r["id"])}
            for r in conn.execute(
                "SELECT * FROM files WHERE family_id=? ORDER BY id", (family_id,)
            ).fetchall()
        ]
        task_id = "META_BA12_TEST"
        conn.execute(
            """INSERT INTO metadata_corrections(
                 id,area,status,source_path,source_relative_path,
                 source_filename,source_size_bytes,source_sha256,media_type,
                 detected_json,proposed_datetime,proposal_source,verification_json,
                 created_at,updated_at
            ) VALUES (?,'library','prepared',?,?,?,?,?,?,?,?,'manual','{}','now','now')""",
            (
                task_id,str(source),"Ohne_Datum/IMG_0001.JPG",
                source.name,len(OLD),_hash(OLD),"jpeg",
                json.dumps({
                    "family_id":family_id,"job_id":"JOB",
                    "family_key":"DCIM/IMG_0001","members":rows,
                }),PROPOSED,
            ),
        )
    return db,ws,source,family_id,task_id


def _child(db, ws, code):
    process = subprocess.run(
        [sys.executable,"-c",code,str(db),str(ws)],
        capture_output=True,text=True,check=False,
    )
    assert process.returncode == 42, (process.returncode,process.stdout,process.stderr)


def _child_library(mode):
    return r"""
import os,sys
from pathlib import Path
import app.metadata_correction as m
import app.metadata_swap_recovery as recovery
m.write_metadata_datetime = lambda path,media_type,value: Path(path).write_bytes(
    Path(path).read_bytes()+b"|corrected"
)
m.verify_metadata_datetime = lambda path,expected: {"expected_datetime":expected,"matching_tags":[{"tag":"test","value":expected}],"observed_tags":[]}
if sys.argv[3] in {"after_backup","after_first_replacement","after_second_backup"}:
    original=m.os.replace
    def abrupt(src,dst,**kwargs):
        result=original(src,dst,**kwargs)
        mode=sys.argv[3]
        if mode=="after_backup" and ".metadata-before-" in str(dst):
            os._exit(42)
        if mode=="after_first_replacement" and ".metadata-" in str(src) and ".metadata-before-" not in str(src) and str(dst).endswith("IMG_0001.JPG"):
            os._exit(42)
        if mode=="after_second_backup" and ".metadata-before-" in str(dst) and ".XMP." in str(dst):
            os._exit(42)
        return result
    m.os.replace=abrupt
elif sys.argv[3] == "after_db_commit":
    recovery.mark_swap_committed=lambda *_a,**_kw: os._exit(42)
elif sys.argv[3] == "after_journal_commit":
    recovery.recover_swap_journal=lambda *_a,**_kw: os._exit(42)
m.apply_metadata_correction(Path(sys.argv[1]),"META_BA12_TEST",workspace_root=Path(sys.argv[2]),library_id="main")
""".replace("sys.argv[3]",repr(mode))


@pytest.mark.parametrize("mode",[
    "after_backup","after_first_replacement","after_second_backup",
    "after_db_commit","after_journal_commit",
])
def test_0500_library_swap_restart_is_safe_at_three_crash_boundaries(tmp_path,mode):
    db,ws,source,family_id,task_id=_seed_library(tmp_path,two_files=True)
    _child(db,ws,_child_library(mode))
    root=storage_paths(ws)["metadata_root"]
    journals=list((root/".swap-journals").glob("*.json"))
    assert len(journals)==1
    before=source.read_bytes() if source.exists() else None
    state=recover_metadata_swaps(root,allowed_databases={db})
    assert state["blocked"]==0,state
    assert len(list((root/".swap-journals").glob("*.json")))==0
    with database_connection(db) as conn:
        task=conn.execute("SELECT status FROM metadata_corrections WHERE id=?",(task_id,)).fetchone()
        row=conn.execute("SELECT selected_capture_time FROM file_families WHERE id=?",(family_id,)).fetchone()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    if mode in {"after_backup","after_first_replacement","after_second_backup"}:
        assert state["rolled_back"]==1
        assert source.read_bytes()==OLD
        assert source.with_suffix(".XMP").read_bytes()==b"synthetic-sidecar"
        assert task["status"]=="blocked"
        assert row["selected_capture_time"] is None
    else:
        assert state["completed"]==1
        assert source.read_bytes()==OLD+b"|corrected"
        assert source.with_suffix(".XMP").read_bytes()==b"synthetic-sidecar|corrected"
        assert task["status"]=="completed"
        assert row["selected_capture_time"]==PROPOSED
    assert recover_metadata_swaps(root,allowed_databases={db})["completed"]==0
    assert_no_pending_swaps(root)


def test_0500_modified_source_blocks_metadata_recovery_without_destroying_bytes(tmp_path):
    db,ws,source,family_id,task_id=_seed_library(tmp_path)
    _child(db,ws,_child_library("after_backup"))
    source.write_bytes(b"foreign-new-content")
    root=storage_paths(ws)["metadata_root"]
    state=recover_metadata_swaps(root,allowed_databases={db})
    assert state["blocked"]==1
    assert source.read_bytes()==b"foreign-new-content"
    assert len(list((root/".swap-journals").glob("*.json")))==1
    with pytest.raises(Exception,match="unterbrochene"):
        assert_no_pending_swaps(root)


def test_0500_unauthorized_db_in_journal_is_blocked(tmp_path):
    db,ws,source,family_id,task_id=_seed_library(tmp_path)
    _child(db,ws,_child_library("after_backup"))
    root=storage_paths(ws)["metadata_root"]
    state=recover_metadata_swaps(root,allowed_databases=set())
    assert state["blocked"]==1
    assert not source.exists()
    assert recover_metadata_swaps(root,allowed_databases={db})["rolled_back"]==1


def test_0500_normal_library_metadata_correction_finishes_without_journal(tmp_path,monkeypatch):
    db,ws,source,family_id,task_id=_seed_library(tmp_path)
    import app.metadata_correction as m
    monkeypatch.setattr(m,"write_metadata_datetime",
      lambda path,media_type,value: Path(path).write_bytes(Path(path).read_bytes()+b"|corrected"))
    monkeypatch.setattr(m,"verify_metadata_datetime",
      lambda path,expected: {"expected_datetime":expected,"matching_tags":[{"tag":"test","value":expected}],"observed_tags":[]})
    result=apply_metadata_correction(db,task_id,workspace_root=ws,library_id="main")
    assert result["status"]=="completed"
    assert source.read_bytes()==OLD+b"|corrected"
    assert not list((storage_paths(ws)["metadata_root"]/".swap-journals").glob("*.json"))



def _seed_multiple(tmp_path):
    _db,ws,_registry=registered_metadata_fixture(tmp_path)
    root=ws/"Metadatenkorrektur"/"Mehrfachkorrektur"
    (root/"A.JPG").write_bytes(b"photo")
    (root/"B.MP4").write_bytes(b"video")
    return root


def _child_multiple(mode):
    return r"""
import os,sys
from pathlib import Path
import app.metadata_correction as m
import app.metadata_swap_recovery as recovery
from tests.backend.test_0340_patch import _fake_multiple_analysis
m.analyze_tree=_fake_multiple_analysis
m.write_metadata_datetime=lambda path,media_type,value: Path(path).write_bytes(
    Path(path).read_bytes()+("|"+value).encode()
)
m.verify_metadata_datetime=lambda path,expected: {"expected_datetime":expected,"matching_tags":[{"tag":"test","value":expected}],"observed_tags":[]}
preview=m.preview_multiple_metadata_correction(
    workspace_root=Path(sys.argv[2]),library_id="main",
    reference_relative_path="A.JPG",proposed_datetime="2026-07-21T12:30:00",
)
if sys.argv[3] in {"after_backup","after_first_replacement","after_second_backup"}:
    original=m.os.replace
    def abrupt(src,dst,**kwargs):
        result=original(src,dst,**kwargs)
        mode=sys.argv[3]
        if mode=="after_backup" and ".multiple-before-" in str(dst):
            os._exit(42)
        if mode=="after_first_replacement" and ".multiple-" in str(src) and ".multiple-before-" not in str(src) and str(dst).endswith("A.JPG"):
            os._exit(42)
        if mode=="after_second_backup" and ".multiple-before-" in str(dst) and ".MP4." in str(dst):
            os._exit(42)
        return result
    m.os.replace=abrupt
elif sys.argv[3]=="after_all_swaps":
    recovery.mark_swap_committed=lambda *_a,**_kw: os._exit(42)
elif sys.argv[3]=="after_journal_commit":
    recovery.recover_swap_journal=lambda *_a,**_kw: os._exit(42)
m.apply_multiple_metadata_correction(
    workspace_root=Path(sys.argv[2]),library_id="main",
    reference_relative_path="A.JPG",proposed_datetime="2026-07-21T12:30:00",
    expected_preview_fingerprint=preview["preview_fingerprint"],
)
""".replace("sys.argv[3]",repr(mode))


@pytest.mark.parametrize("mode",[
    "after_backup","after_first_replacement","after_second_backup",
    "after_all_swaps","after_journal_commit",
])
def test_0500_multiple_correction_recovers_at_all_commit_boundaries(tmp_path,mode):
    root=_seed_multiple(tmp_path)
    ws=root.parent.parent
    db=tmp_path/"kamera.sqlite3"
    _child(db,ws,_child_multiple(mode))
    metadata_root=storage_paths(ws)["metadata_root"]
    result=recover_metadata_swaps(metadata_root,allowed_databases=set())
    assert result["blocked"]==0,result
    if mode=="after_journal_commit":
        assert result["completed"]==1
        assert b"2026-07-21T12:30:00" in (root/"A.JPG").read_bytes()
        assert b"2026-07-21T12:35:30" in (root/"B.MP4").read_bytes()
    else:
        assert result["rolled_back"]==1
        assert (root/"A.JPG").read_bytes()==b"photo"
        assert (root/"B.MP4").read_bytes()==b"video"
    assert recover_metadata_swaps(metadata_root)["completed"]==0


def _seed_reintegration(tmp_path):
    db,ws,source,family_id,task_id=_seed_library(tmp_path)
    with database_connection(db) as conn:
        conn.execute(
            "UPDATE file_families SET selected_capture_time=?,capture_time_confidence='high' WHERE id=?",
            (PROPOSED,family_id),
        )
        conn.execute(
            """UPDATE files SET selected_capture_time=?,selected_capture_source='metadata_correction',
                   capture_time_confidence='high',metadata_write_status='written',
                   review_status='corrected' WHERE family_id=?""",
            (PROPOSED,family_id),
        )
    return db,ws,source,family_id


def _child_reintegrate(mode,family_id):
    return r"""
import os,sys
from pathlib import Path
import app.metadata_correction as m
import app.metadata_swap_recovery as recovery
m.write_metadata_datetime=lambda path,media_type,value: Path(path).write_bytes(
    Path(path).read_bytes()+b"|normalized"
)
m.verify_metadata_datetime=lambda path,expected: {"expected_datetime":expected,"matching_tags":[{"tag":"test","value":expected}],"observed_tags":[]}
m.analyze_tree=lambda root,include_other=False: {"files":[
    {"relative_path":"DCIM/IMG_0001.JPG","filename":"IMG_0001.JPG",
    "media_type":"jpeg","family_key":"DCIM/IMG_0001"}
],"families":[{"family_key":"DCIM/IMG_0001"}]}
m.build_folder_import_plan=lambda entries,analysis,root,**kw: ([
    {"source_relative_path":"DCIM/IMG_0001.JPG",
     "destination_relative_path":"2026/2026-07-20/20260720_141530_Test.JPG"}
],[],{})
if sys.argv[3] in {"after_backup","after_incoming","after_destination"}:
    old=m.os.replace
    def terminate(src,dst,**kwargs):
        result=old(src,dst,**kwargs)
        mode=sys.argv[3]
        if mode=="after_backup" and ".reintegrate-before-" in str(dst):
            os._exit(42)
        if mode=="after_incoming" and ".reintegrate-" in str(src) and ".reintegrate-before-" not in str(src) and str(dst).endswith("IMG_0001.JPG"):
            os._exit(42)
        if mode=="after_destination" and str(dst).endswith("20260720_141530_Test.JPG"):
            os._exit(42)
        return result
    m.os.replace=terminate
elif sys.argv[3]=="after_db_commit":
    recovery.mark_swap_committed=lambda *_a,**_kw: os._exit(42)
elif sys.argv[3]=="after_journal_commit":
    recovery.recover_swap_journal=lambda *_a,**_kw: os._exit(42)
m.reintegrate_library_metadata_family(
    Path(sys.argv[1]),workspace_root=Path(sys.argv[2]),
    library_id="main",family_id=int(sys.argv[4]),
)
""".replace("sys.argv[3]",repr(mode)).replace("sys.argv[4]",str(family_id))


@pytest.mark.parametrize("mode",[
    "after_backup","after_incoming","after_destination",
    "after_db_commit","after_journal_commit",
])
def test_0500_reintegration_survives_swap_and_db_commit_crashes(tmp_path,mode):
    db,ws,source,family_id=_seed_reintegration(tmp_path)
    _child(db,ws,_child_reintegrate(mode,family_id))
    metadata_root=storage_paths(ws)["metadata_root"]
    result=recover_metadata_swaps(metadata_root,allowed_databases={db})
    assert result["blocked"]==0,result
    destination=ws/"SD-Kartensicherungen"/"2026/2026-07-20/20260720_141530_Test.JPG"
    with database_connection(db) as conn:
        file=conn.execute("SELECT current_relative_path FROM files WHERE family_id=?",(family_id,)).fetchone()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    if mode in {"after_backup","after_incoming","after_destination"}:
        assert result["rolled_back"]==1
        assert source.read_bytes()==OLD
        assert not destination.exists()
        assert file["current_relative_path"]=="Ohne_Datum/IMG_0001.JPG"
    else:
        assert result["completed"]==1
        assert not source.exists()
        assert destination.read_bytes()==OLD+b"|normalized"
        assert file["current_relative_path"]=="2026/2026-07-20/20260720_141530_Test.JPG"
