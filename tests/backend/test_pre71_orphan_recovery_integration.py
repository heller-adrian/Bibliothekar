"""Full pre.7.1 legacy orphan replay on a registered, isolated two-library F14 root."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from app import domain_recovery, operation_health, root_operations as ro
from app.archive_release_stock import describe_archive_release_stock, verify_archive_release_copies
from app.database import database_connection
from app.event_change_apply import confirm_event_change
from app.library_registry import ensure_library_identity
from app.storage_config import load_storage_settings, storage_paths
from tests.backend.test_0271_archive_release_stock import _release_case,_copy_release_rows
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready


def test_pre71_startup_replays_exact_archived_copy_orphan_under_its_original_lease(
    ready,tmp_path,
):
    """The pre7 error must be recoverable without deleting F14 records by hand."""
    _case,workspace,registry,databases,_evidence=ready
    source_case=tmp_path/"pre7-case"
    source_case.mkdir()
    simulated=_release_case(source_case,with_asset=True)
    cr_id=simulated["cr_id"]
    confirm_event_change(
        simulated["db"],cr_id,simulated["archive"],simulated["workspace"]
    )
    rows=_copy_release_rows(simulated)
    assert verify_archive_release_copies(
        simulated["db"],simulated["archive"],simulated["workspace"],cr_id
    )["complete"]
    with database_connection(simulated["db"]) as connection:
        for table in ("event_change_file_reviews","event_change_asset_reviews"):
            connection.execute(
                f"""UPDATE {table}
                    SET verification_status='archive_source_still_exists',
                        verified_at=NULL
                    WHERE change_request_id=? AND verification_status='release_copy_verified'""",
                (cr_id,),
            )

    # Transfer only synthetic test bytes into the prepared, registered
    # F14 main-library roots; keep their exact identities and mount anchors.
    main_db=databases[0]
    with sqlite3.connect(simulated["db"]) as src,sqlite3.connect(main_db) as dest:
        src.backup(dest)
    ensure_library_identity(main_db,"main")
    archive=Path(_case/"archive-main")
    main_work=Path(storage_paths(workspace)["workspaces_root"])/"main"
    central=storage_paths(workspace)["backup_root"]
    shutil.copytree(simulated["archive"],archive,dirs_exist_ok=True)
    shutil.copytree(simulated["central"],central,dirs_exist_ok=True)

    # Emulate pre.7's interrupted protected function after an otherwise
    # byte-verified first copy and the accidental status downgrade.
    domain_recovery.handlers()
    with pytest.raises(RuntimeError,match="simulated crash"):
        with ro.reserve(
            workspace,library_id="main",database=main_db,kind="archive",
            ids={"cr_id":cr_id,"function":domain_recovery.ARCHIVE_COPY},
            paths=[
                workspace,main_work,archive,
                *(workspace/name for name in load_storage_settings(workspace_root=workspace).values()),
            ],
        ):
            raise RuntimeError("simulated crash")

    prior=operation_health.inspect(workspace)
    dead=[x for x in prior["reservations"] if not x["live"]]
    assert len(dead)==1
    assert dead[0]["ids"]=={"cr_id":cr_id,"function":domain_recovery.ARCHIVE_COPY}
    assert {"central_stock","library:main"}<=set(prior["blocked_scopes"])
    originals={row["old_path"]:(archive/row["old_path"]).read_bytes() for row in rows}
    copies={row["workspace_release_path"]:(central/row["workspace_release_path"]).read_bytes() for row in rows}
    assert domain_recovery.replay(workspace,registry,database=main_db)
    assert operation_health.inspect(workspace)["writes_allowed"]
    assert describe_archive_release_stock(main_db,cr_id)["stage"]=="remove_archive"
    assert {rel:(archive/rel).read_bytes() for rel in originals}==originals
    assert {rel:(central/rel).read_bytes() for rel in copies}==copies
    assert not domain_recovery.replay(workspace,registry,database=main_db)
