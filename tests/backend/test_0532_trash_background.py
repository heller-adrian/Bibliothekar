"""0.53.2 integration: persistent trash queue -> real file import -> catalogue -> cleanup."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.database import (
    database_connection, get_job, claim_next_job,
    store_metadata_analysis, update_import_file_paths, update_job_progress,
)
from app.folder_import import preflight_folder_import, run_folder_import_job, PipelineError
from app.trash import reconcile_trash_inventory
from app.trash_import import (
    queue_trash_restore, prepare_queued_trash_restore,
    cleanup_successful_trash_import, resume_safe_queued_trash_restores,
    protected_trash_paths,
)
from app.background_activity import current_activity
from tests.backend.test_0440_trash import _fixture, _file


def test_0532_preflight_internal_source_is_explicitly_authorized(tmp_path):
    workspace=tmp_path/"workspace"
    stage=workspace/"Metadaten"/".trash-import"/"job"
    stage.mkdir(parents=True)
    (stage/"IMG.JPG").write_bytes(b"image")
    with pytest.raises(PipelineError,match="ineinander"):
        preflight_folder_import(
            stage,workspace,workspace,
            processing_buffer_percent=0,safety_reserve_gib=0,
        )
    info=preflight_folder_import(
        stage,workspace,workspace,
        processing_buffer_percent=0,safety_reserve_gib=0,
        allow_workspace_source=True,
    )
    assert info["files_and_directories"]==1
    # Reverse nesting and exact workspace remain forbidden with the flag.
    with pytest.raises(PipelineError,match="ineinander"):
        preflight_folder_import(
            workspace,workspace,workspace,processing_buffer_percent=0,
            safety_reserve_gib=0,allow_workspace_source=True,
        )


def test_0532_end_to_end_unknown_jpeg_reaches_real_daily_stock(tmp_path,monkeypatch):
    db,workspace,paths=_fixture(tmp_path,monkeypatch)
    trash=Path(paths["trash_root"])
    (trash/"2026-01-05").mkdir()
    original=trash/"2026-01-05"/"20260105_065044_iPhone-12-mini.JPG"
    data=b"\xff\xd8" + b"camera-restoration-regression"*30 + b"\xff\xd9"
    original.write_bytes(data)
    job=queue_trash_restore(db,workspace,["2026-01-05/"+original.name])
    assert job["queued_file_count"]==1
    assert original.read_bytes()==data
    assert get_job(db,job["job_id"])["state"]=="queued"
    activity=current_activity(db,db)["operations"]
    assert any(item["id"]==job["job_id"] and item["active"] for item in activity)
    claim=claim_next_job(db,operation="trash_import")
    assert claim and claim["id"]==job["job_id"]
    prepared=prepare_queued_trash_restore(db,[db],workspace,job["job_id"])
    assert prepared["unknown_file_count"]==1
    assert prepared["known_restored_count"]==0
    source=Path(claim["source_path"])
    stage_file=source/"2026-01-05"/original.name
    assert stage_file.read_bytes()==data
    import app.metadata as metadata
    def fake_exif(root,**kwargs):
        return [{"SourceFile":str(root/"2026-01-05"/original.name),"EXIF:DateTimeOriginal":"2026:01:05 06:50:44"}]
    monkeypatch.setattr(metadata,"run_exiftool",fake_exif)
    def persist_metadata(analysis,checksums):
        store_metadata_analysis(db,job["job_id"],analysis,checksums,finalize_job=False)
    def persist_paths(plan):
        update_import_file_paths(db,job["job_id"],plan,
                                 working_path=str(Path(paths["backup_root"])))
    result=run_folder_import_job(
        source=source,workspace=workspace,pool_probe_path=workspace,
        log_dir=tmp_path/"logs",processing_buffer_percent=0,safety_reserve_gib=0,
        job_id=job["job_id"],central_stock=True,allow_workspace_source=True,
        metadata_callback=persist_metadata,path_callback=persist_paths,
        progress_callback=lambda state,stage,current,total,message:
            update_job_progress(db,job["job_id"],state=state,stage=stage,
                                current=current,total=total,message=message),
    )
    organization=result["organization"]
    assert organization["file_count"]==1
    relative=organization["destinations"][0]
    target=Path(paths["backup_root"])/relative
    assert target.read_bytes()==data
    imported=organization["imported_source_files"]
    cleaned=cleanup_successful_trash_import(workspace,job["job_id"],imported)
    assert cleaned["removed_file_count"]==1 and cleaned["skipped"]==[]
    assert not original.exists()
    with database_connection(db) as connection:
        rows=connection.execute(
            "SELECT f.current_root_kind,f.current_relative_path,ff.selected_capture_time "
            "FROM files f JOIN file_families ff ON ff.id=f.family_id "
            "WHERE f.job_id=?",(job["job_id"],)
        ).fetchall()
    assert len(rows)==1
    assert rows[0]["current_root_kind"]=="shared_workspace"
    assert rows[0]["current_relative_path"]==relative
    assert str(rows[0]["selected_capture_time"]).startswith("2026-01-05")


def test_0532_known_file_queued_and_restored_in_worker(tmp_path,monkeypatch):
    db,workspace,paths=_fixture(tmp_path,monkeypatch)
    digest_data=b"known-photo"
    file_id=_file(db,"2026/2026-10-08/K.JPG",digest_data)
    trash=Path(paths["trash_root"])/"Old"
    trash.mkdir()
    (trash/"K.JPG").write_bytes(digest_data)
    reconcile_trash_inventory(db,workspace)
    q=queue_trash_restore(db,workspace,["Old/K.JPG"])
    assert get_job(db,q["job_id"])["state"]=="queued"
    claim=claim_next_job(db,operation="trash_import")
    assert claim["id"]==q["job_id"]
    res=prepare_queued_trash_restore(db,[db],workspace,q["job_id"])
    assert res["known_restored_count"]==1
    assert res["unknown_file_count"]==0
    assert not (trash/"K.JPG").exists()
    with database_connection(db) as c:
        row=c.execute(
            "SELECT job_id,current_root_kind,current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        assert row["job_id"]=="J"
        assert row["current_root_kind"]=="shared_workspace"
        assert (Path(paths["backup_root"])/row["current_relative_path"]).read_bytes()==digest_data


def test_0532_staged_and_inflight_sources_cannot_be_deleted(tmp_path,monkeypatch):
    db,workspace,paths=_fixture(tmp_path,monkeypatch)
    root=Path(paths["trash_root"])
    (root/"J.JPG").write_bytes(b"reserved")
    queued=queue_trash_restore(db,workspace,["J.JPG"])
    assert "J.JPG" in protected_trash_paths(db,workspace)
    assert queued["job_id"].startswith("TRASH_IMPORT_")
    with pytest.raises(Exception,match="bereits"):
        queue_trash_restore(db,workspace,["J.JPG"])
    with database_connection(db) as c:
        c.execute("UPDATE jobs SET state='interrupted' WHERE id=?",(queued["job_id"],))
    assert resume_safe_queued_trash_restores(db,workspace)==1
    assert get_job(db,queued["job_id"])["state"]=="queued"
    assert (root/"J.JPG").read_bytes()==b"reserved"



def test_0532_actual_claimed_worker_finishes_trash_restore(tmp_path,monkeypatch):
    """Contract that failed in 0.53.1: queue -> main worker -> real SSD bytes."""
    from app import main
    from app.library_registry import list_active_library_contexts
    from tests.backend.test_0400_import_backup_controls import _foundation
    from app.storage_config import storage_paths

    database,registry,workspace=_foundation(tmp_path)
    contexts=list_active_library_contexts(registry)
    assert contexts
    context=next(x for x in contexts if x.library_id=="main")
    monkeypatch.setattr(main,"DATABASE_FILE",database)
    monkeypatch.setattr(main,"REGISTRY_DATABASE_FILE",registry)
    monkeypatch.setattr(main,"WORKSPACE_PATH",workspace)
    monkeypatch.setattr(main,"LOG_PATH",tmp_path/"logs")
    monkeypatch.setattr(main,"MAIN_LIBRARY_CONTEXT",context)
    monkeypatch.setattr(main,"load_settings",
                        lambda:{"storage":{"processing_buffer_percent":0,
                                           "safety_reserve_gib":0}})
    import app.metadata as metadata
    monkeypatch.setattr(metadata,"run_exiftool",
        lambda root,**kw:[
            {"SourceFile":str(root/"2026-01-05"/"CAM.JPG"),
             "EXIF:DateTimeOriginal":"2026:01:05 06:50:44"}
        ])
    trash=Path(storage_paths(workspace)["trash_root"])/"2026-01-05"
    trash.mkdir(parents=True,exist_ok=True)
    source=trash/"CAM.JPG"
    data=b"\xff\xd8"+b"actual-worker-bytes"*20+b"\xff\xd9"
    source.write_bytes(data)
    info=queue_trash_restore(database,workspace,["2026-01-05/CAM.JPG"])
    job_id=info["job_id"]
    claimed=claim_next_job(database,operation="trash_import")
    assert claimed and claimed["id"]==job_id
    main.process_claimed_job(claimed,library_context=context)
    final=get_job(database,job_id)
    assert final["state"]=="completed",final.get("error_message")
    with database_connection(database) as conn:
        media=conn.execute(
            "SELECT current_relative_path,current_root_kind FROM files "
            "WHERE job_id=?",(job_id,)
        ).fetchall()
    assert len(media)==1
    assert media[0]["current_root_kind"]=="shared_workspace"
    assert (Path(storage_paths(workspace)["backup_root"])/
            str(media[0]["current_relative_path"])).read_bytes()==data
    assert not source.exists()
