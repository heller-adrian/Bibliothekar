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

PROPOSED = "2026-07-20T14:15:30"
OLD = b"synthetic-camera-original"


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _seed_library(tmp_path, *, two_files=False):
    db = tmp_path / "kamera.sqlite3"
    ws = tmp_path / "workspace"
    root = ws / "SD-Kartensicherungen"
    source = root / "Ohne_Datum" / "IMG_0001.JPG"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(OLD)
    initialize_database(db)
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
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM files WHERE family_id=? ORDER BY id", (family_id,)
        ).fetchall()]
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
m.write_metadata_datetime = lambda path,media_type,value: Path(path).write_bytes(
    Path(path).read_bytes()+b"|corrected"
)
m.verify_metadata_datetime = lambda path,expected: {"expected_datetime":expected,"matching_tags":[{"tag":"test","value":expected}],"observed_tags":[]}
if sys.argv[3] == "after_backup":
    original=m.os.replace
    def abrupt(src,dst):
        result=original(src,dst)
        if ".metadata-before-" in str(dst):
            os._exit(42)
        return result
    m.os.replace=abrupt
elif sys.argv[3] == "after_db_commit":
    m.mark_swap_committed=lambda *_a,**_kw: os._exit(42)
elif sys.argv[3] == "after_journal_commit":
    m.recover_swap_journal=lambda *_a,**_kw: os._exit(42)
m.apply_metadata_correction(Path(sys.argv[1]),"META_BA12_TEST",workspace_root=Path(sys.argv[2]),library_id="main")
""".replace("sys.argv[3]",repr(mode))


@pytest.mark.parametrize("mode",["after_backup","after_db_commit","after_journal_commit"])
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
    if mode=="after_backup":
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
