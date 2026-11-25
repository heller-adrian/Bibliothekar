"""Routes for the adoption wizard within the active library context."""
from contextlib import ExitStack, contextmanager
from datetime import date
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import Event, Lock
from uuid import uuid4
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.database import database_connection
from app.event_layout import get_global_default
from app.event_naming import naming_from_library_settings
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
from app.legacy_adoption_catalogue import prepare_documents
from app.legacy_adoption_dataset import DatasetError, browsable_folders
from app.legacy_adoption_execution import change_phase, complete_rollback, confirm_plan, verify_execution
from app.legacy_adoption_export import directory_scaffold, event_documents, manifest_file
from app.legacy_adoption_flat_copy import require_no_partial_publication
from app.legacy_adoption_host import ExecutionError
from app.legacy_adoption_history import completed_adoptions, history_html
from app.legacy_adoption_manual import manual_work
from app.legacy_adoption_inventory import (
    _job, create_job, discard_job, inventory_chronology, inventory_errors, inventory_exclusions, inventory_families,
    inventory_status, qualify_source, scan_inventory,
)
from app.legacy_adoption_package import (
    assert_unstarted_release_current, inspect_runner, locked_script, permit, prepare_probe, probe_details,
    read_manifest, retire_unstarted_package, rollback_directory_scope, script_details, script_documents_stale, script_journal_started, script_status,
)
from app.legacy_adoption_preparation import (
    abandon_failed_preparation, exclusive_preparation_worker, preparation_status,
    preparation_worker_active, record_preparation, reserve_preparation, saved_preparation_proof,
)
from app.legacy_adoption_partners import inventory_members, resolve as resolve_partners
from app.legacy_adoption_paths import AdoptionError, bound_directory
from app.legacy_adoption_mode import (
    active_adoption, adoption_execution_access, choose_initial_setup, complete_initial_preferences,
    later_adoption_blockers, require_initial_adoption,
    require_later_adoption, reserve_adoption,
)
from app.media_family_identity import IDENTITY_VERSION
from app.legacy_adoption_worker import dispatch
from app.library_context import resolve_library_context
from app.legacy_adoption_plan import (
    MAX_PLAN_ITEMS, ManualXmpRenameConflict, PlanFileIssues, create_plan, file_issue_summary,
    plan_directories, plan_moves, plan_status,
)
from app.legacy_adoption_registration import assert_completed_adoption, finalize_adoption
from app.legacy_adoption_review import (
    begin_review_batch, check_review_staging, copy_review, fail_pending_review_batch, finish_review_cancellation,
    review_batch_status, review_cases, review_count, review_selection, run_review_batch, ReviewStagingError, STAGING_ERROR,
)
from app.legacy_adoption_review_cancel import request as request_review_cancel
from app.legacy_adoption_review_metadata import apply_metadata, metadata_sources, stage_metadata
from app.legacy_adoption_review_progress import batch_details
from app.legacy_adoption_verify import editable_plan, STALE_XMP_DOCUMENTS, plan_issues, reopen_plan
from app.library_registry import LibraryRegistryError, list_libraries
from app.operation_health import read_session
from app.root_operations import _lock, RootOperationBusy, RootOperationError, admission


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
    create_subfolder: StrictBool = True


class EventDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_id: str | None = Field(default=None, min_length=1, max_length=180)
    event_kind: Literal["event", "no_event"] = "event"
    name: str = Field(default="", max_length=180)
    start_date: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    preserve_day_folders: bool = False
    subevent_prefix_enabled: StrictBool | None = None
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


class FreezePlan(Freeze):
    filename_method: Literal["manual", "script"] = "manual"
    background: StrictBool = False


class PlanningExclusions(Freeze):
    acknowledged: StrictBool
    restore: StrictBool = False


class PartnerChoice(BaseModel):
    xmp: str
    raw: str


class PlanningPartners(PlanningExclusions):
    choices: list[PartnerChoice] = Field(default_factory=list, max_length=10000)


class SelectExecution(BaseModel):
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    method: Literal["manual", "script"]


class SelectedMetadata(Freeze):
    family_keys: list[str] = Field(min_length=1, max_length=10000)


class StageMetadata(SelectedMetadata):
    source: str | None = Field(max_length=240)
    individual: StrictBool = False


class PlanCommand(BaseModel):
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class RollbackCheck(PlanCommand):
    keep_draft: StrictBool = False
    background: StrictBool = False


class ReopenPlan(BaseModel):
    plan_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    background: StrictBool = False


class FinishPlan(PlanCommand):
    background: StrictBool = False


class Confirm(PlanCommand):
    method: Literal["manual", "script"]
    acknowledged: StrictBool
    probe_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ReviewCopy(BaseModel):
    family_key: str = Field(min_length=1, max_length=4096)


class ReviewBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # null selects all eligible families on the server, including later pages.
    family_keys: list[str] | None = Field(min_length=1)


class CancelReviewBatch(BaseModel):
    batch_id: str = Field(pattern=r"^[a-f0-9]{32}$")


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
    except ManualXmpRenameConflict as error:
        raise HTTPException(409, {"code": "manual_xmp_rename_conflict", "message": str(error)}) from error
    except PlanFileIssues as error:
        raise HTTPException(409, {"code": "plan_file_issues", "message": str(error),
                                  **file_issue_summary(error.items)}) from error
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
    from app.initial_library_preferences_ui import preferences_html

    def require_reopen_idle(request: Request):
        job_id = request.path_params.get("job_id")
        if (not job_id or request.method in {"GET", "HEAD", "OPTIONS"}
                or request.url.path.endswith(("/reopen", "/rollback/check", "/draft/check", "/draft/structure"))):
            return
        library = context()
        with _errors(), database_connection(library.database_path) as connection:
            job = _job(connection, library.library_id, job_id)
            state = json.loads(job["draft_json"]).get("reopen_attempt", {}).get("state")
            if state in {"queued", "running"}:
                raise AdoptionError("Der Verschiebeplan wird bereits zurückgenommen.")

    router = APIRouter(prefix="/api/legacy-adoption", tags=["Bestandsübernahme"],
                       dependencies=[Depends(require_reopen_idle)])
    running = {}
    review_running = set()
    metadata_running = set()
    preparing = set()
    planning = set()
    releasing = set()
    reopening = set()
    registering = set()
    running_lock = Lock()

    def source_path(root, relative):
        path = source_root_path(root)
        if path is None or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise AdoptionError("Der gewählte Quellpfad ist ungültig.")
        return path / relative

    def key(library, job_id):
        return str(library.database_path), job_id

    def matching_update_required(connection, job_id):
        return connection.execute(
            """SELECT 1 FROM legacy_adoption_inventory
                WHERE job_id=? AND disposition='candidate'
                  AND json_extract(metadata_json, '$.media_type')='xmp'
                  AND coalesce(json_extract(metadata_json, '$.capture_identity_version'), 0) < ?
                LIMIT 1""", (job_id, IDENTITY_VERSION),
        ).fetchone() is not None

    def planning_attempt(library, job_id, command, *, state, message=None, issues=None, partners=None):
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = _job(connection, library.library_id, job_id)
            if row["draft_revision"] != command.revision:
                raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
            draft = json.loads(row["draft_json"])
            previous = draft.get("planning_attempt", {})
            if state == "queued":
                if connection.execute(
                    "SELECT 1 FROM legacy_adoption_plans WHERE job_id=?", (job_id,),
                ).fetchone():
                    raise AdoptionError("Ein Verschiebeplan ist bereits gespeichert.")
                if previous.get("state") in {"queued", "running"} and (
                    previous["method"], previous["revision"]
                ) != (command.filename_method, command.revision):
                    raise AdoptionError("Eine andere Planprüfung läuft bereits.")
            draft["planning_attempt"] = {
                "state": state, "method": command.filename_method, "revision": command.revision,
            }
            if message:
                draft["planning_attempt"]["message"] = message
            if issues:
                draft["planning_attempt"]["issues"] = issues
            if partners:
                draft["planning_attempt"]["partners"] = partners
            connection.execute("UPDATE legacy_adoption_jobs SET draft_json=? WHERE id=?",
                               (json.dumps(draft), job_id))

    def run_planning(library, job_id, command, later):
        registry = registry_path()
        lock = registry.with_name(registry.name + ".adoption-planning.lock")
        try:
            with _lock(lock, exclusive=True):
                try:
                    if saved := plan_status(library, job_id):
                        return saved
                    with admission(library):
                        reservation = active_adoption(registry)
                        if not reservation or (reservation["library_id"], reservation["job_id"]) != (library.library_id, job_id):
                            raise AdoptionError("Der Übernahmeauftrag ist nicht mehr aktiv.")
                        if later:
                            require_later_adoption(library)
                        else:
                            require_initial_adoption(registry, library)
                        with database_connection(library.database_path) as connection:
                            require_no_partial_publication(connection, job_id)
                            if matching_update_required(connection, job_id):
                                raise AdoptionError("Aktualisiere die Inventur für die neue RAW- und XMP-Zuordnung.")
                        planning_attempt(library, job_id, command, state="running")
                        result = create_plan(library, registry, job_id, draft_revision=command.revision,
                                             allow_existing=later, filename_method=command.filename_method)
                        planning_attempt(library, job_id, command, state="completed")
                        return result
                except Exception as error:
                    planning_attempt(library, job_id, command, state="failed", message=str(error),
                                     issues=error.items if isinstance(error, PlanFileIssues) else None,
                                     partners=error.partners if isinstance(error, PlanFileIssues) else None)
                    if not command.background:
                        raise
                    logging.getLogger(__name__).info("Legacy adoption planning %s: %s", job_id, error)
        except RootOperationBusy:
            if not command.background:
                raise
        finally:
            with running_lock:
                planning.discard(key(library, job_id))

    def require_planning_idle(library, job_id):
        with running_lock:
            if key(library, job_id) in planning:
                raise AdoptionError("Die Planprüfung läuft bereits.")
        with database_connection(library.database_path) as connection:
            row = _job(connection, library.library_id, job_id)
            attempt = json.loads(row["draft_json"]).get("planning_attempt", {})
            if attempt.get("state") in {"queued", "running"} and not connection.execute(
                "SELECT 1 FROM legacy_adoption_plans WHERE job_id=?", (job_id,),
            ).fetchone():
                raise AdoptionError("Die Planprüfung läuft bereits.")

    def run_scan(library, job_id, pause):
        def check_pause():
            if pause.is_set():
                raise InterruptedError("Inventur pausiert. Bereits gelesene Dateien sind gespeichert.")

        try:
            registry = registry_path()
            with _lock(registry.with_name(registry.name + ".adoption-scan.lock"), exclusive=True):
                scan_inventory(library, job_id, registry_path=registry, cancellation_callback=check_pause)
        except RootOperationBusy:
            pass
        except Exception as error:
            # Most failures are already persisted by scan_inventory. A job
            # rejected before claiming a generation remains visible as ready.
            logging.getLogger(__name__).info("Legacy inventory %s: %s", job_id, error)
        finally:
            with running_lock:
                running.pop(key(library, job_id), None)

    def copy_status(library, job_id, *, details=False):
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN")
            _job(connection, library.library_id, job_id)
            result = review_batch_status(connection, job_id)
            if details:
                result.update(batch_details(connection, library.database_path, job_id))
        with running_lock:
            result["running"] = key(library, job_id) in review_running
        return result

    def require_review_idle(library, job_id):
        status = copy_status(library, job_id)
        if status["running"] or status["pending"] or status.get("state") in {"active", "cancelling"}:
            raise AdoptionError("Schließe den Kopierauftrag zuerst ab.")

    def require_preparation_idle(library, job_id):
        plan = plan_status(library, job_id)
        if not plan.get("id") or plan.get("execution"):
            return
        progress = preparation_status(library, job_id, plan["id"])
        if progress is not None:
            raise AdoptionError(
                "Die Skriptvorbereitung ist gespeichert. Setze sie zuerst fort "
                "oder nutze den kontrollierten Rücksetzweg für einen anderen Plan."
            )

    def run_copies(library, job_id, registry):
        def copy_family(family_key):
            with admission(library):
                return copy_review(library, job_id, family_key)

        try:
            with adoption_execution_access(registry, wait_seconds=2):
                with admission(library):
                    try:
                        if copy_status(library, job_id).get("state") != "cancelling":
                            check_review_staging(library)
                    except ReviewStagingError as error:
                        logging.getLogger(__name__).warning(
                            "Legacy review staging %s: %s (%s)", job_id, error.operation, error.code,
                        )
                        fail_pending_review_batch(library, job_id, str(error))
                    except (AdoptionError, OSError, RootOperationError) as error:
                        logging.getLogger(__name__).warning("Legacy review staging %s: %r", job_id, error.__cause__ or error)
                        fail_pending_review_batch(library, job_id, STAGING_ERROR)
                run_review_batch(library, job_id, copy_family=copy_family)
                with admission(library):
                    finish_review_cancellation(library, job_id)
        except Exception:
            logging.getLogger(__name__).exception("Legacy review batch interrupted for job %s", job_id)
        finally:
            with running_lock:
                review_running.discard(key(library, job_id))

    def require_inventory_idle(library, job_id):
        with running_lock:
            if key(library, job_id) in running:
                raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")

    def schedule_copies(library, job_id, tasks, registry):
        with running_lock:
            run_key = key(library, job_id)
            if run_key in review_running:
                return
            review_running.add(run_key)
        dispatch("review", run_copies, library, job_id, registry, tasks=tasks)

    @app.get("/setup/preferences", response_class=HTMLResponse, include_in_schema=False)
    def setup_preferences(request: Request):
        library = context()
        return HTMLResponse(
            preferences_html(library.display_name),
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/setup/preferences/continue")
    def confirm_setup_preferences():
        library = context()
        with _errors(), admission(library):
            complete_initial_preferences(registry_path(), library)
        return {"next": "/setup/adoption"}

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

    @app.get("/legacy-adoption/history", response_class=HTMLResponse, include_in_schema=False)
    def adoption_history(job: str | None = Query(None, pattern=r"^[a-f0-9]{32}$"),
                         page: int = Query(1, ge=1, le=100000)):
        library = context()
        with _errors():
            entries, more = completed_adoptions(library, registry_path(), job_id=job, page=page)
        return HTMLResponse(history_html(library, entries, job_id=job, page=page, more=more),
                            status_code=404 if job and not entries else 200,
                            headers={"Cache-Control": "no-store"})

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
            with bound_directory(path) as descriptor, os.scandir(descriptor) as entries, \
                    bound_directory(library.archive_root) as archive_fd:
                names = sorted(
                    entry.name for entry in entries if not entry.name.startswith(".")
                    and entry.is_dir(follow_symlinks=False)
                )
                folders = browsable_folders(path, descriptor, library.archive_root, archive_fd, names)
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
            operation = key(library, job_id)
            with running_lock:
                metadata_was_running = operation in metadata_running
            result = inventory_status(library, job_id)
            result["plan"] = plan_status(library, job_id)
            with database_connection(library.database_path) as connection:
                item = _job(connection, library.library_id, job_id)
                result["draft"] = json.loads(item["draft_json"])
                result["reopen"] = result["draft"].pop("reopen_attempt", {})
                result["inventory_changes"] = result["draft"].pop("inventory_changes", {})
                result["draft"].pop("scan_family_proofs", None)
                attempt = result["draft"].pop("planning_attempt", {})
                issues = attempt.pop("issues", ())
                if issues:
                    attempt["files"] = file_issue_summary(issues)
                attempt["partners"] = [
                    {"xmp": case["xmp"], "candidates": [
                        {key: option[key] for key in ("raw", "files")} for option in case["candidates"]
                    ]} for case in attempt.get("partners", ())
                ]
                result["partners"] = [
                    {key: option[key] for key in ("xmp", "raw", "files")}
                    for option in result["draft"].pop("file_partners", {}).values()
                ]
                result["planning"] = attempt
                result["matching_update_required"] = (item["state"] == "inventoried" and not result["plan"]
                                                      and matching_update_required(connection, job_id))
                result["excluded_files"] = file_issue_summary(result["draft"].pop("file_exclusions", {}).values())
                result["draft_revision"] = item["draft_revision"]
                result["scan_generation"] = item["scan_generation"]
                result["layout_default"] = get_global_default(connection)
                result["subevent_prefix_enabled"] = naming_from_library_settings(library.settings)["subevent_prefix_enabled"]
                result["review_count"] = review_count(connection, job_id, result["plan"].get("id"))
            reopen = result["reopen"]
            if ((attempt.get("state") == "completed" and not result["plan"])
                    or (reopen.get("state") == "completed" and result["plan"].get("id") == reopen["plan_id"])):
                result["plan"] = plan_status(library, job_id)
            with running_lock:
                result["scan_running"] = key(library, job_id) in running
                result["registration_running"] = operation in registering
                result["metadata_running"] = metadata_was_running or operation in metadata_running
                if attempt.get("state") in {"queued", "running"} and result["plan"]:
                    attempt["state"] = "completed"
        return result

    @router.post("/jobs/{job_id}/scan", status_code=202)
    def scan(job_id: str, tasks: BackgroundTasks):
        library = context()
        with _errors(), admission(library):
            require_planning_idle(library, job_id)
            status = inventory_status(library, job_id)
            if status["state"] not in {"ready", "scanning", "inventoried"} or plan_status(library, job_id):
                raise AdoptionError("Der Auftrag ist nicht zur Inventur verfügbar.")
            require_review_idle(library, job_id)
            with database_connection(library.database_path) as connection:
                require_no_partial_publication(connection, job_id)
            with running_lock:
                if key(library, job_id) not in running:
                    with database_connection(library.database_path) as connection:
                        connection.execute(
                            "UPDATE legacy_adoption_jobs SET state='scanning', scan_error=NULL WHERE id=?",
                            (job_id,),
                        )
                    pause = Event()
                    running[key(library, job_id)] = pause
                    dispatch("scan", run_scan, library, job_id, pause, tasks=tasks)
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

    @router.get("/jobs/{job_id}/inventory-exclusions")
    def inventory_excluded(job_id: str, after: str = ""):
        with _errors():
            return inventory_exclusions(context(), job_id, after=after)

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
            require_review_idle(library, job_id)
            require_inventory_idle(library, job_id)
            return copy_review(library, job_id, payload.family_key)

    @router.get("/jobs/{job_id}/review/selection")
    def select_review_cases(job_id: str, metadata: bool = False):
        with _errors():
            return review_selection(context(), job_id, include_metadata=metadata)

    @router.post("/jobs/{job_id}/review/metadata/sources")
    def sources_for_review(job_id: str, payload: SelectedMetadata, request: Request):
        library = context()
        with _errors():
            require_adoption(request, library)
            return metadata_sources(library, job_id, revision=payload.revision, keys=payload.family_keys)

    @router.put("/jobs/{job_id}/review/metadata")
    def set_review_metadata(job_id: str, payload: StageMetadata, request: Request):
        library = context()
        with _errors(), admission(library):
            require_adoption(request, library)
            require_inventory_idle(library, job_id)
            require_review_idle(library, job_id)
            if (payload.individual and len(payload.family_keys) != 1) or (payload.source is None and not payload.individual):
                raise AdoptionError("Wähle genau eine Dateifamilie.")
            return stage_metadata(library, job_id, revision=payload.revision, keys=payload.family_keys,
                                  source=payload.source, individual=payload.individual)

    @router.post("/jobs/{job_id}/review/metadata/apply")
    def apply_review_metadata(job_id: str, payload: Freeze, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_adoption(request, library)
            require_inventory_idle(library, job_id)
            require_review_idle(library, job_id)
            operation = key(library, job_id)
            with running_lock:
                metadata_running.add(operation)
            try:
                return apply_metadata(library, job_id, revision=payload.revision, allow_existing=is_later(request))
            finally:
                with running_lock:
                    metadata_running.discard(operation)

    @router.get("/jobs/{job_id}/review/batch")
    def review_progress(job_id: str, details: bool = False):
        with _errors():
            return copy_status(context(), job_id, details=details)

    @router.post("/jobs/{job_id}/review/batch", status_code=202)
    def copy_cases(job_id: str, payload: ReviewBatch, tasks: BackgroundTasks):
        library, registry = context(), registry_path()
        with _errors(), adoption_execution_access(registry), admission(library):
            require_review_idle(library, job_id)
            require_inventory_idle(library, job_id)
            batch_id = begin_review_batch(library, job_id, payload.family_keys)
        schedule_copies(library, job_id, tasks, registry)
        return {"accepted": True, "batch_id": batch_id}

    @router.post("/jobs/{job_id}/review/batch/cancel", status_code=202)
    def cancel_copies(job_id: str, payload: CancelReviewBatch, tasks: BackgroundTasks):
        library, registry = context(), registry_path()
        # The worker owns the disk-operation locks. This request only records
        # intent and can run while a member is being copied or hashed.
        with _errors(), database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _job(connection, library.library_id, job_id)
            pending = request_review_cancel(connection, job_id, payload.batch_id)
        if pending:
            schedule_copies(library, job_id, tasks, registry)
        return {"accepted": True}

    @router.post("/jobs/{job_id}/review/batch/resume", status_code=202)
    def resume_copies(job_id: str, tasks: BackgroundTasks):
        library, registry = context(), registry_path()
        with _errors(), adoption_execution_access(registry), admission(library):
            require_inventory_idle(library, job_id)
            status = copy_status(library, job_id)
            pending = (status["pending"] or status.get("state") == "active") and not status["running"]
        if pending:
            schedule_copies(library, job_id, tasks, registry)
        return {"accepted": True}

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

    @router.post("/jobs/{job_id}/draft/structure")
    def draft_structure(job_id: str, draft: Draft, request: Request):
        from app.legacy_adoption_plan import preview_event_directories
        library = context()
        with _errors():
            require_adoption(request, library)
            return preview_event_directories(library, job_id, draft.model_dump(exclude_none=True),
                                             allow_existing=is_later(request))

    @router.put("/jobs/{job_id}/draft")
    def save_draft(job_id: str, draft: SaveDraft, request: Request):
        library = context()
        with _errors(), admission(library), database_connection(library.database_path) as connection:
            require_adoption(request, library)
            require_planning_idle(library, job_id)
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
            previous = json.loads(item["draft_json"])
            saved = draft.model_dump(exclude_none=True, exclude={"revision"})
            saved["file_exclusions"] = previous.get("file_exclusions", {})
            saved["file_partners"] = previous.get("file_partners", {})
            saved["metadata_review_pending"] = {
                key: choice for key, choice in previous.get("metadata_review_pending", {}).items()
                if key not in saved["capture_overrides"]
            }
            saved["metadata_review_applied"] = {
                key: choice for key, choice in previous.get("metadata_review_applied", {}).items()
                if saved["capture_overrides"].get(key) == choice["time"]
            }
            connection.execute(
                "UPDATE legacy_adoption_jobs SET draft_json = ?, draft_revision = ? WHERE id = ?",
                (json.dumps(saved), revision, job_id),
            )
        return {"saved": True, "revision": revision}

    @router.post("/jobs/{job_id}/planning-exclusions")
    def update_planning_exclusions(job_id: str, command: PlanningExclusions, request: Request):
        library = context()
        with _errors(), admission(library), database_connection(library.database_path) as connection:
            require_adoption(request, library)
            require_planning_idle(library, job_id)
            connection.execute("BEGIN IMMEDIATE")
            row = _job(connection, library.library_id, job_id)
            if (command.acknowledged is not True or row["draft_revision"] != command.revision
                    or row["state"] != "inventoried" or connection.execute(
                    "SELECT 1 FROM legacy_adoption_plans WHERE job_id=?", (job_id,)).fetchone()):
                raise AdoptionError("Der Entwurf ist nicht mehr aktuell oder die Bestätigung fehlt.")
            draft = json.loads(row["draft_json"])
            attempt = draft.pop("planning_attempt", {})
            excluded = draft.setdefault("file_exclusions", {})
            if command.restore:
                excluded.clear()
            else:
                issues = attempt.get("issues", ())
                if (not issues or attempt.get("revision") != command.revision
                        or any(item.get("identity_version") != IDENTITY_VERSION for item in issues)):
                    raise AdoptionError("Es fehlen bestätigbare Ergebnisse der aktuellen Planprüfung.")
                excluded.update((item["path"], item) for item in issues)
            revision = command.revision + 1
            connection.execute(
                "UPDATE legacy_adoption_jobs SET draft_json=?, draft_revision=? WHERE id=?",
                (json.dumps(draft), revision, job_id),
            )
        return {"revision": revision, "excluded_files": file_issue_summary(excluded.values())}

    @router.post("/jobs/{job_id}/planning-partners")
    def update_planning_partners(job_id: str, command: PlanningPartners, request: Request):
        library = context()
        with _errors(), admission(library), database_connection(library.database_path) as connection:
            require_adoption(request, library)
            require_planning_idle(library, job_id)
            require_inventory_idle(library, job_id)
            require_review_idle(library, job_id)
            connection.execute("BEGIN IMMEDIATE")
            require_no_partial_publication(connection, job_id)
            row = _job(connection, library.library_id, job_id)
            if (not command.acknowledged or row["draft_revision"] != command.revision
                    or row["state"] != "inventoried" or connection.execute(
                    "SELECT 1 FROM legacy_adoption_plans WHERE job_id=?", (job_id,)).fetchone()):
                raise AdoptionError("Der Entwurf ist nicht mehr aktuell oder die Bestätigung fehlt.")
            draft = json.loads(row["draft_json"])
            attempt = draft.pop("planning_attempt", {})
            decisions = draft.setdefault("file_partners", {})
            if command.restore:
                decisions.clear()
            else:
                options = {(case["xmp"], option["raw"]): option for case in attempt.get("partners", ())
                           for option in case["candidates"] if option["version"] == IDENTITY_VERSION}
                if (not command.choices or len({choice.xmp for choice in command.choices}) != len(command.choices)
                        or attempt.get("state") != "failed" or attempt.get("revision") != command.revision
                        or any((choice.xmp, choice.raw) not in options or choice.xmp in decisions
                               for choice in command.choices)):
                    raise AdoptionError("Wähle genau einen angebotenen RAW-Partner pro XMP aus der aktuellen Planprüfung.")
                decisions.update((choice.xmp, options[choice.xmp, choice.raw]) for choice in command.choices)
                resolve_partners(inventory_members(connection, job_id), draft)
            revision = command.revision + 1
            connection.execute(
                "UPDATE legacy_adoption_jobs SET draft_json=?, draft_revision=? WHERE id=?",
                (json.dumps(draft), revision, job_id),
            )
        return {"revision": revision}

    @router.post("/jobs/{job_id}/plan")
    def freeze(job_id: str, draft: FreezePlan, request: Request, tasks: BackgroundTasks):
        library = context()
        with _errors(), admission(library):
            require_adoption(request, library)
            require_inventory_idle(library, job_id)
            require_review_idle(library, job_id)
            with database_connection(library.database_path) as connection:
                require_no_partial_publication(connection, job_id)
                if matching_update_required(connection, job_id):
                    raise AdoptionError("Aktualisiere die Inventur für die neue RAW- und XMP-Zuordnung.")
            operation = key(library, job_id)
            with running_lock:
                if operation in planning:
                    raise AdoptionError("Die Planprüfung läuft bereits.")
                planning.add(operation)
            try:
                planning_attempt(library, job_id, draft, state="queued")
                later = is_later(request)
                if draft.background:
                    dispatch("planning", run_planning, library, job_id, draft, later, tasks=tasks)
                    return JSONResponse({"accepted": True}, status_code=202)
            except Exception:
                with running_lock:
                    planning.discard(operation)
                raise
        with _errors():
            return run_planning(library, job_id, draft, later)

    @router.post("/jobs/{job_id}/execution-method")
    def select_execution(job_id: str, command: SelectExecution, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_adoption(request, library)
            require_review_idle(library, job_id)
            require_preparation_idle(library, job_id)
            with database_connection(library.database_path) as connection:
                require_no_partial_publication(connection, job_id)
            create_plan(
                library, registry_path(), job_id, allow_existing=is_later(request),
                filename_method=command.method, replace_plan_id=command.plan_id,
            )
            prepare_documents(library, job_id)
            return plan_status(library, job_id)

    @router.get("/jobs/{job_id}/directories")
    def directories(job_id: str, after: str = ""):
        with _errors():
            return plan_directories(context(), job_id, after=after)

    @router.get("/jobs/{job_id}/moves")
    def moves(job_id: str, after: str = "", renamed: bool = False):
        with _errors():
            return plan_moves(context(), job_id, after=after, renamed=renamed)

    @router.get("/jobs/{job_id}/issues")
    def issues(job_id: str):
        with _errors():
            return plan_issues(context(), job_id)

    @router.post("/jobs/{job_id}/documents")
    def documents(job_id: str):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_preparation_idle(library, job_id)
            return prepare_documents(library, job_id)

    @router.get("/jobs/{job_id}/manual-work")
    def manual_steps(job_id: str, check: bool = False):
        with _errors():
            return manual_work(context(), job_id, check=check)

    @router.get("/jobs/{job_id}/download/{artifact}")
    def download(job_id: str, artifact: Literal[
        "folders", "documents", "original-documents", "manifest", "manual-setup", "original-folders",
    ]):
        library = context()
        if artifact == "manifest":
            return _download(lambda: manifest_file(library, job_id), "bestandsuebernahme.jsonl",
                             media_type="application/x-ndjson")
        with _errors():
            execution = plan_status(library, job_id).get("execution")
            allowed = {
                "original-documents": {"manual", "repair", "rolling_back"},
                "original-folders": {"rolling_back"},
            }.get(artifact, {"manual"})
            if not execution or execution["method"] != "manual" or execution["phase"] not in allowed:
                raise AdoptionError("Diese Unterlagen sind für den aktuellen Ausführungsschritt gesperrt.")
        if artifact in {"folders", "manual-setup", "original-folders"}:
            return _download(
                lambda: directory_scaffold(library, job_id, documents=artifact == "manual-setup",
                                           original=artifact == "original-folders"),
                "quellordnergeruest.zip" if artifact == "original-folders" else "archiv-ordnergeruest.zip",
            )
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
            require_preparation_idle(library, job_id)
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
            with running_lock:
                result["release_running"] = key(library, job_id) in releasing
            if getattr(request.state, "legacy_adoption_recovery", False) and plan["execution"]["phase"] != "rolling_back":
                result.pop("command", None)
            return result

    @router.post("/jobs/{job_id}/script/release")
    def script_release(job_id: str, command: PlanCommand):
        library = context()
        operation = key(library, job_id)
        with _errors():
            with running_lock:
                if operation in releasing:
                    raise AdoptionError("Der Nachweis für den Skriptbefehl wird bereits geprüft.")
                releasing.add(operation)
            try:
                with (
                    adoption_execution_access(registry_path()), admission(library),
                    locked_script(library, job_id, command.plan_id) as (descriptor, script),
                ):
                    if script["phase"] not in {"script_prepared", "repair"}:
                        raise AdoptionError("Die Skriptausführung ist in dieser Phase gesperrt.")
                    reject_stale_script(library, descriptor, script, command.plan_id)
                    try:
                        assert_unstarted_release_current(library, job_id, command.plan_id, descriptor, script)
                    except (AdoptionError, DatasetError, OSError) as error:
                        if not script_journal_started(descriptor):
                            permit(descriptor, script, None)
                        raise AdoptionError(
                            "Skriptnachweis veraltet. Prüfe die Inventur und bereite den Plan erneut vor. " + str(error)
                        ) from error
                    change_phase(library, job_id, command.plan_id, "script_prepared",
                                 from_phases={"script_prepared", "repair"})
                    return {"command": permit(descriptor, script, "apply")}
            finally:
                with running_lock:
                    releasing.discard(operation)

    def run_script_preparation(library, job_id, plan_id, probe_digest):
        """Independent OS-locked worker; progress resides on disk, not a socket."""
        try:
            with exclusive_preparation_worker(job_id, plan_id) as exclusive:
                if not exclusive:
                    # Another process is already hashing this exact package.
                    # Never mark its shared progress record as a failure.
                    return
                try:
                    with adoption_execution_access(registry_path(), wait_seconds=2), admission(library):
                        record_preparation(
                            library, job_id, plan_id, probe_digest, "running", phase="hashing",
                        )

                        def checkpoint(package, processed, total, bytes_processed, bytes_total, *, phase, elapsed_seconds):
                            record_preparation(
                                library, job_id, plan_id, probe_digest, "running",
                                phase=phase, processed=processed, total=total, elapsed_seconds=elapsed_seconds,
                                bytes_processed=bytes_processed, bytes_total=bytes_total,
                                descriptor=package,
                            )

                        confirm_plan(
                            library, job_id, plan_id, "script", acknowledged=True,
                            probe_digest=probe_digest, progress=checkpoint,
                        )
                        record_preparation(
                            library, job_id, plan_id, probe_digest, "completed",
                            phase="manifest_ready",
                        )
                except Exception as error:
                    logging.getLogger(__name__).exception(
                        "Legacy adoption script preparation failed for %s", job_id,
                    )
                    try:
                        record_preparation(
                            library, job_id, plan_id, probe_digest, "failed",
                            phase="attention_required", error=str(error)[:500],
                        )
                    except Exception:
                        logging.getLogger(__name__).exception(
                            "Cannot persist failed legacy preparation for %s", job_id,
                        )
        finally:
            with running_lock:
                preparing.discard(key(library, job_id))

    @router.get("/jobs/{job_id}/preparation")
    def preparation(job_id: str):
        library = context()
        with _errors():
            plan = plan_status(library, job_id)
            if not plan.get("id"):
                return {"state": "not_started"}
            result = preparation_status(library, job_id, plan["id"])
            if (plan.get("execution") or {}).get("method") == "script":
                read_manifest(library, job_id, plan["id"])
                return {**(result or {}), "state": "completed", "phase": "manifest_ready", "worker_active": False}
            if not result:
                return {"state": "not_started"}
            if result["state"] == "completed":
                result = {**result, "state": "failed", "phase": "attention_required",
                          "error": "Die gespeicherte Vorbereitung wurde in der Datenbank nicht bestätigt."}
            with running_lock:
                local_running = key(library, job_id) in preparing
            # Distinguish a genuinely active process anywhere on the server
            # from a stale running record left after a restart.
            return {**result, "worker_active": (
                preparation_worker_active(job_id, plan["id"]) or local_running
            )}

    @router.post("/jobs/{job_id}/preparation/abandon")
    def abandon_preparation(job_id: str, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_adoption(request, library)
            plan = plan_status(library, job_id)
            if not plan.get("id") or plan.get("execution"):
                raise AdoptionError("Nur eine nicht bestätigte Skriptvorbereitung darf zurückgesetzt werden.")
            with running_lock:
                if key(library, job_id) in preparing:
                    raise AdoptionError("Die Vorbereitung ist noch aktiv.")
            return {
                "abandoned": abandon_failed_preparation(library, job_id, plan["id"]),
            }

    @router.post("/jobs/{job_id}/confirm")
    def confirm(job_id: str, command: Confirm, request: Request, tasks: BackgroundTasks):
        library = context()
        if command.method != "script":
            with _errors(), adoption_execution_access(registry_path()), admission(library):
                require_adoption(request, library)
                require_review_idle(library, job_id)
                return confirm_plan(library, job_id, command.plan_id, command.method,
                                    acknowledged=command.acknowledged, probe_digest=command.probe_sha256)
        # Script preparation may read hundreds of gigabytes; never keep the
        # confirmation HTTP request open while checksums are computed.
        with _errors(), admission(library):
            require_adoption(request, library)
            require_review_idle(library, job_id)
            if not command.acknowledged or not command.probe_sha256:
                raise AdoptionError("Bestätige die Sicherheitsbedingungen und den Hostnachweis.")
            plan = plan_status(library, job_id)
            execution = plan.get("execution")
            if plan.get("id") == command.plan_id and (execution or {}).get("method") == "script":
                read_manifest(library, job_id, plan["id"])
                return plan
            if (plan.get("id") != command.plan_id or plan.get("filename_method") != "script"
                    or plan.get("state") != "prepared" or execution):
                raise AdoptionError("Nur der aktuell vorbereitete Skriptplan darf bestätigt werden.")
            proof = probe_details(library, job_id, command.plan_id)
            if not proof.get("verified") or proof.get("sha256") != command.probe_sha256:
                raise AdoptionError("Der bestätigte Hostpfadnachweis fehlt oder ist veraltet.")
            with running_lock:
                current_key = key(library, job_id)
                if current_key not in preparing:
                    reserve_preparation(library, job_id, command.plan_id, command.probe_sha256)
                    preparing.add(current_key)
                    dispatch("preparation", run_script_preparation, library, job_id,
                             command.plan_id, command.probe_sha256, tasks=tasks)
            return JSONResponse(
                {"accepted": True, "preparation": preparation_status(library, job_id, command.plan_id)},
                status_code=202,
            )

    script_completion_phases = {"script_prepared", "operations_done", "verifying", "repair", "registration_pending"}

    def reject_stale_script(library, descriptor, script, plan_id):
        if script_documents_stale(library, plan_id):
            permit(descriptor, script, None)
            raise AdoptionError(STALE_XMP_DOCUMENTS)

    def retire_completed_script(library, descriptor, script, plan_id):
        reject_stale_script(library, descriptor, script, plan_id)
        if script["phase"] not in script_completion_phases:
            raise AdoptionError("Der Übernahmeauftrag ist für diesen Schritt nicht verfügbar.")
        status = script_status(descriptor, script)
        if not status or (status["state"], status["mode"]) != ("completed", "apply"):
            raise AdoptionError("Das externe Skript hat die Ausführung noch nicht abgeschlossen.")
        permit(descriptor, script, None)

    @router.post("/jobs/{job_id}/verify")
    def verify(job_id: str, command: PlanCommand):
        # Compatibility with already open assistants and older clients.
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            planned = plan_status(library, job_id)
            execution = planned.get("execution")
            if execution and execution["method"] == "script":
                with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                    retire_completed_script(library, descriptor, script, command.plan_id)
                    change_phase(library, job_id, command.plan_id, "operations_done",
                                 from_phases=script_completion_phases)
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
            plan = plan_status(library, job_id)
            execution = plan.get("execution")
            if execution and execution["method"] == "script":
                phases.update(("script_prepared", "operations_done"))
                with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                    if script["phase"] not in phases:
                        raise AdoptionError("Eine Skriptrücknahme ist in dieser Phase gesperrt.")
                    permit(descriptor, script, None)
                    change_phase(library, job_id, command.plan_id, "rolling_back", from_phases=phases)
                    permit(descriptor, script, "rollback", rollback_directories=rollback_directory_scope(library, plan))
            else:
                change_phase(library, job_id, command.plan_id, "rolling_back", from_phases=phases)
            return plan_status(library, job_id)

    def check_rollback(library, job_id, plan_id, *, keep_draft=False, finish=None):
        execution = plan_status(library, job_id).get("execution")
        if execution and execution["method"] == "script":
            with locked_script(library, job_id, plan_id) as (descriptor, script):
                if script["phase"] != "rolling_back":
                    raise AdoptionError("Starte zuerst den vorgesehenen Wiederherstellungsweg.")
                keep_draft = keep_draft or script_documents_stale(library, plan_id)
                if keep_draft and script_journal_started(descriptor):
                    status = script_status(descriptor, script)
                    if not status or (status.get("state"), status.get("mode")) != ("rolled_back", "rollback"):
                        raise AdoptionError("Schließe zuerst die kontrollierte Skriptrücknahme ab.")
                return complete_rollback(library, job_id, plan_id, keep_draft=keep_draft, finish=finish,
                                         before_commit=lambda: permit(descriptor, script, None))
        return complete_rollback(library, job_id, plan_id, finish=finish)

    @router.post("/jobs/{job_id}/rollback/check")
    def rollback_check(job_id: str, command: RollbackCheck, tasks: BackgroundTasks):
        with _errors():
            return start_reopen(context(), job_id, command, tasks, kind="rollback")

    def run_finalize(library, job_id, plan_id):
        registry = registry_path()
        try:
            with adoption_execution_access(registry, wait_seconds=2):
                finalize_adoption(library, registry, job_id, plan_id)
        except Exception:
            logging.getLogger(__name__).exception("Legacy adoption finalization stopped for %s", job_id)
        finally:
            with running_lock:
                registering.discard(key(library, job_id))

    def schedule_finalization(library, job_id, plan_id, tasks=None):
        operation = key(library, job_id)
        with running_lock:
            if operation not in registering:
                registering.add(operation)
                dispatch("registration", run_finalize, library, job_id, plan_id, tasks=tasks)

    @router.post("/jobs/{job_id}/finalize")
    def finalize(job_id: str, command: FinishPlan, request: Request, tasks: BackgroundTasks):
        library = context()
        with _errors(), adoption_execution_access(registry_path()):
            with read_session():
                planned = plan_status(library, job_id)
            if planned.get("id") != command.plan_id:
                raise AdoptionError("Der angezeigte Verschiebeplan ist veraltet.")
            if planned["state"] == "completed":
                assert_completed_adoption(library, registry_path(), job_id, command.plan_id)
                return planned
            execution = planned["execution"]
            if execution is None or execution["phase"] != "registering":
                with admission(library):
                    require_adoption(request, library)
                    if execution and execution["method"] == "script":
                        with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                            retire_completed_script(library, descriptor, script, command.plan_id)
                            change_phase(library, job_id, command.plan_id, "registering",
                                         from_phases=script_completion_phases)
                    else:
                        change_phase(library, job_id, command.plan_id, "registering",
                                     from_phases={"manual", "verifying", "repair", "registration_pending"})
            if not command.background:
                return finalize_adoption(library, registry_path(), job_id, command.plan_id)
        schedule_finalization(library, job_id, command.plan_id, tasks)
        return JSONResponse({"accepted": True}, status_code=202)

    def store_reopen(connection, job, attempt):
        draft = json.loads(job["draft_json"])
        draft["reopen_attempt"] = attempt
        connection.execute("UPDATE legacy_adoption_jobs SET draft_json=? WHERE id=?",
                           (json.dumps(draft), job["id"]))

    def run_reopen(library, job_id, attempt, background):
        operation = key(library, job_id)
        registry = registry_path()
        lock = registry.with_name(registry.name + ".adoption-return.lock")
        try:
            with _lock(lock, exclusive=True):
                try:
                    with adoption_execution_access(registry, wait_seconds=2), admission(library):
                        with database_connection(library.database_path) as connection:
                            connection.execute("BEGIN IMMEDIATE")
                            job = _job(connection, library.library_id, job_id)
                            saved = json.loads(job["draft_json"]).get("reopen_attempt", {})
                            if saved.get("id") != attempt["id"] or saved.get("state") not in {"queued", "running"}:
                                return
                            store_reopen(connection, job, {**attempt, "state": "running"})
                        plan_id = attempt["plan_id"]
                        if attempt.get("kind") == "rollback":
                            def rolled_back(connection, job, keep_draft):
                                store_reopen(connection, job, {**attempt, "state": "completed",
                                                               "step": "inventory" if keep_draft else "setup"})

                            return check_rollback(library, job_id, plan_id, keep_draft=attempt["keep_draft"],
                                                  finish=rolled_back)
                        require_review_idle(library, job_id)
                        require_preparation_idle(library, job_id)

                        def completed(connection, job, changed):
                            store_reopen(connection, job, {**attempt, "state": "completed",
                                                           "changed_sources": changed,
                                                           "step": "inventory" if changed else "plan"})

                        reopen_plan(library, job_id, expected_id=plan_id, finish=completed)
                        return {"reopened": True}
                except Exception as error:
                    with database_connection(library.database_path) as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        job = _job(connection, library.library_id, job_id)
                        saved = json.loads(job["draft_json"]).get("reopen_attempt", {})
                        if saved.get("id") == attempt["id"]:
                            store_reopen(connection, job, {**attempt, "state": "failed", "message": str(error)})
                    if not background:
                        raise
                    logging.getLogger(__name__).info("Legacy adoption return %s: %s", job_id, error)
        except RootOperationBusy:
            if not background:
                raise
        finally:
            with running_lock:
                reopening.discard(operation)

    def schedule_reopen(library, job_id, attempt, tasks=None):
        with running_lock:
            operation = key(library, job_id)
            if operation in reopening:
                return
            reopening.add(operation)
        dispatch("reopen", run_reopen, library, job_id, attempt, True, tasks=tasks)

    def start_reopen(library, job_id, command, tasks, *, kind="draft"):
        keep_draft = getattr(command, "keep_draft", False)
        with database_connection(library.database_path) as connection:
            job = _job(connection, library.library_id, job_id)
            previous = json.loads(job["draft_json"]).get("reopen_attempt", {})
        previous_state = previous.get("state")
        same_request = (command.plan_id, kind, keep_draft) == (
            previous.get("plan_id"), previous.get("kind", "draft"), previous.get("keep_draft", False),
        )
        if previous_state in {"queued", "running"}:
            if not same_request:
                raise AdoptionError("Der Verschiebeplan wird bereits zurückgenommen.")
            schedule_reopen(library, job_id, previous, tasks)
            return JSONResponse({"accepted": True}, status_code=202)
        if previous_state == "completed" and same_request and previous["step"] != "setup":
            return {"reopened": True}
        with adoption_execution_access(registry_path()), admission(library):
            if kind == "draft":
                require_review_idle(library, job_id)
                require_preparation_idle(library, job_id)
            with database_connection(library.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                job = _job(connection, library.library_id, job_id)
                if json.loads(job["draft_json"]).get("reopen_attempt", {}) != previous:
                    raise AdoptionError("Der Verschiebeplan wird bereits zurückgenommen.")
                if kind == "draft":
                    plan_id = editable_plan(connection, job_id)["id"]
                else:
                    plan = connection.execute(
                        """SELECT plan.id FROM legacy_adoption_plans plan
                             JOIN legacy_adoption_execution execution ON execution.plan_id=plan.id
                            WHERE plan.job_id=? AND execution.phase='rolling_back'""", (job_id,),
                    ).fetchone()
                    if plan is None:
                        raise AdoptionError("Starte zuerst den vorgesehenen Wiederherstellungsweg.")
                    plan_id = plan["id"]
                if command.plan_id is not None and command.plan_id != plan_id:
                    raise AdoptionError("Der geprüfte Verschiebeplan wurde ersetzt.")
                attempt = {"id": uuid4().hex, "plan_id": plan_id, "state": "queued",
                           "kind": kind, "keep_draft": keep_draft}
                store_reopen(connection, job, attempt)
        if command.background:
            schedule_reopen(library, job_id, attempt, tasks)
            return JSONResponse({"accepted": True}, status_code=202)
        return run_reopen(library, job_id, attempt, False)

    @router.post("/jobs/{job_id}/reopen")
    def reopen(job_id: str, tasks: BackgroundTasks, command: ReopenPlan | None = None):
        with _errors():
            return start_reopen(context(), job_id, command or ReopenPlan(), tasks)

    @router.post("/jobs/{job_id}/script/reopen-unstarted")
    def reopen_unstarted_script(job_id: str, command: PlanCommand, request: Request):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_adoption(request, library)
            require_review_idle(library, job_id)
            with locked_script(library, job_id, command.plan_id) as (descriptor, script):
                with database_connection(library.database_path) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    plan = connection.execute(
                        """SELECT id FROM legacy_adoption_plans
                           WHERE id=? AND job_id=? AND state='prepared'""",
                        (command.plan_id, job_id),
                    ).fetchone()
                    if not plan:
                        raise AdoptionError("Der bestätigte Verschiebeplan ist eingefroren.")
                    retire_unstarted_package(descriptor, script)
                    connection.execute("DELETE FROM legacy_adoption_plans WHERE id=?", (command.plan_id,))
        return {"reopened": True}

    @router.delete("/jobs/{job_id}")
    def discard(job_id: str):
        library = context()
        with _errors(), adoption_execution_access(registry_path()), admission(library):
            require_planning_idle(library, job_id)
            require_preparation_idle(library, job_id)
            if copy_status(library, job_id)["running"]:
                raise AdoptionError("Schließe den Kopierauftrag zuerst ab.")
            with database_connection(library.database_path) as connection:
                require_no_partial_publication(connection, job_id)
            discard_job(library, job_id)
        return {"discarded": True}

    @app.on_event("startup")
    def resume_pending_adoption():
        registry = registry_path()
        try:
            reservation = active_adoption(registry)
            if not reservation:
                return
            job_id = reservation["job_id"]
            library = resolve_library_context(registry, reservation["library_id"])
            operation = key(library, job_id)
            plan_id = reservation["plan_id"]
            if reservation["phase"] in {"script_prepared", "operations_done", "verifying", "repair",
                                        "registration_pending", "registering"}:
                plan = plan_status(library, job_id)
                if (plan.get("execution") or {}).get("method") == "script" and script_documents_stale(library, plan_id):
                    # The runner and its original journal must remain available
                    # for rollback. Revoke any previous apply permission.
                    with locked_script(library, job_id, plan_id) as (descriptor, script):
                        permit(descriptor, script, None)
            if reservation["phase"] == "registering":
                schedule_finalization(library, job_id, plan_id)
                return
            if plan_id:
                with database_connection(library.database_path) as connection:
                    job = _job(connection, library.library_id, job_id)
                    reopen = json.loads(job["draft_json"]).get("reopen_attempt", {})
                if reopen.get("state") in {"queued", "running"} and reopen.get("plan_id") == plan_id:
                    schedule_reopen(library, job_id, reopen)
                    return
                if not reservation["phase"] and (digest := saved_preparation_proof(library, job_id, plan_id)):
                    with running_lock:
                        if operation not in preparing:
                            preparing.add(operation)
                            dispatch("recovered-preparation", run_script_preparation, library, job_id, plan_id, digest)
                return
            if copy_status(library, job_id).get("state") in {"active", "cancelling"}:
                schedule_copies(library, job_id, None, registry)
                return
            with database_connection(library.database_path) as connection:
                row = _job(connection, library.library_id, job_id)
                attempt = json.loads(row["draft_json"]).get("planning_attempt", {})
                interrupted_scan = row["state"] == "scanning" and row["scan_error"] is None
                if not interrupted_scan and (
                    attempt.get("state") not in {"queued", "running"} or attempt.get("revision") != row["draft_revision"]
                ):
                    return
            if interrupted_scan:
                with running_lock:
                    if operation not in running:
                        pause = Event()
                        running[operation] = pause
                        dispatch("recovered-scan", run_scan, library, job_id, pause)
                return
            command = FreezePlan(revision=attempt["revision"], filename_method=attempt["method"], background=True)
            operation = key(library, job_id)
            with running_lock:
                if operation not in planning:
                    planning.add(operation)
                    dispatch("recovered-planning", run_planning, library, job_id, command,
                             reservation["access_kind"] == "library")
        except (AdoptionError, ExecutionError, RootOperationError, LibraryRegistryError, OSError,
                sqlite3.DatabaseError, ValueError):
            logging.getLogger(__name__).exception("Could not resume pending adoption work")

    app.include_router(router)
