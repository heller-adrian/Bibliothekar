"""Routes for the adoption wizard within the active library context."""
from contextlib import ExitStack, contextmanager
from datetime import date
import json
import os
from pathlib import Path
from threading import Event, Lock
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.database import database_connection
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
from app.legacy_adoption_catalogue import prepare_documents
from app.legacy_adoption_dataset import DatasetError
from app.legacy_adoption_export import directory_scaffold, event_documents, manifest_file
from app.legacy_adoption_inventory import (
    _job, create_job, discard_job, inventory_chronology, inventory_errors, inventory_families,
    inventory_status, scan_inventory,
)
from app.legacy_adoption_paths import AdoptionError, bound_directory
from app.legacy_adoption_mode import reserve_adoption
from app.legacy_adoption_plan import create_plan, plan_moves, plan_status
from app.legacy_adoption_registration import finalize_adoption
from app.legacy_adoption_verify import plan_issues, reopen_plan, verify_media
from app.library_registry import LibraryRegistryError, list_libraries
from app.root_operations import RootOperationError, admission


class Source(BaseModel):
    root: Literal["nas", "saved"]
    relative: str = Field(default="", max_length=4096)


class EventDefinition(BaseModel):
    existing_id: str | None = None
    event_kind: Literal["event", "no_event"] = "event"
    name: str = Field(default="", max_length=180)
    start_date: str | None = None
    end_date: str | None = None
    preserve_day_folders: bool = False
    segments: list[dict[str, str]] = Field(default_factory=list, max_length=200)
    children: list[dict[str, str]] = Field(default_factory=list, max_length=200)
    folder_layout: dict[str, Any] | None = None


class Draft(BaseModel):
    events: list[EventDefinition] = Field(default_factory=list, max_length=200)
    capture_overrides: dict[str, str] = Field(default_factory=dict, max_length=10000)
    exclude_families: list[str] = Field(default_factory=list, max_length=10000)
    target_stems: dict[str, str] = Field(default_factory=dict, max_length=10000)


class Finalize(BaseModel):
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@contextmanager
def _errors():
    try:
        yield
    except FileNotFoundError as error:
        raise HTTPException(404, "Der gewählte Pfad ist nicht erreichbar.") from error
    except PermissionError as error:
        raise HTTPException(403, "Für den gewählten Ordner fehlt die Leseberechtigung.") from error
    except (AdoptionError, DatasetError, LibraryRegistryError, RootOperationError, OSError, ValueError, TypeError) as error:
        raise HTTPException(409, str(error)) from error


def _download(factory, filename, *, media_type="application/zip"):
    # Open before headers so missing or stale plans produce a normal API error.
    stack = ExitStack()
    with _errors():
        try:
            stream = stack.enter_context(factory())
        except BaseException:
            stack.close()
            raise

    def chunks():
        with stack:
            while data := stream.read(256 * 1024):
                yield data

    return StreamingResponse(chunks(), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


def install_legacy_adoption_routes(app, *, context, registry_path, source_root_path):
    from app.legacy_adoption_ui import wizard_html

    router = APIRouter(prefix="/api/legacy-adoption", tags=["Bestandsübernahme"])
    running = {}
    running_lock = Lock()

    def source_path(root, relative):
        path = source_root_path(root)
        if path is None or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise AdoptionError("Der gewählte Quellpfad ist ungültig.")
        return path / relative

    def key(library, job_id):
        return str(library.database_path), job_id

    def run_scan(library, job_id, pause):
        def check_pause():
            if pause.is_set():
                raise InterruptedError("Inventur pausiert. Bereits gelesene Dateien sind gespeichert.")

        try:
            scan_inventory(library, job_id, cancellation_callback=check_pause)
        except Exception as error:
            # Most failures are already persisted by scan_inventory. A job
            # rejected before claiming a generation remains visible as ready.
            import logging
            logging.getLogger(__name__).info("Legacy inventory %s: %s", job_id, error)
        finally:
            with running_lock:
                running.pop(key(library, job_id), None)

    @app.get("/legacy-adoption", response_class=HTMLResponse, include_in_schema=False)
    def wizard():
        return HTMLResponse(wizard_html(context().library_id), headers={"Cache-Control": "no-store"})

    @router.get("/source")
    def source_folders(root: Literal["nas", "saved"] = "nas", relative: str = ""):
        with _errors():
            path = source_path(root, relative)
            with bound_directory(path) as descriptor, os.scandir(descriptor) as entries:
                folders = sorted(
                    entry.name for entry in entries if not entry.name.startswith(".")
                    and entry.is_dir(follow_symlinks=False)
                )
        rel = Path(relative)
        return {"path": str(path), "relative": "" if str(rel) == "." else str(rel),
                "parent": None if not rel.parts else ("" if str(rel.parent) == "." else str(rel.parent)),
                "folders": folders}

    @router.get("/jobs")
    def jobs(request: Request):
        library = context()
        active = getattr(request.state, "legacy_adoption", None)
        job_id = active["job_id"] if active else None
        with database_connection(library.database_path) as connection:
            return [dict(row) for row in connection.execute(
                """SELECT job.id, job.state, job.source_root, job.created_at,
                          plan.state AS plan_state
                     FROM legacy_adoption_jobs job LEFT JOIN legacy_adoption_plans plan ON plan.job_id = job.id
                    WHERE job.library_id = ? AND job.state != 'discarded'
                      AND (job.id = ? OR (? IS NULL AND plan.state = 'completed'))
                    ORDER BY job.created_at DESC, job.id DESC""", (library.library_id, job_id, job_id),
            )]

    @router.post("/jobs", status_code=201)
    def new_job(source: Source):
        library = context()
        with _errors(), admission(library):
            roots = tuple(
                Path(row[field]) for row in list_libraries(registry_path(), active_only=False, registered_only=True)
                for field in ("archive_root", "workspace_root", "work_root", "database_path")
            )
            identifier = create_job(library, source_path(source.root, source.relative), other_managed_roots=roots)
            reserve_adoption(registry_path(), library.library_id, identifier)
        return {"id": identifier}

    @router.get("/jobs/{job_id}")
    def job(job_id: str):
        library = context()
        with _errors():
            result = inventory_status(library, job_id)
            with database_connection(library.database_path) as connection:
                result["draft"] = json.loads(_job(connection, library.library_id, job_id)["draft_json"])
            with running_lock:
                result["scan_running"] = key(library, job_id) in running
            result["plan"] = plan_status(library, job_id)
        return result

    @router.post("/jobs/{job_id}/scan", status_code=202)
    def scan(job_id: str, tasks: BackgroundTasks):
        library = context()
        with _errors(), admission(library):
            status = inventory_status(library, job_id)
            if status["state"] not in {"ready", "scanning", "inventoried"} or plan_status(library, job_id):
                raise AdoptionError("Der Auftrag ist nicht zur Inventur verfügbar.")
            with running_lock:
                if key(library, job_id) not in running:
                    pause = Event()
                    running[key(library, job_id)] = pause
                    tasks.add_task(run_scan, library, job_id, pause)
        return {"accepted": True}

    @router.post("/jobs/{job_id}/pause")
    def pause_scan(job_id: str):
        library = context()
        with _errors():
            inventory_status(library, job_id)
            with running_lock:
                pause = running.get(key(library, job_id))
                if pause is not None:
                    pause.set()
        return {"accepted": True}

    @router.get("/jobs/{job_id}/chronology")
    def chronology(job_id: str, year: str = ""):
        with _errors():
            return inventory_chronology(context(), job_id, year=year)

    @router.get("/jobs/{job_id}/families")
    def families(job_id: str, day: str | None = None, after: str = ""):
        with _errors():
            return inventory_families(context(), job_id, day=day, after=after, limit=60)

    @router.get("/jobs/{job_id}/errors")
    def errors(job_id: str, after: str = ""):
        with _errors():
            return inventory_errors(context(), job_id, after=after)

    @router.get("/events")
    def existing(day: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
        with _errors(), database_connection(context().database_path) as connection:
            date.fromisoformat(day)
            start, end = day + "T00:00:00", day + "T23:59:59"
            normal = continuous_event_overlaps(connection, "", start, end)
            free = no_event_segment_overlaps(connection, "", start, end)
            matches = {row["id"] for row in normal if row["status"] == "archived"}
            matches.update(row["event_id"] for row in free if row["status"] == "archived")
            return [dict(row) for row in connection.execute(
                """SELECT id, name, start_datetime, end_datetime FROM events WHERE parent_event_id IS NULL
                    AND status = 'archived' AND pending_delete = 0 AND coalesce(linkage_kind, '') = ''
                    ORDER BY start_datetime DESC, name""",
            ) if row["id"] in matches]

    @router.put("/jobs/{job_id}/draft")
    def save_draft(job_id: str, draft: Draft):
        library = context()
        with _errors(), admission(library), database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            item = _job(connection, library.library_id, job_id)
            if item["state"] != "inventoried" or connection.execute(
                "SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,),
            ).fetchone():
                raise AdoptionError("Der Entwurf ist in diesem Zustand nicht bearbeitbar.")
            connection.execute(
                "UPDATE legacy_adoption_jobs SET draft_json = ? WHERE id = ?",
                (draft.model_dump_json(exclude_none=True), job_id),
            )
        return {"saved": True}

    @router.post("/jobs/{job_id}/plan")
    def freeze(job_id: str, draft: Draft):
        library = context()
        with _errors(), admission(library):
            return create_plan(library, registry_path(), job_id, draft.model_dump(exclude_none=True))

    @router.get("/jobs/{job_id}/moves")
    def moves(job_id: str, after: str = ""):
        with _errors():
            return plan_moves(context(), job_id, after=after)

    @router.get("/jobs/{job_id}/issues")
    def issues(job_id: str):
        with _errors():
            return plan_issues(context(), job_id)

    @router.post("/jobs/{job_id}/documents")
    def documents(job_id: str):
        library = context()
        with _errors(), admission(library):
            return prepare_documents(library, job_id)

    @router.get("/jobs/{job_id}/download/{artifact}")
    def download(job_id: str, artifact: Literal["folders", "documents", "original-documents", "manifest"]):
        library = context()
        if artifact == "manifest":
            return _download(lambda: manifest_file(library, job_id), "bestandsuebernahme.jsonl",
                             media_type="application/x-ndjson")
        if artifact == "folders":
            return _download(lambda: directory_scaffold(library, job_id), "archiv-ordnergeruest.zip")
        return _download(lambda: event_documents(library, job_id, originals=artifact == "original-documents"),
                         "urspruengliche-ereignisdokumente.zip" if artifact == "original-documents"
                         else "ereignisdokumente.zip")

    @router.post("/jobs/{job_id}/verify")
    def verify(job_id: str):
        library = context()
        with _errors(), admission(library):
            return verify_media(library, job_id)

    @router.post("/jobs/{job_id}/finalize")
    def finalize(job_id: str, command: Finalize):
        library = context()
        with _errors():
            planned = plan_status(library, job_id)
            if planned.get("id") != command.plan_id:
                raise AdoptionError("Der angezeigte Verschiebeplan ist veraltet.")
            return finalize_adoption(library, registry_path(), job_id, command.plan_id)

    @router.post("/jobs/{job_id}/reopen")
    def reopen(job_id: str):
        library = context()
        with _errors(), admission(library):
            reopen_plan(library, job_id)
        return {"reopened": True}

    @router.delete("/jobs/{job_id}")
    def discard(job_id: str):
        library = context()
        with _errors(), admission(library):
            discard_job(library, job_id)
        return {"discarded": True}

    app.include_router(router)
