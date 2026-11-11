"""Routes for the adoption wizard within the active library context."""
from contextlib import ExitStack, contextmanager
from datetime import date
import json
import os
from pathlib import Path
from threading import Event, Lock
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.database import database_connection
from app.event_layout import get_global_default
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
from app.legacy_adoption_catalogue import prepare_documents
from app.legacy_adoption_dataset import DatasetError
from app.legacy_adoption_execution import change_phase, complete_rollback, confirm_plan, verify_execution
from app.legacy_adoption_export import directory_scaffold, event_documents, manifest_file
from app.legacy_adoption_host import ExecutionError
from app.legacy_adoption_inventory import (
    _job, create_job, discard_job, inventory_chronology, inventory_errors, inventory_families,
    inventory_status, qualify_source, scan_inventory,
)
from app.legacy_adoption_package import (
    inspect_runner, locked_script, permit, prepare_probe, probe_details, read_manifest, script_details, script_status,
)
from app.legacy_adoption_paths import AdoptionError, bound_directory
from app.legacy_adoption_mode import (
    adoption_execution_access, choose_initial_setup, later_adoption_blockers, require_initial_adoption,
    require_later_adoption, reserve_adoption,
)
from app.legacy_adoption_plan import MAX_PLAN_ITEMS, create_plan, plan_directories, plan_moves, plan_status
from app.legacy_adoption_registration import finalize_adoption
from app.legacy_adoption_review import copy_review, review_cases, review_count
from app.legacy_adoption_verify import plan_issues, reopen_plan
from app.library_registry import LibraryRegistryError, list_libraries
from app.root_operations import RootOperationError, admission


class SetupDecision(BaseModel):
    decision: Literal["adopting", "skipped"]


class Source(BaseModel):
    root: Literal["nas", "saved"]
    relative: str = Field(default="", max_length=4096)


class FolderLayout(BaseModel):
    mode: Literal["default", "custom"] = "custom"
    structure_enabled: StrictBool | None = None
    input_path: str | None = None
    layout: dict[str, Any] | None = None


class ChildDefinition(BaseModel):
    name: str = Field(max_length=180)
    start_datetime: str
    end_datetime: str
    folder_layout: FolderLayout | None = None


class EventDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_id: str | None = Field(default=None, min_length=1, max_length=180)
    event_kind: Literal["event", "no_event"] = "event"
    name: str = Field(default="", max_length=180)
    start_date: str | None = None
    end_date: str | None = None
    preserve_day_folders: bool = False
    segments: list[dict[str, str]] = Field(default_factory=list, max_length=200)
    children: list[ChildDefinition] = Field(default_factory=list, max_length=200)
    folder_layout: FolderLayout | None = None


class Draft(BaseModel):
    events: list[EventDefinition] = Field(default_factory=list, max_length=MAX_PLAN_ITEMS)
    capture_overrides: dict[str, str] = Field(default_factory=dict, max_length=10000)
    exclude_families: list[str] = Field(default_factory=list, max_length=10000)
    target_stems: dict[str, str] = Field(default_factory=dict, max_length=10000)


class SaveDraft(Draft):
    revision: int = Field(ge=0)


class Freeze(BaseModel):
    revision: int = Field(ge=0)


class PlanCommand(BaseModel):
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Confirm(PlanCommand):
    method: Literal["manual", "script"]
    acknowledged: StrictBool
    probe_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ReviewCopy(BaseModel):
    family_key: str = Field(min_length=1, max_length=4096)


class ScriptHost(PlanCommand):
    appdata: str | None = Field(default=None, min_length=1, max_length=4096)
    source: str | None = Field(default=None, min_length=1, max_length=4096)
    archive: str | None = Field(default=None, min_length=1, max_length=4096)


@contextmanager
def _errors():
    try:
        yield
    except FileNotFoundError as error:
        raise HTTPException(404, "Der gewählte Pfad ist nicht erreichbar.") from error
    except PermissionError as error:
        raise HTTPException(403, "Für den gewählten Ordner fehlt die Leseberechtigung.") from error
    except (AdoptionError, DatasetError, ExecutionError, LibraryRegistryError,
            RootOperationError, OSError, ValueError, TypeError, KeyError) as error:
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
    from app.legacy_adoption_ui import setup_choice_html, wizard_html

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

    @app.get("/setup/adoption", response_class=HTMLResponse, include_in_schema=False)
    def setup_choice(request: Request):
        return HTMLResponse(
            setup_choice_html(request.state.initial_setup["decision"]),
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/setup/adoption")
    def decide_setup(payload: SetupDecision):
        library = context()
        with _errors(), admission(library):
            choose_initial_setup(registry_path(), library, payload.decision)
        return {"next": "/legacy-adoption" if payload.decision == "adopting" else "/"}

    def is_later(request):
        return getattr(request.state, "legacy_adoption_later", False)

    def require_adoption(request, library):
        if is_later(request):
            require_later_adoption(library)
        else:
            require_initial_adoption(registry_path(), library)

    @router.get("/eligibility")
    def eligibility():
        with _errors():
            blockers = later_adoption_blockers(context())
        return {"eligible": not blockers, "blockers": blockers}

    @app.get("/legacy-adoption", response_class=HTMLResponse, include_in_schema=False)
    def wizard(request: Request):
        library = context()
        later = is_later(request)
        if later and request.state.legacy_adoption is None:
            with _errors():
                require_later_adoption(library)
        return HTMLResponse(
            wizard_html(library.library_id, later=later,
                        recovery_only=getattr(request.state, "legacy_adoption_recovery", False)),
            headers={"Cache-Control": "no-store"},
        )

    def managed_roots():
        return tuple(
            Path(row[field]) for row in list_libraries(registry_path(), active_only=False, registered_only=True)
            for field in ("archive_root", "workspace_root", "work_root", "database_path")
        )

    def source_evidence(library, path, roots):
        try:
            *_, evidence, read_only = qualify_source(library, path, other_managed_roots=roots)
        except (AdoptionError, DatasetError) as error:
            return {"dataset": None, "read_only": False, "reason": str(error)}
        except OSError:
            return {"dataset": None, "read_only": False, "reason": "Die Quelle ist nicht lesend erreichbar."}
        return {"dataset": evidence["dataset"], "read_only": read_only, "reason": None}

    @router.get("/sources")
    def sources(request: Request):
        library = context()
        with _errors():
            require_adoption(request, library)
            roots = managed_roots()
            choices = []
            for key in ("nas", "saved"):
                path = source_root_path(key)
                if path is None:
                    continue
                try:
                    with bound_directory(path):
                        proof = source_evidence(library, path, roots)
                except (AdoptionError, OSError):
                    continue
                # A NAS mount can contain a compatible subfolder. A generic
                # backup root is only useful if the root itself is eligible.
                if key == "nas" or (proof["dataset"] and proof["read_only"]):
                    choices.append({"key": key, **proof})
            preferred = next((item["key"] for item in choices if item["dataset"] and item["read_only"]), None)
        return {"roots": choices, "preferred": preferred or (choices[0]["key"] if choices else None)}

    @router.get("/source")
    def source_folders(request: Request, root: Literal["nas", "saved"] = "nas", relative: str = ""):
        library = context()
        with _errors():
            require_adoption(request, library)
            path = source_path(root, relative)
            with bound_directory(path) as descriptor, os.scandir(descriptor) as entries:
                folders = sorted(
                    entry.name for entry in entries if not entry.name.startswith(".")
                    and entry.is_dir(follow_symlinks=False)
                )
            proof = source_evidence(library, path, managed_roots())
        rel = Path(relative)
        return {"path": str(path), "relative": "" if str(rel) == "." else str(rel),
                "parent": None if not rel.parts else ("" if str(rel.parent) == "." else str(rel.parent)),
                "folders": folders, **proof}

    @router.post("/jobs", status_code=201)
    def new_job(source: Source, request: Request):
        library = context()
        with _errors(), admission(library):
            require_adoption(request, library)
            identifier = create_job(library, source_path(source.root, source.relative),
                                    other_managed_roots=managed_roots())
            reserve_adoption(registry_path(), library.library_id, identifier,
                             access_kind="library" if is_later(request) else "initial")
        return {"id": identifier}

    @router.get("/jobs/{job_id}")
    def job(job_id: str):
        library = context()
        with _errors():
            result = inventory_status(library, job_id)
            result["plan"] = plan_status(library, job_id)
            with database_connection(library.database_path) as connection:
                item = _job(connection, library.library_id, job_id)
                result["draft"] = json.loads(item["draft_json"])
                result["draft_revision"] = item["draft_revision"]
                result["layout_default"] = get_global_default(connection)
                result["review_count"] = review_count(connection, job_id, result["plan"].get("id"))
            with running_lock:
                result["scan_running"] = key(library, job_id) in running
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

    @router.get("/jobs/{job_id}/review")
    def review(job_id: str, after: str = ""):
        with _errors():
            return review_cases(context(), job_id, after=after)

    @router.post("/jobs/{job_id}/review/copy")
    def copy_case(job_id: str, payload: ReviewCopy):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            return copy_review(library, job_id, payload.family_key)

    @router.get("/jobs/{job_id}/events")
    def archived_events(job_id: str, day: date, request: Request):
        if not is_later(request):
            raise HTTPException(409, "Vorhandene Archivereignisse können bei der Ersteinrichtung nicht ergänzt werden.")
        library = context()
        start, end = day.isoformat() + "T00:00:00", day.isoformat() + "T23:59:59"
        with _errors(), database_connection(library.database_path) as connection:
            _job(connection, library.library_id, job_id)
            matches = {row["id"] for row in continuous_event_overlaps(connection, job_id, start, end)}
            matches.update(row["event_id"] for row in no_event_segment_overlaps(connection, job_id, start, end))
            return [dict(row) for row in connection.execute(
                """SELECT id, name, start_datetime, end_datetime FROM events WHERE parent_event_id IS NULL
                    AND status = 'archived' AND pending_delete = 0 AND coalesce(linkage_kind, '') = ''
                    ORDER BY start_datetime DESC, name"""
            ) if row["id"] in matches]

    @router.post("/jobs/{job_id}/draft/check")
    def check_draft(job_id: str, draft: Draft, request: Request):
        from app.legacy_adoption_plan import preview_draft
        library = context()
        with _errors():
            require_adoption(request, library)
            return preview_draft(library, job_id, draft.model_dump(exclude_none=True), allow_existing=is_later(request))

    @router.put("/jobs/{job_id}/draft")
    def save_draft(job_id: str, draft: SaveDraft, request: Request):
        library = context()
        with _errors(), admission(library), database_connection(library.database_path) as connection:
            require_adoption(request, library)
            if not is_later(request) and any(event.existing_id for event in draft.events):
                raise AdoptionError("Vorhandene Archivereignisse können bei der Ersteinrichtung nicht ergänzt werden.")
            connection.execute("BEGIN IMMEDIATE")
            item = _job(connection, library.library_id, job_id)
            if item["state"] != "inventoried" or connection.execute(
                "SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,),
            ).fetchone():
                raise AdoptionError("Der Entwurf ist in diesem Zustand nicht bearbeitbar.")
            if item["draft_revision"] != draft.revision:
                raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
            revision = draft.revision + 1
            connection.execute(
                "UPDATE legacy_adoption_jobs SET draft_json = ?, draft_revision = ? WHERE id = ?",
                (draft.model_dump_json(exclude_none=True, exclude={"revision"}), revision, job_id),
            )
        return {"saved": True, "revision": revision}

    @router.post("/jobs/{job_id}/plan")
    def freeze(job_id: str, draft: Freeze, request: Request):
        library = context()
        with _errors(), admission(library):
            require_adoption(request, library)
            return create_plan(library, registry_path(), job_id, draft_revision=draft.revision,
                               allow_existing=is_later(request))

    @router.get("/jobs/{job_id}/directories")
    def directories(job_id: str, after: str = ""):
        with _errors():
            return plan_directories(context(), job_id, after=after)

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
        with _errors():
            execution = plan_status(library, job_id).get("execution")
            allowed = {"manual"} if artifact != "original-documents" else {"manual", "repair", "rolling_back"}
            if not execution or execution["method"] != "manual" or execution["phase"] not in allowed:
                raise AdoptionError("Diese Unterlagen sind für den aktuellen Ausführungsschritt gesperrt.")
        if artifact == "folders":
            return _download(lambda: directory_scaffold(library, job_id), "archiv-ordnergeruest.zip")
        return _download(lambda: event_documents(library, job_id, originals=artifact == "original-documents"),
                         "urspruengliche-ereignisdokumente.zip" if artifact == "original-documents"
                         else "ereignisdokumente.zip")

    @router.get("/jobs/{job_id}/script/source/{name}", response_class=PlainTextResponse)
    def script_source(job_id: str, name: str):
        with _errors():
            inventory_status(context(), job_id)
            return PlainTextResponse(inspect_runner(name), headers={"Cache-Control": "no-store"})

    @router.get("/jobs/{job_id}/script/probe")
    def get_probe(job_id: str):
        library = context()
        with _errors():
            plan = plan_status(library, job_id)
            return probe_details(library, job_id, plan["id"]) if plan and not plan["execution"] else {}

    @router.post("/jobs/{job_id}/script/probe")
    def script_probe(job_id: str, command: ScriptHost):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            return prepare_probe(library, job_id, command.plan_id, command.appdata, command.source, command.archive)

    @router.get("/jobs/{job_id}/script/manifest")
    def script_manifest(job_id: str):
        library = context()
        with _errors():
            plan = plan_status(library, job_id)
            if not plan.get("execution") or plan["execution"]["method"] != "script":
                raise AdoptionError("Für diesen Auftrag ist kein Skript freigegeben.")
            return Response(read_manifest(library, job_id, plan["id"]), media_type="application/json",
                            headers={"Cache-Control": "no-store"})

    @router.get("/jobs/{job_id}/script")
    def script(job_id: str, request: Request):
        library = context()
        with _errors():
            plan = plan_status(library, job_id)
            if not plan.get("execution") or plan["execution"]["method"] != "script":
                raise AdoptionError("Für diesen Auftrag ist kein Skript freigegeben.")
            result = script_details(library, job_id, plan["id"])
            if getattr(request.state, "legacy_adoption_recovery", False) and plan["execution"]["phase"] != "rolling_back":
                result.pop("command", None)
            return result

    @router.post("/jobs/{job_id}/script/release")
    def script_release(job_id: str, command: PlanCommand):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library),                 locked_script(library, job_id, command.plan_id) as (descriptor, script):
            if script["phase"] not in {"script_prepared", "repair"}:
                raise AdoptionError("Die Skriptausführung ist in dieser Phase gesperrt.")
            change_phase(library, job_id, command.plan_id, "script_prepared",
                         from_phases={"script_prepared", "repair"})
            return {"command": permit(descriptor, script, "apply")}

    @router.post("/jobs/{job_id}/confirm")
    def confirm(job_id: str, command: Confirm, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_adoption(request, library)
            return confirm_plan(library, job_id, command.plan_id, command.method,
                                acknowledged=command.acknowledged, probe_digest=command.probe_sha256)

    @router.post("/jobs/{job_id}/verify")
    def verify(job_id: str, command: PlanCommand):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            planned = plan_status(library, job_id)
            execution = planned.get("execution")
            if execution and execution["method"] == "script":
                with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                    status = script_status(descriptor, script)
                    if not status or (status["state"], status["mode"]) != ("completed", "apply"):
                        raise AdoptionError("Das externe Skript hat die Ausführung noch nicht abgeschlossen.")
                    permit(descriptor, script, None)
                    change_phase(library, job_id, command.plan_id, "operations_done", from_phases={
                        "script_prepared", "operations_done", "verifying", "repair", "registration_pending",
                    })
                    return verify_execution(library, job_id, command.plan_id)
            return verify_execution(library, job_id, command.plan_id)

    @router.post("/jobs/{job_id}/resume")
    def resume(job_id: str, command: PlanCommand):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            execution = plan_status(library, job_id).get("execution")
            if not execution or execution["method"] != "manual":
                raise AdoptionError("Die bestätigte Methode kann nicht geändert werden.")
            change_phase(library, job_id, command.plan_id, "manual", from_phases={"repair"})
            return plan_status(library, job_id)

    @router.post("/jobs/{job_id}/rollback/start")
    def rollback_start(job_id: str, command: PlanCommand):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            phases = {"manual", "verifying", "repair", "registration_pending", "rolling_back"}
            execution = plan_status(library, job_id).get("execution")
            if execution and execution["method"] == "script":
                phases.update(("script_prepared", "operations_done"))
                with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                    if script["phase"] not in phases:
                        raise AdoptionError("Eine Skriptrücknahme ist in dieser Phase gesperrt.")
                    permit(descriptor, script, None)
                    change_phase(library, job_id, command.plan_id, "rolling_back", from_phases=phases)
                    permit(descriptor, script, "rollback")
            else:
                change_phase(library, job_id, command.plan_id, "rolling_back", from_phases=phases)
            return plan_status(library, job_id)

    @router.post("/jobs/{job_id}/rollback/check")
    def rollback_check(job_id: str, command: PlanCommand):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            execution = plan_status(library, job_id).get("execution")
            if execution and execution["method"] == "script":
                with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                    if script["phase"] != "rolling_back":
                        raise AdoptionError("Starte zuerst den vorgesehenen Wiederherstellungsweg.")
                    return complete_rollback(
                        library, job_id, command.plan_id, before_commit=lambda: permit(descriptor, script, None),
                    )
            return complete_rollback(library, job_id, command.plan_id)

    @router.post("/jobs/{job_id}/finalize")
    def finalize(job_id: str, command: PlanCommand, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()):
            planned = plan_status(library, job_id)
            if planned.get("id") != command.plan_id:
                raise AdoptionError("Der angezeigte Verschiebeplan ist veraltet.")
            if planned["state"] != "completed" and (
                planned["execution"] is None or planned["execution"]["phase"] != "registering"
            ):
                with admission(library):
                    require_adoption(request, library)
                    change_phase(library, job_id, command.plan_id, "registering",
                                 from_phases={"registration_pending"})
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
