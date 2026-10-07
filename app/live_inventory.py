from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import database_connection
from app.event_inventory import EventInventoryError, scan_event_inventory
from app.sort_plan import _reapply_physical_event_prefix
from app.workspace_layout import WorkspaceLayoutError, shared_work_root


def refresh_live_event_inventories(
    database_path: Path,
    workspace_path: Path,
    archive_root: Path,
    *,
    job_id: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Refresh observational IST snapshots for applied/archived parent events."""
    where = [
        "parent_event_id IS NULL",
        "status IN ('applied','archived')",
        "COALESCE(TRIM(linkage_kind),'')=''",
    ]
    params: list[Any] = []
    if job_id is not None:
        where.append("job_id=?")
        params.append(str(job_id))
    if event_id is not None:
        where.append("id=?")
        params.append(str(event_id))

    with database_connection(database_path) as connection:
        rows = connection.execute(
            f"""SELECT id,job_id,status FROM events
                WHERE {' AND '.join(where)}
                ORDER BY job_id,start_datetime,id""",
            params,
        ).fetchall()

    refreshed: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for row in rows:
        current_event_id = str(row["id"])
        current_job_id = str(row["job_id"])
        try:
            if str(row["status"]) == "applied":
                root = shared_work_root(workspace_path)
                root_kind = "shared_workspace"
                prefix = _reapply_physical_event_prefix(
                    database_path, current_job_id, current_event_id
                )
            else:
                root = archive_root
                root_kind = "camera_archive"
                prefix = None

            inventory = scan_event_inventory(
                database_path,
                root,
                current_job_id,
                current_event_id,
                root_kind=root_kind,
                persist=True,
                update_known_file_locations=False,
                event_prefix_override=prefix,
                fast_refresh=True,
            )
            refreshed[current_event_id] = dict(inventory.get("summary") or {})
        except (EventInventoryError, WorkspaceLayoutError, OSError) as error:
            # Ein angewendetes Ereignis kann vom Benutzer bereits vollständig
            # ins Archiv verschoben worden sein. In diesem Sonderfall wird das
            # Archiv read-only gescannt, damit reconcile_missing_files den
            # vorhandenen Mechanismus „Mögliche Archivübernahme erkannt“
            # tatsächlich aus einem realen Dateisystemzustand ableiten kann.
            if (
                str(row["status"]) == "applied"
                and isinstance(error, EventInventoryError)
                and "Ereignisordner wurde nicht gefunden" in str(error)
            ):
                try:
                    archive_inventory = scan_event_inventory(
                        database_path,
                        archive_root,
                        current_job_id,
                        current_event_id,
                        root_kind="camera_archive",
                        persist=True,
                        update_known_file_locations=False,
                        fast_refresh=False,
                    )
                    archive_known = {
                        int(item["known_file_id"])
                        for item in archive_inventory.get("files") or []
                        if item.get("known_file_id") is not None
                    }
                    if archive_known:
                        from app.event_access import event_file_rows
                        from app.physical_state import reconcile_missing_files
                        with database_connection(database_path) as connection:
                            event = connection.execute(
                                "SELECT * FROM events WHERE id=?",
                                (current_event_id,),
                            ).fetchone()
                            expected_ids = [
                                int(item["file_id"])
                                for item in event_file_rows(
                                    connection,
                                    current_event_id,
                                )
                            ]
                            if event is not None and expected_ids:
                                reconcile_missing_files(
                                    connection,
                                    dict(event),
                                    "shared_workspace",
                                    expected_ids,
                                )
                        refreshed[current_event_id] = {
                            **dict(archive_inventory.get("summary") or {}),
                            "archive_transfer_candidate": True,
                        }
                        continue
                except (EventInventoryError, OSError):
                    pass
            errors.append({
                "event_id": current_event_id,
                "job_id": current_job_id,
                "message": str(error),
            })

    return {"refreshed_count": len(refreshed), "events": refreshed, "errors": errors}
