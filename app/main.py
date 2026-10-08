from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
import json
import hashlib
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
import time

from PIL import Image, ImageOps

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from app import __version__
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.transfer_ui import TRANSFER_HTML
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.trash_ui import TRASH_HTML
from app.trash import (
    TRASH_CONFIRMATION, TrashError, reconcile_trash_inventory,
    empty_trash_filesystem, purge_trash_database,
)
from app.ui_shell import apply_shell
from app import view_cache
from app import background_mutation_cancel as cancel_queue
from app.background_activity import current_activity
from app.live_inventory import refresh_live_event_inventories
from app.global_workspace import build_global_workspace_summary
from app.global_stock import (
    GlobalStockError,
    migrate_main_free_stock_to_central,
    project_all_imports,
    project_import_job,
    propagate_corrected_family,
    synchronize_central_stock_projections,
)
from app.central_stock_reconcile import reconcile_central_free_stock
from app.external_changes import (
    ExternalChangeError,
    acknowledge_external_notices,
    dismiss_external_notice,
    list_external_change_state,
    repair_external_conflicts,
    repair_external_notice,
)
from app.operation_batches import (
    OperationBatchError,
    create_apply_batch,
    execute_apply_batch,
    get_operation_batch,
    list_active_operation_batches,
    recover_operation_batches,
)
from app.canonical_membership import resolve_payload_membership
from app.event_layout import (
    ensure_event_layout_snapshot,
    get_event_layout,
    get_global_default as get_global_event_folder_layout,
    set_global_default as set_global_event_folder_layout,
    update_event_layout,
    EventLayoutError,
)
from app.event_structure_changes import (
    detect_all_event_structure_changes,
    get_structure_change,
    confirm_applied_structure_change,
    prepare_archived_structure_change,
    verify_archived_structure_change,
    EventStructureChangeError,
)

from app.database import (
    claim_next_job,
    complete_job,
    create_job,
    find_folder_import_by_identity,
    set_job_source_identity,
    create_planned_event,
    delete_planned_event,
    fail_job,
    get_job,
    get_event_edit_context,
    initialize_database,
    list_archive_change_reviews,
    list_database_jobs,
    list_file_metadata_candidates,
    list_job_day_groups,
    list_job_events,
    search_events,
    list_global_tasks,
    list_no_event_month_targets,
    assign_free_families_to_existing_no_event,
    list_job_time_segments,
    list_job_files,
    mark_running_jobs_interrupted,
    recover_failed_job_as_completed,
    repair_interrupted_jobs_from_terminal_evidence,
    store_metadata_analysis,
    update_import_file_paths,
    set_job_source_volume_label,
    update_event_definition,
    update_job_progress,
    database_connection,
    list_imported_source_files,
    list_imported_media_origins,
    store_imported_source_files,
)
from app.metadata import MetadataError, analyze_tree
from app.metadata_correction import (
    MetadataCorrectionError,
    apply_metadata_correction,
    cancel_metadata_correction,
    create_metadata_correction,
    execute_metadata_correction,
    get_metadata_correction,
    list_metadata_corrections,
    metadata_area_paths,
    preview_multiple_metadata_correction,
    apply_multiple_metadata_correction,
    reintegrate_library_metadata_family,
    scan_metadata_area,
)
from app.event_naming import (
    EventNamingError,
    legacy_naming_for_existing_event,
    naming_from_library_settings,
    normalize_event_naming,
)
from app.pipeline import (
    recover_cross_device_protocol_failures,
    run_simulated_job,
    sha256_file,
)
from app.folder_import import (
    ImportCancelled,
    cleanup_completed_folder_import,
    run_folder_import_job,
    quick_source_signature,
)
from app.event_structure import (
    EventPreviewError,
    build_event_preview,
)
from app.planning import (
    list_job_available_families,
    list_job_planning_overview,
    list_global_released_archive_groups,
)
from app.free_stock_layout import (
    FreeStockLayoutError,
    canonical_free_directory,
)
from app.sort_plan import (
    SortPlanError,
    build_event_sort_plan,
)
from app.sort_apply import (
    SortApplyError,
    execute_sort_run,
    get_sort_run,
    latest_event_sort_run,
    mark_incomplete_sort_runs_interrupted,
    recover_interrupted_sort_runs,
    prepare_sort_run,
)
from app.event_reapply import prepare_reapply_sort_run
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    prepare_workspace_reconcile_run,
    execute_workspace_reconcile_run,
)
from app.backup_lifecycle import (
    list_backup_lifecycles,
    upsert_backup_lifecycle,
)
from app.backup_management import (
    BackupDeletionError,
    backup_deletion_status,
    delete_backup,
)
from app.archive_transfer import (
    ArchiveVerificationError,
    list_archive_candidates,
    verify_event_archive,
)
from app.ssd_release import (
    SsdReleaseError,
    finalize_manually_moved_event_if_verified,
    release_event_ssd,
)
from app.workspace_layout import (
    BACKUP_DIRECTORY_NAME,
    WORK_DIRECTORY_NAME,
    WorkspaceLayoutError,
    backup_root as workspace_backup_root,
    ensure_workspace_layout,
    migrate_legacy_applied_files,
    resolve_library_work_root,
)

from app.storage_config import (
    StorageSettingsError,
    default_library_work_root,
    load_storage_settings,
    normalize_storage_settings,
    save_storage_settings,
    storage_paths,
    load_metadata_correction_settings,
    save_metadata_correction_settings,
)

from app.library_registry import (
    MAIN_LIBRARY_ID,
    LibraryRegistryError,
    initialize_library_registry,
    adopt_main_library,
    list_libraries,
    get_library,
    register_library,
    ensure_library_identity,
    read_library_identity,
    update_library_display_name,
    update_library_database_path,
    update_library_paths,
    update_library_settings,
    set_library_active,
    remove_library_registration,
    unregister_library,
    list_library_import_job_ids,
    remove_source_backup,
)
from app.library_context import (
    LibraryContext,
    resolve_library_context,
    list_active_library_contexts,
)
from app.library_runtime import (
    get_current_library,
    reset_current_library,
    set_current_library,
)
from app.global_library_inventory import (
    admitted_family_keys,
    backfill_library_claims,
    backfill_library_inventory,
    blocked_family_ids,
    claim_event_families,
    promote_family_ids_owned,
    register_analysis_inventory,
    release_event_reservations,
    release_family_ids_claims,
    release_new_reservations,
    reserve_family_ids,
)

# ── Change-Request-Workflow (0.16.0) ────────────────────────────
from app.event_change_request import (
    propose_event_change,
    list_event_change_requests,
    get_event_change_request,
    get_event_change_files,
    EventChangeRequestError,
)
from app.event_change_apply import (
    confirm_event_change,
    cancel_event_change,
    finish_event_change,
    verify_event_change,
    EventChangeApplyError,
)

from app.event_suggestions import (
    EventSuggestionError,
    accept_event_suggestion,
    list_event_suggestions,
)
from app.archive_cascade import prepare_archived_cascade_impacts
from app.archive_change_assistant import build_archive_change_assistant
from app.archive_reassignment import (
    list_archive_reassignments,
    assign_archive_reassignments,
    ArchiveReassignmentError,
)


APP_VERSION = __version__
RELEASE_VERSION = "0.28.7"
DEPLOYMENT_VERSION = "0.45.4"

CONFIG_PATH = Path(
    os.environ.get(
        "KAMERA_CONFIG",
        "/config/settings.json",
    )
)

WORKSPACE_PATH = Path(
    os.environ.get(
        "KAMERA_WORKSPACE",
        "/workspace",
    )
)

DATABASE_DIRECTORY = Path(
    os.environ.get(
        "KAMERA_DATABASE_DIR",
        "/database",
    )
)

DATABASE_FILE = DATABASE_DIRECTORY / "kamera.sqlite3"

REGISTRY_DATABASE_FILE = Path(
    os.environ.get(
        "KAMERA_REGISTRY_DATABASE",
        str(DATABASE_DIRECTORY / "bibliothekar-global.sqlite3"),
    )
)

LOG_PATH = Path(
    os.environ.get(
        "KAMERA_LOG_DIR",
        "/logs",
    )
)

POOL_PROBE_PATH = Path(
    os.environ.get(
        "KAMERA_POOL_PROBE",
        "/workspace",
    )
)

ARCHIVE_ROOT = Path(
    os.environ.get(
        "KAMERA_ARCHIVE_ROOT",
        "/main-library",
    )
)

IMPORT_ROOT = Path(
    os.environ.get(
        "KAMERA_IMPORT_ROOT",
        "/sources/import",
    )
)

REMOVABLE_ROOT = Path(
    os.environ.get(
        "KAMERA_REMOVABLE_ROOT",
        "/sources/removable",
    )
)

NAS_SOURCE_ROOT = Path(
    os.environ.get(
        "KAMERA_NAS_SOURCE_ROOT",
        "/sources/nas",
    )
)

SOURCE_HELPER_URL = os.environ.get(
    "KAMERA_SOURCE_HELPER_URL",
    "http://source-helper:8090",
).rstrip("/")


def build_main_library_context() -> LibraryContext:
    legacy = WORKSPACE_PATH / WORK_DIRECTORY_NAME
    # Reiner Bootstrap-Kontext für Codepfade ohne Request. Er erzeugt und
    # impliziert niemals /Arbeitsbereiche/main. Ohne registrierte Bibliothek
    # ist der Work-Pfad absichtlich nur ein nicht angelegter Platzhalter.
    work_root = (
        legacy.resolve(strict=False)
        if legacy.exists() and not legacy.is_symlink()
        else (WORKSPACE_PATH / ".bibliothekar-ohne-bibliothek").resolve(strict=False)
    )
    return LibraryContext(
        library_id=MAIN_LIBRARY_ID,
        display_name="Nicht eingerichtet",
        database_path=DATABASE_FILE,
        workspace_root=WORKSPACE_PATH,
        work_root=work_root,
        archive_root=ARCHIVE_ROOT,
        is_main=True,
        settings={"bootstrap": True, "onboarding_required": True},
    )


MAIN_LIBRARY_CONTEXT = build_main_library_context()

# Bibliotheksdatenbanken können nach dem Prozessstart aus der Registry
# aufgelöst werden (z. B. sekundäre/Testbibliotheken). Der Request-Pfad darf
# deshalb niemals voraussetzen, dass nur die Startup-Schleife alle tatsächlich
# verwendeten DBs migriert hat.
_LIBRARY_SCHEMA_LOCK = Lock()
_LIBRARY_SCHEMA_READY: set[str] = set()
_CENTRAL_RECONCILE_LOCK = Lock()
_CENTRAL_RECONCILE_LAST = 0.0
_CENTRAL_RECONCILE_RESULT: dict[str, Any] = {}


def ensure_library_database_schema(context: LibraryContext) -> dict[str, Any] | None:
    database_path = context.database_path.expanduser().resolve(strict=False)
    key = str(database_path)
    if key in _LIBRARY_SCHEMA_READY:
        return None

    with _LIBRARY_SCHEMA_LOCK:
        if key in _LIBRARY_SCHEMA_READY:
            return None
        result = initialize_database(database_path)
        _LIBRARY_SCHEMA_READY.add(key)
        return result


def current_library_context() -> LibraryContext:
    current = get_current_library()
    if current is not None:
        return current
    # Direkte interne/testseitige Aufrufe ohne HTTP-Request bleiben mit den
    # aktuellen Main-Konstanten kompatibel. Im echten Request setzt die
    # Middleware immer den Registry-basierten LibraryContext.
    return build_main_library_context()


def current_database_file() -> Path:
    return current_library_context().database_path


def _resolve_registered_library_database(
    row: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Return the existing DB; safely repair only the canonical path if needed."""
    library_id = str(row.get("library_id") or "").strip()
    configured = Path(str(row.get("database_path") or "")).expanduser().resolve(
        strict=False
    )
    if configured.is_file():
        return configured, row

    canonical = (
        DATABASE_DIRECTORY
        / "libraries"
        / f"{library_id}.sqlite3"
    ).resolve(strict=False)

    if canonical != configured and canonical.is_file():
        try:
            identity = read_library_identity(canonical)
        except Exception as error:
            raise LibraryRegistryError(
                "Die gefundene Ersatz-Datenbank ist nicht lesbar: "
                + str(canonical)
            ) from error
        if identity == library_id:
            repaired = update_library_database_path(
                REGISTRY_DATABASE_FILE,
                library_id,
                canonical,
            )
            return canonical, repaired

    raise LibraryRegistryError(
        "Die registrierte SQLite-Datenbank der Bibliothek fehlt. "
        "Erwarteter Pfad: "
        + str(configured)
        + (
            " · Auch der sichere Standardpfad wurde nicht mit passender "
            "Bibliotheks-ID gefunden: " + str(canonical)
            if canonical != configured
            else ""
        )
    )


def _ensure_compatibility_link(link: Path, target: Path) -> None:
    resolved_target = target.resolve(strict=False)
    if link.is_symlink():
        try:
            if link.resolve(strict=False) == resolved_target:
                return
        except OSError:
            pass
        link.unlink(missing_ok=True)
    elif link.exists():
        raise RuntimeError(
            "Interner Bibliotheks-Kompatibilitätspfad ist bereits belegt: "
            + str(link)
        )
    link.symlink_to(resolved_target, target_is_directory=True)


def compatibility_workspace_root(context: LibraryContext) -> Path:
    # Alle Bibliotheken – auch die primäre – erhalten für Altcode intern eine
    # kleine Kompatibilitätsansicht. Dadurch hängt kein Arbeitsablauf mehr von
    # /workspace/Arbeitsbereich oder /workspace/Arbeitsbereiche/main ab.
    root = Path("/tmp/bibliothekar-library-workspaces") / re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        context.library_id,
    )
    root.mkdir(parents=True, exist_ok=True)
    _ensure_compatibility_link(
        root / WORK_DIRECTORY_NAME,
        context.work_root,
    )
    _ensure_compatibility_link(
        root / BACKUP_DIRECTORY_NAME,
        workspace_backup_root(context.workspace_root),
    )
    # The legacy alias remains for old internal paths; canonical operations
    # must also resolve the configured name, even after a Finder rename.
    configured_backup = load_storage_settings()["backup_directory_name"]
    if configured_backup != BACKUP_DIRECTORY_NAME:
        _ensure_compatibility_link(
            root / configured_backup,
            workspace_backup_root(context.workspace_root),
        )
    return root


def current_workspace_root() -> Path:
    current = get_current_library()
    if current is None:
        # Direkte interne/ältere Testaufrufe besitzen keinen Request-Kontext.
        # Sie behalten den bisherigen neutralen Workspace-Pfad; echte
        # Bibliotheksrequests laufen immer durch die Middleware und erhalten
        # die bibliotheksspezifische Kompatibilitätsansicht.
        return current_library_context().workspace_root
    return compatibility_workspace_root(current)


def current_work_root() -> Path:
    return current_library_context().work_root


def current_archive_root() -> Path:
    return current_library_context().archive_root


def _default_requested_library_id() -> str:
    rows = list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=True,
        registered_only=True,
    )
    if not rows:
        return MAIN_LIBRARY_ID
    main_row = next(
        (row for row in rows if str(row["library_id"]) == MAIN_LIBRARY_ID),
        None,
    )
    return str((main_row or rows[0])["library_id"])


def _requested_library_id(request: Request) -> str:
    fallback = _default_requested_library_id()
    return str(
        request.headers.get("X-Bibliothekar-Library")
        or request.query_params.get("library")
        or request.query_params.get("library_id")
        or fallback
    ).strip() or fallback


WORKER_STOP = Event()
CANCEL_WORKER_STOP = Event()
CANCEL_WORKER_WAKE = Event()
CANCEL_WORKER_THREAD: Thread | None = None
WORKER_THREAD: Thread | None = None
IMPORT_CANCEL_LOCK = Lock()
IMPORT_CANCEL_REQUESTS: set[str] = set()


def _request_import_cancel(job_id: str) -> None:
    with IMPORT_CANCEL_LOCK:
        IMPORT_CANCEL_REQUESTS.add(str(job_id))


def _import_cancel_requested(job_id: str) -> bool:
    with IMPORT_CANCEL_LOCK:
        return str(job_id) in IMPORT_CANCEL_REQUESTS


def _clear_import_cancel(job_id: str) -> None:
    with IMPORT_CANCEL_LOCK:
        IMPORT_CANCEL_REQUESTS.discard(str(job_id))


def _remove_cancelled_import_job(job_id: str) -> None:
    """Remove only DB/registry traces after the file pipeline rolled back safely."""
    remove_source_backup(
        REGISTRY_DATABASE_FILE,
        f"{MAIN_LIBRARY_ID}:{job_id}",
    )
    with database_connection(DATABASE_FILE) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM imported_source_files WHERE imported_job_id = ?",
            (job_id,),
        )
        connection.execute(
            "DELETE FROM jobs WHERE id = ?",
            (job_id,),
        )
        connection.commit()
    shutil.rmtree(LOG_PATH / "backups" / job_id, ignore_errors=True)
    try:
        _thumbnail_path(job_id).unlink()
    except FileNotFoundError:
        pass


def _discard_terminal_import_job(job_id: str) -> dict[str, int]:
    """Remove a failed/interrupted folder import and safe remnants.

    Restart recovery already turns running jobs into interrupted jobs. This
    cleanup is limited to terminal incomplete imports so it cannot race a live
    worker or erase a completed provenance record.
    """
    job = get_job(DATABASE_FILE, job_id)
    if job is None:
        raise ValueError("Import wurde nicht gefunden.")
    if (
        str(job.get("kind") or "") != "sd_import"
        or str(job.get("operation") or "") != "folder_import"
    ):
        raise ValueError("Nur Kamera-/Ordnerimporte können entfernt werden.")

    state = str(job.get("state") or "")
    if state not in {"failed", "interrupted"}:
        raise ValueError(
            "Nur fehlgeschlagene oder unterbrochene Importe können entfernt werden."
        )

    central_root = workspace_backup_root(WORKSPACE_PATH).resolve(strict=False)
    removed_files = 0

    with database_connection(DATABASE_FILE) as connection:
        rows = connection.execute(
            """
            SELECT
                current_root_kind,
                current_relative_path,
                size_bytes,
                COALESCE(NULLIF(sha256_current, ''), sha256_original) AS sha256
            FROM files
            WHERE job_id = ?
            ORDER BY id
            """,
            (job_id,),
        ).fetchall()

    for row in rows:
        if str(row["current_root_kind"] or "") != "shared_workspace":
            continue
        relative = str(row["current_relative_path"] or "").strip()
        if not relative:
            continue
        candidate = (central_root / relative).resolve(strict=False)
        try:
            candidate.relative_to(central_root)
        except ValueError as error:
            raise ValueError(
                "Unsicherer Dateipfad im unterbrochenen Import: " + relative
            ) from error
        if not candidate.exists():
            continue
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError(
                "Unerwarteter Eintrag im unterbrochenen Import: " + relative
            )
        expected_size = int(row["size_bytes"] or 0)
        expected_sha = str(row["sha256"] or "")
        if expected_size and candidate.stat().st_size != expected_size:
            raise ValueError(
                "Dateigröße stimmt beim Bereinigen nicht mehr: " + relative
            )
        if expected_sha and sha256_file(candidate) != expected_sha:
            raise ValueError(
                "SHA-256 stimmt beim Bereinigen nicht mehr: " + relative
            )
        candidate.unlink()
        removed_files += 1
        current = candidate.parent
        while current != central_root:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    incoming = (central_root / ".incoming" / job_id).resolve(strict=False)
    try:
        incoming.relative_to(central_root)
    except ValueError as error:
        raise ValueError("Unsicherer temporärer Importpfad.") from error
    shutil.rmtree(incoming, ignore_errors=True)
    try:
        incoming.parent.rmdir()
    except OSError:
        pass

    _clear_import_cancel(job_id)
    _remove_cancelled_import_job(job_id)
    return {"deleted_file_count": removed_files}


def _thumbnail_path(
    job_id: str,
    *,
    library_id: str = MAIN_LIBRARY_ID,
) -> Path:
    identity = (
        job_id
        if library_id == MAIN_LIBRARY_ID
        else f"{library_id}:{job_id}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return LOG_PATH / "thumbnails" / f"{digest}.jpg"


def ensure_job_thumbnail(
    job_id: str,
    *,
    library_context: LibraryContext | None = None,
) -> Path | None:
    context = library_context or current_library_context()
    target = _thumbnail_path(
        job_id,
        library_id=context.library_id,
    )
    if target.is_file():
        return target

    candidates = [
        row
        for row in list_job_files(context.database_path, job_id)
        if str(row.get("media_type") or "") == "jpeg"
        and row.get("current_relative_path")
    ]
    candidates.sort(
        key=lambda row: (
            str(row.get("selected_capture_time") or "9999-12-31T23:59:59"),
            str(row.get("current_relative_path") or ""),
        )
    )

    roots: list[Path] = []
    try:
        roots.append(
            workspace_backup_root(context.workspace_root).resolve(strict=False)
        )
    except WorkspaceLayoutError:
        # Isolated test/runtime contexts may expose only their library work root.
        pass
    work_root = context.work_root.resolve(strict=False)
    if work_root not in roots:
        roots.append(work_root)
    for row in candidates:
        relative = Path(str(row["current_relative_path"]))
        source = None
        for root in roots:
            candidate = (root / relative).resolve(strict=False)
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if candidate.is_file():
                source = candidate
                break
        if source is None:
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((320, 220))
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                image.save(
                    target,
                    format="JPEG",
                    quality=72,
                    optimize=True,
                    progressive=True,
                )
            return target
        except Exception:
            target.unlink(missing_ok=True)

    return None


app = FastAPI(
    title="Kamera-Automatisierung",
    version=APP_VERSION,
)


def _registered_library_rows() -> list[dict[str, Any]]:
    try:
        return list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        )
    except Exception:
        return []


def _onboarding_required() -> bool:
    return not _registered_library_rows()


def _library_onboarding_html() -> str:
    workspaces_root = str(
        storage_paths(WORKSPACE_PATH)["workspaces_root"]
    )
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekar · Bibliothek einrichten</title>
<style>
:root{{color-scheme:dark;--bg:#0c1115;--surface:#172027;--border:#34414a;--text:#f2f4f5;--muted:#aeb8bf;--accent:#58aaf2;--danger:#ff716f}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif}}
main{{width:min(760px,calc(100% - 32px));margin:7vh auto}} .card{{background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:28px}}
h1{{margin:0 0 8px;font-size:2rem}} p{{color:var(--muted);line-height:1.5}} label{{display:grid;gap:7px;margin:18px 0}}
input{{width:100%;padding:13px 14px;border-radius:11px;border:1px solid var(--border);background:#10171c;color:var(--text);font:inherit}}
button{{border:0;border-radius:11px;padding:13px 18px;background:var(--accent);color:white;font:inherit;font-weight:650;cursor:pointer}}
button:disabled{{opacity:.45;cursor:default}} #status{{white-space:pre-wrap;margin-top:15px;color:var(--muted)}} #status.error{{color:var(--danger)}} .hint{{font-size:.9rem}}
</style>
</head>
<body><main><section class="card">
<h1>Erste Bibliothek einrichten</h1>
<p>Bibliothekar besitzt noch keine Bibliothek. Lege jetzt Name, Arbeitsbereich und das in TrueNAS read-only gemountete Archiv fest. Es wird kein technischer <code>main</code>-Arbeitsordner angelegt.</p>
<label>Bibliotheksname<input id="name" value="" placeholder="z. B. Kamerabibliothek"></label>
<label>Arbeitsbereich · RW<input id="work" value="" placeholder="{workspaces_root}/Kamerabibliothek"></label>
<p class="hint">Leer lassen: Bibliothekar erzeugt unter <code>{workspaces_root}</code> automatisch einen Ordner aus dem Bibliotheksnamen.</p>
<label>Archiv · eigener RO-Mount<input id="archive" value="" placeholder="/main-library"></label>
<button id="create" type="button">Bibliothek prüfen und anlegen</button>
<div id="status" role="status"></div>
</section></main>
<script>
const nameEl=document.getElementById("name"),workEl=document.getElementById("work"),archiveEl=document.getElementById("archive"),statusEl=document.getElementById("status"),button=document.getElementById("create");
async function json(url,options={{}}){{const r=await fetch(url,options);let d={{}};try{{d=await r.json()}}catch{{}}if(!r.ok)throw new Error(typeof d.detail==="string"?d.detail:JSON.stringify(d.detail||d));return d}}
button.addEventListener("click",async()=>{{button.disabled=true;statusEl.className="";statusEl.textContent="Bibliothek wird geprüft …";try{{
const payload={{display_name:nameEl.value,work_root:workEl.value,archive_root:archiveEl.value}};
const managedName=String(payload.display_name||"Bibliothek").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,32)||"bibliothek";
const check=await json("/api/libraries/check",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{work_root:payload.work_root,archive_root:payload.archive_root,default_library_id:payload.work_root?"":managedName}})}});
if(!check.valid)throw new Error((check.errors||[]).join("\\n"));
await json("/api/libraries",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(payload)}});
statusEl.textContent="Bibliothek eingerichtet. Bibliothekar wird geöffnet …";location.assign("/");
}}catch(e){{statusEl.className="error";statusEl.textContent=e.message;button.disabled=false;}}}});
</script></body></html>"""


@app.middleware("http")
async def library_context_middleware(request: Request, call_next):
    if _onboarding_required():
        path = request.url.path
        allowed_api = (
            path.startswith("/api/libraries")
            or path == "/api/settings/storage-paths"
            or path == "/api/health"
        )
        if not allowed_api:
            if request.method == "GET" and not path.startswith("/api/"):
                return HTMLResponse(_library_onboarding_html(), status_code=200)
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Bibliothekar ist noch nicht eingerichtet. Bitte zuerst eine Bibliothek anlegen.",
                    "onboarding_required": True,
                },
            )
        # Die neutralen Setup-APIs brauchen noch keinen registrierten
        # Bibliothekskontext. Die globale DB ist beim Startup bereits migriert.
        token = set_current_library(MAIN_LIBRARY_CONTEXT)
        try:
            return await call_next(request)
        finally:
            reset_current_library(token)

    requested = _requested_library_id(request)
    try:
        context = resolve_library_context(
            REGISTRY_DATABASE_FILE,
            requested,
        )
    except Exception as error:
        if request.url.path.startswith("/api/libraries"):
            rows = _registered_library_rows()
            if not rows:
                context = MAIN_LIBRARY_CONTEXT
            else:
                context = resolve_library_context(
                    REGISTRY_DATABASE_FILE,
                    str(rows[0]["library_id"]),
                )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Bibliothekskontext ist nicht verfügbar: " + str(error),
                    "library_id": requested,
                },
            )

    try:
        ensure_library_database_schema(context)
    except Exception as error:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Bibliotheks-Datenbank konnte nicht auf den aktuellen "
                    "Schemastand gebracht werden: " + str(error)
                ),
                "library_id": context.library_id,
            },
        )

    token = set_current_library(context)
    try:
        response = await call_next(request)
    finally:
        reset_current_library(token)
    return response


DATABASE_INITIALIZATION: dict[str, Any] | None = None
DATABASE_INITIALIZATION_ERROR: str | None = None
WORKSPACE_LAYOUT_INITIALIZATION: dict[str, Any] | None = None
WORKSPACE_LAYOUT_ERROR: str | None = None
LIBRARY_REGISTRY_INITIALIZATION: dict[str, Any] | None = None
LIBRARY_REGISTRY_ERROR: str | None = None


def synchronize_global_central_stock() -> dict[str, Any]:
    rows = list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=False,
        registered_only=True,
    )
    database_paths = [
        Path(str(row["database_path"]))
        for row in rows
        if str(row.get("database_path") or "").strip()
    ]
    if DATABASE_FILE not in database_paths:
        database_paths.insert(0, DATABASE_FILE)
    return synchronize_central_stock_projections(
        database_paths,
        WORKSPACE_PATH,
    )


def reconcile_global_central_stock_state(
    *,
    force: bool = False,
) -> dict[str, Any]:
    global _CENTRAL_RECONCILE_LAST
    global _CENTRAL_RECONCILE_RESULT

    with _CENTRAL_RECONCILE_LOCK:
        now_monotonic = time.monotonic()
        if (
            not force
            and _CENTRAL_RECONCILE_LAST > 0
            and now_monotonic - _CENTRAL_RECONCILE_LAST < 20.0
        ):
            return dict(_CENTRAL_RECONCILE_RESULT)

        results: dict[str, Any] = {}
        changed = False
        rows = list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        )
        for row in rows:
            library_id = str(row.get("library_id") or "")
            database_path = Path(str(row.get("database_path") or ""))
            if not library_id or not database_path.is_file():
                continue
            try:
                context = resolve_library_context(
                    REGISTRY_DATABASE_FILE,
                    library_id,
                )
                ensure_library_database_schema(context)
                blocked = blocked_family_ids(
                    REGISTRY_DATABASE_FILE,
                    database_path=database_path,
                    library_id=library_id,
                )
                state = reconcile_central_free_stock(
                    database_path,
                    WORKSPACE_PATH,
                    library_id=library_id,
                    excluded_family_ids=blocked,
                )
                results[library_id] = state
                if int(state.get("deleted_file_count") or 0):
                    changed = True
                    backfill_library_claims(
                        REGISTRY_DATABASE_FILE,
                        database_path=database_path,
                        library_id=library_id,
                    )
            except Exception as error:
                results[library_id] = {
                    "ready": False,
                    "error": str(error),
                }

        _CENTRAL_RECONCILE_LAST = now_monotonic
        _CENTRAL_RECONCILE_RESULT = {
            "libraries": results,
            "changed": changed,
        }
        return dict(_CENTRAL_RECONCILE_RESULT)


def folder_import_display_label(
    job: dict[str, Any],
    organization: dict[str, Any],
) -> str:
    """Return the human-facing source name without changing the technical job ID."""
    trigger = str(job.get("trigger_type") or "")
    current = str(job.get("source_volume_label") or "").strip()
    if trigger not in {"approved_sd", "usb_key"}:
        return current or "Sicherungsordner"

    start_date = str(organization.get("capture_start_date") or "")
    end_date = str(organization.get("capture_end_date") or "")
    def display_date(value: str) -> str:
        return value.replace("-", ".") if len(value) == 10 else ""

    if trigger == "approved_sd":
        devices = list(organization.get("devices") or [])
        if len(devices) == 1:
            base = str(devices[0].get("name") or "SD-Karte")
        elif devices:
            base = "Mehrere Aufnahmegeräte"
        else:
            base = "SD-Karte"
    else:
        base = current or "Externes Laufwerk"

    if start_date and end_date:
        return f"{base} - {display_date(start_date)} - {display_date(end_date)}"
    return base


def process_claimed_job(
    job: dict[str, Any],
    *,
    library_context: LibraryContext | None = None,
) -> None:
    context = library_context or build_main_library_context()
    database_file = context.database_path
    workspace_path = context.workspace_root
    work_root = context.work_root
    pool_probe_path = context.workspace_root

    job_id = str(job["id"])
    operation = str(
        job.get(
            "operation",
            "legacy_simulation",
        )
    )
    is_import_operation = operation in {
        "folder_import",
        "metadata_multiple_import",
        "metadata_general_import",
    }

    try:
        settings = load_settings()
        storage = settings.get("storage", {})

        if operation == "metadata_fixture_analysis":
            source_value = job.get("source_path")

            if not source_value:
                raise RuntimeError(
                    "Metadatenauftrag besitzt keinen Quellpfad."
                )

            source = Path(str(source_value))

            if not source.is_dir():
                raise RuntimeError(
                    "Metadaten-Testbestand fehlt: " + str(source)
                )

            update_job_progress(
                database_file,
                job_id,
                state="backup_verified",
                stage="backup_verified",
                current=0,
                total=0,
                message=(
                    "Kontrollierter Testbestand wurde als unverändert bestätigt."
                ),
            )

            update_job_progress(
                database_file,
                job_id,
                state="analyzing_metadata",
                stage="metadata_analysis",
                current=0,
                total=0,
                message="Foto- und Videometadaten werden analysiert.",
            )

            analysis = analyze_tree(source)
            source_files = sorted(
                path
                for path in source.rglob("*")
                if path.is_file()
            )
            checksums = {
                path.relative_to(source).as_posix(): sha256_file(path)
                for path in source_files
            }
            store_metadata_analysis(
                database_file,
                job_id,
                analysis,
                checksums,
            )
            return

        lifecycle_backend = (
            "verification_receipt"
            if is_import_operation
            else "simulation_receipt"
        )

        known_total_files = 0

        def report_progress(
            state: str,
            stage: str,
            current: int,
            total: int,
            message: str,
        ) -> None:
            nonlocal known_total_files
            if total > 0 and stage in {
                "source_manifest",
                "copying",
                "backup_verification",
                "metadata_analysis",
                "organization_planning",
                "workspace_moving",
                "workspace_verification",
            }:
                known_total_files = max(
                    known_total_files,
                    int(total),
                )

            stage_ranges = {
                "starting": (0, 5),
                "source_manifest": (5, 120),
                "copying": (120, 430),
                "backup_verification": (430, 620),
                "snapshot_created": (620, 630),
                "metadata_analysis": (630, 850),
                "organization_planning": (850, 900),
                "workspace_moving": (900, 970),
                "workspace_verification": (970, 995),
                "completed": (1000, 1000),
            }
            lower, upper = stage_ranges.get(stage, (0, 995))
            if stage == "completed":
                overall_current = 1000
            elif total > 0:
                ratio = max(
                    0.0,
                    min(1.0, float(current) / float(total)),
                )
                overall_current = int(
                    round(lower + (upper - lower) * ratio)
                )
            else:
                overall_current = int(lower)

            update_job_progress(
                database_file,
                job_id,
                state=state,
                stage=stage,
                current=overall_current,
                total=1000,
                message=message,
            )

            lifecycle_status = {
                "starting": "copying",
                "copying": "copying",
                "backup_verification": "backup_verified",
                "snapshot_created": "snapshot_created",
                "metadata_analysis": "snapshot_created",
                "organization_planning": "snapshot_created",
                "workspace_moving": "workspace_moving",
                "workspace_verification": "workspace_verified",
                "completed": "completed",
            }.get(stage, "copying")

            upsert_backup_lifecycle(
                database_file,
                job_id=job_id,
                status=lifecycle_status,
                source_path=str(job.get("source_path") or ""),
                temporary_backup_path=str(
                    workspace_path
                    / BACKUP_DIRECTORY_NAME
                    / (".incoming" if is_import_operation else "")
                    / job_id
                    / "Original"
                ),
                workspace_path=str(
                    workspace_backup_root(workspace_path)
                    if is_import_operation
                    else work_root
                ),
                protocol_path=str(
                    LOG_PATH / "backups" / job_id
                ),
                snapshot_backend=lifecycle_backend,
                file_count=known_total_files or None,
                moved_file_count=(
                    current
                    if stage in {
                        "workspace_moving",
                        "workspace_verification",
                        "completed",
                    }
                    else None
                ),
                details={
                    "stage": stage,
                    "message": message,
                    "progress_current": current,
                    "progress_total": total,
                },
                completed=stage == "completed",
            )

        if is_import_operation:
            source_value = job.get("source_path")
            if not source_value:
                raise RuntimeError("Ordnerimport besitzt keinen Quellpfad.")
            source = Path(str(source_value))
            managed_multiple_import = operation == "metadata_multiple_import"
            managed_general_import = operation == "metadata_general_import"
            managed_metadata_import = managed_multiple_import or managed_general_import
            if managed_multiple_import:
                expected_multiple_root = metadata_area_paths(
                    area="multiple",
                    workspace_root=workspace_path,
                    library_id=context.library_id,
                    create=True,
                )["root"].resolve(strict=False)
                if source.resolve(strict=False) != expected_multiple_root:
                    raise RuntimeError(
                        "Mehrfachkorrektur-Import verweist auf einen unerwarteten Quellordner."
                    )
            if managed_general_import:
                metadata_root = storage_paths(workspace_path)["metadata_root"].resolve(strict=False)
                expected_stage_root = (metadata_root / ".general-import").resolve(strict=False)
                resolved_source = source.resolve(strict=False)
                try:
                    resolved_source.relative_to(expected_stage_root)
                except ValueError as error:
                    raise RuntimeError(
                        "Allgemein-Import verweist auf einen unerwarteten Staging-Ordner."
                    ) from error

            def persist_metadata(
                analysis: dict[str, Any],
                checksums: dict[str, str],
            ) -> None:
                store_metadata_analysis(
                    database_file,
                    job_id,
                    analysis,
                    checksums,
                    finalize_job=False,
                )

            def persist_paths(
                plan: list[dict[str, Any]],
            ) -> None:
                update_import_file_paths(
                    database_file,
                    job_id,
                    plan,
                    working_path=str(
                        workspace_backup_root(workspace_path)
                    ),
                )

            def persist_identity(signature: str, fingerprint: str) -> None:
                set_job_source_identity(
                    database_file,
                    job_id,
                    source_signature=signature,
                    source_fingerprint=fingerprint,
                )

            def admit_families(
                analysis: dict[str, Any],
                checksums: dict[str, str],
                sizes: dict[str, int],
            ) -> dict[str, Any]:
                inventory = register_analysis_inventory(
                    REGISTRY_DATABASE_FILE,
                    library_id=context.library_id,
                    job_id=job_id,
                    source_identity=str(
                        job.get("source_signature")
                        or job.get("source_device_id")
                        or source
                    ),
                    source_path=str(source),
                    analysis=analysis,
                    checksums=checksums,
                    sizes=sizes,
                )
                allowed, blocked = admitted_family_keys(
                    inventory,
                    context.library_id,
                )
                return {
                    "allowed_family_keys": sorted(allowed),
                    "blocked_families": blocked,
                }

            source_device_id = str(job.get("source_device_id") or "").strip()
            history_rows = (
                list_imported_source_files(database_file, source_device_id)
                if source_device_id
                else []
            )
            origin_rows = list_imported_media_origins(
                database_file,
                exclude_job_id=job_id,
            )
            imported_hashes = {
                (int(row["size_bytes"]), str(row["sha256"]))
                for row in origin_rows
            }
            imported_sha256 = {
                str(row["sha256"])
                for row in origin_rows
                if str(row.get("sha256") or "")
            }
            duplicate_origins: dict[tuple[int, str], dict[str, Any]] = {}
            duplicate_origins_by_sha: dict[str, dict[str, Any]] = {}
            for row in origin_rows:
                duplicate_origins.setdefault(
                    (int(row["size_bytes"]), str(row["sha256"])),
                    dict(row),
                )
                duplicate_origins_by_sha.setdefault(
                    str(row["sha256"]),
                    dict(row),
                )

            def persist_import_history(entries: list[dict[str, Any]]) -> None:
                if not source_device_id:
                    return
                store_imported_source_files(
                    database_file,
                    source_device_id=source_device_id,
                    job_id=job_id,
                    entries=entries,
                )

            def central_destination_directory(capture_value: str) -> Path | None:
                """Use the current physical timeline for newly imported free stock.

                If a capture already belongs to an applied/archived interval,
                it intentionally stays in the neutral day folder until the
                existing event-suggestion workflow is confirmed.
                """
                try:
                    with database_connection(database_file) as connection:
                        return Path(str(canonical_free_directory(
                            connection,
                            capture_value,
                            physical=True,
                        )))
                except FreeStockLayoutError:
                    return None

            result = run_folder_import_job(
                source=source,
                workspace=workspace_path,
                pool_probe_path=pool_probe_path,
                log_dir=LOG_PATH,
                processing_buffer_percent=int(
                    storage.get("processing_buffer_percent", 10)
                ),
                safety_reserve_gib=int(
                    storage.get("safety_reserve_gib", 20)
                ),
                job_id=job_id,
                progress_callback=report_progress,
                metadata_callback=persist_metadata,
                path_callback=persist_paths,
                identity_callback=persist_identity,
                imported_hashes=imported_hashes,
                duplicate_origins=duplicate_origins,
                imported_sha256=imported_sha256,
                duplicate_origins_by_sha=duplicate_origins_by_sha,
                import_history_callback=persist_import_history,
                family_admission_callback=admit_families,
                destination_directory_callback=central_destination_directory,
                work_root=work_root,
                central_stock=True,
                allow_workspace_source=managed_metadata_import,
                cancellation_callback=(
                    (lambda: _import_cancel_requested(job_id))
                    if operation == "folder_import"
                    else None
                ),
            )
            if operation == "folder_import" and _import_cancel_requested(job_id):
                cleanup_completed_folder_import(
                    result,
                    Path(str((result.get("organization") or {}).get("working_root") or workspace_backup_root(workspace_path))),
                )
                raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
            organization = result.get("organization", {})
            if str(job.get("trigger_type") or "") in {"approved_sd", "usb_key"}:
                set_job_source_volume_label(
                    database_file,
                    job_id,
                    folder_import_display_label(job, organization),
                )
            if managed_metadata_import:
                cleanup_removed = 0
                cleanup_errors: list[str] = []
                general_root = (
                    metadata_area_paths(
                        area="general",
                        workspace_root=workspace_path,
                        library_id=context.library_id,
                        create=True,
                    )["root"].resolve(strict=False)
                    if managed_general_import
                    else None
                )
                for entry in list(
                    (result.get("organization") or {}).get(
                        "imported_source_files"
                    ) or []
                ):
                    try:
                        relative = Path(str(entry.get("relative_path") or ""))
                        if (
                            relative.is_absolute()
                            or ".." in relative.parts
                            or not relative.parts
                        ):
                            raise RuntimeError("Unsicherer Quellpfad.")
                        candidates = [(source / relative).resolve(strict=False)]
                        if general_root is not None:
                            candidates.append((general_root / relative).resolve(strict=False))
                        for candidate in candidates:
                            base = source.resolve(strict=False) if candidate == candidates[0] else general_root
                            candidate.relative_to(base)
                            if not candidate.is_file() or candidate.is_symlink():
                                continue
                            if (
                                int(candidate.stat().st_size)
                                != int(entry.get("size_bytes") or 0)
                                or sha256_file(candidate)
                                != str(entry.get("sha256") or "")
                            ):
                                raise RuntimeError(
                                    "Quelldatei stimmt nach der Übernahme nicht mehr mit dem verifizierten Import überein."
                                )
                            candidate.unlink()
                            cleanup_removed += 1
                    except Exception as cleanup_error:
                        cleanup_errors.append(
                            str(entry.get("relative_path") or "")
                            + ": "
                            + str(cleanup_error)
                        )

                # Leere Unterordner entfernen. Der Mehrfachkorrektur-Stamm
                # bleibt bestehen; ein Allgemein-Stagingordner wird komplett
                # entfernt, sobald er leer ist.
                for directory in sorted(
                    (
                        path
                        for path in source.rglob("*")
                        if path.is_dir() and not path.is_symlink()
                    ),
                    key=lambda path: len(path.parts),
                    reverse=True,
                ):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
                if managed_general_import:
                    try:
                        source.rmdir()
                    except OSError:
                        pass
                result["source_cleanup"] = {
                    "removed_file_count": cleanup_removed,
                    "errors": cleanup_errors,
                }
                completion_prefix = (
                    "Mehrfachkorrektur wurde in den Tagesbestand übernommen."
                    if managed_multiple_import
                    else "Ausgewählte Allgemein-Dateien wurden in den Tagesbestand übernommen."
                )
            else:
                completion_prefix = "Ordnerimport erfolgreich abgeschlossen."
        else:
            result = run_simulated_job(
                workspace=workspace_path,
                pool_probe_path=pool_probe_path,
                log_dir=LOG_PATH,
                processing_buffer_percent=int(
                    storage.get("processing_buffer_percent", 10)
                ),
                safety_reserve_gib=int(
                    storage.get("safety_reserve_gib", 20)
                ),
                job_id=job_id,
                progress_callback=report_progress,
                work_root=work_root,
            )
            completion_prefix = "Simulation erfolgreich abgeschlossen."

        organization = result.get("organization", {})
        snapshot = result.get("snapshot", {})
        outputs = result.get("outputs", {})

        upsert_backup_lifecycle(
            database_file,
            job_id=job_id,
            status="completed",
            source_path=str(job.get("source_path") or ""),
            temporary_backup_path=str(
                workspace_path
                / BACKUP_DIRECTORY_NAME
                / (".incoming" if is_import_operation else "")
                / job_id
                / "Original"
            ),
            workspace_path=str(
                organization.get(
                    "working_root",
                    work_root,
                )
            ),
            protocol_path=str(outputs.get("protocol") or ""),
            snapshot_backend=str(
                snapshot.get("backend") or lifecycle_backend
            ),
            snapshot_reference=str(snapshot.get("reference") or ""),
            file_count=int(organization.get("file_count", 0)),
            total_size_bytes=int(
                result.get("source", {}).get("size_bytes", 0)
            ),
            moved_file_count=int(organization.get("file_count", 0)),
            temporary_backup_removed=bool(
                result.get("temporary_backup_removed")
            ),
            details=result,
            completed=True,
        )

        complete_job(
            database_file,
            job_id,
            stage="organized_verified",
            result=result,
            message=(
                completion_prefix
                + " "
                + str(organization.get("file_count", 0))
                + " Mediendateien wurden verifiziert."
            ),
        )

        if is_import_operation:
            if database_file.resolve(strict=False) != DATABASE_FILE.resolve(strict=False):
                raise RuntimeError(
                    "Globaler Kameraimport wurde unerwartet außerhalb der Main-Datenbank verarbeitet."
                )

            projection_results: dict[str, dict[str, int]] = {}
            for library in list_active_library_contexts(REGISTRY_DATABASE_FILE):
                if library.library_id == MAIN_LIBRARY_ID:
                    continue
                projected = project_import_job(
                    DATABASE_FILE,
                    library.database_path,
                    job_id,
                )
                backfill = backfill_library_inventory(
                    REGISTRY_DATABASE_FILE,
                    database_path=library.database_path,
                    library_id=library.library_id,
                    claim_all_owned=False,
                )
                projection_results[library.library_id] = {
                    **projected,
                    "inventory_families": int(backfill.get("family_count") or 0),
                }

            try:
                ensure_job_thumbnail(
                    job_id,
                    library_context=MAIN_LIBRARY_CONTEXT,
                )
            except Exception as thumbnail_error:
                print(
                    "Vorschaubild konnte nicht erstellt werden:",
                    thumbnail_error,
                    flush=True,
                )

            if projection_results:
                print(
                    "Globaler Import wurde in Bibliotheken projiziert:",
                    projection_results,
                    flush=True,
                )

    except ImportCancelled:
        try:
            _remove_cancelled_import_job(job_id)
        except Exception as cleanup_error:
            print(
                "Abgebrochener Import konnte nicht vollständig bereinigt werden:",
                cleanup_error,
                flush=True,
            )
            try:
                fail_job(
                    database_file,
                    job_id,
                    error_message=(
                        "Import wurde abgebrochen; Bereinigung fehlgeschlagen: "
                        + str(cleanup_error)
                    ),
                )
            except Exception:
                pass
        finally:
            _clear_import_cancel(job_id)
        return
    except Exception as error:
        _clear_import_cancel(job_id)
        try:
            if operation != "metadata_fixture_analysis":
                upsert_backup_lifecycle(
                    database_file,
                    job_id=job_id,
                    status="failed",
                    source_path=str(job.get("source_path") or ""),
                    temporary_backup_path=str(
                        workspace_path
                        / BACKUP_DIRECTORY_NAME
                        / (".incoming" if is_import_operation else "")
                        / job_id
                        / "Original"
                    ),
                    workspace_path=str(
                        workspace_backup_root(workspace_path)
                        if is_import_operation
                        else work_root
                    ),
                    protocol_path=str(
                        LOG_PATH / "backups" / job_id
                    ),
                    snapshot_backend=(
                        "verification_receipt"
                        if is_import_operation
                        else "simulation_receipt"
                    ),
                    error_message=str(error),
                    details={"error": str(error)},
                )

            fail_job(
                database_file,
                job_id,
                error_message=str(error),
            )
        except Exception as database_error:
            print(
                "Auftragsfehler konnte nicht in SQLite gespeichert werden:",
                database_error,
                flush=True,
            )


def ordered_worker_contexts(
    contexts: list[LibraryContext],
    last_library_id: str | None,
) -> list[LibraryContext]:
    if len(contexts) < 2 or not last_library_id:
        return list(contexts)

    for index, context in enumerate(contexts):
        if context.library_id != last_library_id:
            continue
        start = (index + 1) % len(contexts)
        return contexts[start:] + contexts[:start]

    return list(contexts)


def claim_next_library_job(
    contexts: list[LibraryContext],
) -> tuple[LibraryContext, dict[str, Any]] | None:
    for context in contexts:
        if not context.database_path.is_file():
            print(
                "Bibliotheks-Datenbank fehlt; Queue wird übersprungen "
                f"({context.library_id}): {context.database_path}",
                flush=True,
            )
            continue

        try:
            job = claim_next_job(
                context.database_path
            )
        except Exception as error:
            print(
                "Bibliotheks-Queue konnte nicht gelesen werden "
                f"({context.library_id}): {error}",
                flush=True,
            )
            continue

        if job is not None:
            return context, job

    return None


def process_background_mutation_cancel() -> bool:
    """Bearbeite einen dauerhaften Verwerfauftrag unabhängig vom HTTP-Request."""
    from app.event_mutation import cancel_mutation
    for context in list_active_library_contexts(REGISTRY_DATABASE_FILE):
        ensure_library_database_schema(context)
        row = cancel_queue.claim_next(context.database_path)
        if row is None:
            continue
        try:
            with database_connection(context.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                if not cancel_queue.mutation_already_cancelled(
                    connection, row["mutation_id"], row["job_id"]
                ):
                    cancel_mutation(
                        connection, row["mutation_id"], row["job_id"],
                        workspace_path=context.workspace_root,
                    )
                connection.commit()

            # Auch nach einem Neustart zwischen SQLite-COMMIT und dem
            # zentralen Claims-Abgleich ist dieser Schritt wiederholbar.
            backfill_library_claims(
                REGISTRY_DATABASE_FILE,
                database_path=context.database_path,
                library_id=context.library_id,
            )
            synchronize_global_central_stock()
            cancel_queue.finish(context.database_path, row["id"])
        except Exception as error:
            cancel_queue.finish(
                context.database_path, row["id"], error=str(error)
            )
            print("Hintergrund-Verwerfen fehlgeschlagen:", error, flush=True)
        return True
    return False


def cancel_worker_loop() -> None:
    """Unabhängiger, ereignisgesteuerter Worker; keine Leerlauf-DB-Abfragen."""
    while not CANCEL_WORKER_STOP.is_set():
        try:
            while not CANCEL_WORKER_STOP.is_set() and process_background_mutation_cancel():
                pass
        except Exception as error:
            print("Hintergrund-Verwerfworker:", error, flush=True)
        CANCEL_WORKER_WAKE.wait(5.0)
        CANCEL_WORKER_WAKE.clear()


def start_cancel_worker() -> None:
    global CANCEL_WORKER_THREAD
    CANCEL_WORKER_STOP.clear()
    if CANCEL_WORKER_THREAD is None or not CANCEL_WORKER_THREAD.is_alive():
        CANCEL_WORKER_THREAD = Thread(
            target=cancel_worker_loop,
            name="bibliothekar-mutation-cancel-worker",
            daemon=True,
        )
        CANCEL_WORKER_THREAD.start()
    CANCEL_WORKER_WAKE.set()


def worker_loop() -> None:
    last_library_id: str | None = None

    while not WORKER_STOP.is_set():
        try:
            # Kamera-/Ordnerimporte sind seit 0.31.1 globaler Bestand und
            # liegen ausschließlich in der Main-Datenbank. Sie werden deshalb
            # direkt aus dieser Queue übernommen und nicht über die
            # Bibliotheks-Registry wiederentdeckt. Ein fehlerhafter oder
            # vorübergehend unvollständiger Sekundärkontext kann den globalen
            # Import damit nicht mehr dauerhaft auf "queued" halten.
            global_import = claim_next_job(
                DATABASE_FILE,
                operation="folder_import",
            )
            if global_import is None:
                global_import = claim_next_job(
                    DATABASE_FILE,
                    operation="metadata_multiple_import",
                )
            if global_import is None:
                global_import = claim_next_job(
                    DATABASE_FILE,
                    operation="metadata_general_import",
                )
            if global_import is not None:
                claimed = (MAIN_LIBRARY_CONTEXT, global_import)
            else:
                contexts = ordered_worker_contexts(
                    list_active_library_contexts(
                        REGISTRY_DATABASE_FILE
                    ),
                    last_library_id,
                )
                claimed = claim_next_library_job(contexts)

            if claimed is None:
                WORKER_STOP.wait(1.0)
                continue

            context, job = claimed
            process_claimed_job(
                job,
                library_context=context,
            )
            last_library_id = context.library_id

        except Exception as error:
            print(
                "Fehler im bibliotheksbewussten Hintergrund-Worker:",
                error,
                flush=True,
            )
            WORKER_STOP.wait(2.0)


@app.on_event("startup")
def startup_database() -> None:
    global DATABASE_INITIALIZATION
    global DATABASE_INITIALIZATION_ERROR
    global WORKSPACE_LAYOUT_INITIALIZATION
    global WORKSPACE_LAYOUT_ERROR
    global LIBRARY_REGISTRY_INITIALIZATION
    global LIBRARY_REGISTRY_ERROR
    global MAIN_LIBRARY_CONTEXT
    global WORKER_THREAD

    try:
        DATABASE_INITIALIZATION = initialize_database(
            DATABASE_FILE
        )
        _LIBRARY_SCHEMA_READY.add(
            str(DATABASE_FILE.expanduser().resolve(strict=False))
        )

        LIBRARY_REGISTRY_INITIALIZATION = initialize_library_registry(
            REGISTRY_DATABASE_FILE
        )
        existing_main = get_library(
            REGISTRY_DATABASE_FILE,
            MAIN_LIBRARY_ID,
            active_only=False,
        )
        registered_libraries = list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        )
        workspace_layout = ensure_workspace_layout(
            WORKSPACE_PATH,
            configured_main_work_root=(
                Path(str(existing_main["work_root"]))
                if existing_main is not None
                else None
            ),
            create_default_main=False,
        )

        # 0.32.9: Eine frische Installation besitzt absichtlich noch keine
        # Bibliothek. Nur die neutralen Workspace-Stämme werden vorbereitet;
        # die erste Bibliothek (Name, Arbeitsbereich, Archiv) legt der Nutzer
        # über das Onboarding selbst an.
        if not registered_libraries:
            WORKSPACE_LAYOUT_INITIALIZATION = {
                **workspace_layout,
                "onboarding_required": True,
            }
            LIBRARY_REGISTRY_INITIALIZATION = {
                **(LIBRARY_REGISTRY_INITIALIZATION or {}),
                "onboarding_required": True,
            }
            WORKSPACE_LAYOUT_ERROR = None
            LIBRARY_REGISTRY_ERROR = None
            DATABASE_INITIALIZATION_ERROR = None

            WORKER_STOP.clear()
            if WORKER_THREAD is None or not WORKER_THREAD.is_alive():
                WORKER_THREAD = Thread(
                    target=worker_loop,
                    name="kamera-job-worker",
                    daemon=True,
                )
                WORKER_THREAD.start()
            start_cancel_worker()
            return

        if existing_main is not None:
            MAIN_LIBRARY_CONTEXT = resolve_library_context(
                REGISTRY_DATABASE_FILE,
                MAIN_LIBRARY_ID,
            )
            legacy_layout = migrate_legacy_applied_files(
                DATABASE_FILE,
                WORKSPACE_PATH,
            )
            global_stock_migration = migrate_main_free_stock_to_central(
                DATABASE_FILE,
                WORKSPACE_PATH,
                main_work_root=MAIN_LIBRARY_CONTEXT.work_root,
            )
            main_inventory = backfill_library_inventory(
                REGISTRY_DATABASE_FILE,
                database_path=DATABASE_FILE,
                library_id=MAIN_LIBRARY_ID,
                claim_all_owned=False,
            )
            main_claims = backfill_library_claims(
                REGISTRY_DATABASE_FILE,
                database_path=DATABASE_FILE,
                library_id=MAIN_LIBRARY_ID,
            )
        else:
            # Eine Registry ohne Primärbibliothek ist zulässig. Insbesondere
            # wird beim Update niemals wieder eine "main"-Bibliothek oder ein
            # "main"-Arbeitsordner erzeugt.
            MAIN_LIBRARY_CONTEXT = build_main_library_context()
            legacy_layout = {}
            global_stock_migration = {
                "skipped": True,
                "reason": "Keine registrierte Primärbibliothek.",
            }
            main_inventory = None
            main_claims = None

        WORKSPACE_LAYOUT_INITIALIZATION = {
            **workspace_layout,
            **legacy_layout,
            "global_stock_migration": global_stock_migration,
        }
        WORKSPACE_LAYOUT_ERROR = None

        secondary_sync: dict[str, dict[str, Any]] = {}
        for library_row in list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        ):
            library_id = str(library_row["library_id"])
            if library_id == MAIN_LIBRARY_ID:
                continue
            library_database = Path(str(library_row["database_path"]))
            secondary_context = LibraryContext(
                library_id=library_id,
                display_name=str(library_row["display_name"]),
                database_path=library_database,
                workspace_root=Path(str(library_row["workspace_root"])),
                work_root=Path(str(library_row["work_root"])),
                archive_root=Path(str(library_row["archive_root"])),
                is_main=bool(library_row["is_main"]),
                settings=dict(library_row.get("settings") or {}),
            )
            ensure_library_database_schema(secondary_context)
            ensure_library_identity(library_database, library_id)
            projection = project_all_imports(
                DATABASE_FILE,
                library_database,
            )
            inventory = backfill_library_inventory(
                REGISTRY_DATABASE_FILE,
                database_path=library_database,
                library_id=library_id,
                claim_all_owned=False,
            )
            claims = backfill_library_claims(
                REGISTRY_DATABASE_FILE,
                database_path=library_database,
                library_id=library_id,
            )
            secondary_sync[library_id] = {
                "projection": projection,
                "inventory": inventory,
                "claims": claims,
            }

        central_projection_sync = synchronize_global_central_stock()

        LIBRARY_REGISTRY_INITIALIZATION = {
            **(LIBRARY_REGISTRY_INITIALIZATION or {}),
            "main_inventory": main_inventory,
            "main_claims": main_claims,
            "secondary_sync": secondary_sync,
            "central_projection_sync": central_projection_sync,
        }
        LIBRARY_REGISTRY_ERROR = None

        recovered_protocols = recover_cross_device_protocol_failures(
            WORKSPACE_PATH,
            LOG_PATH,
        )

        for recovered in recovered_protocols:
            recovered_job_id = str(recovered["job_id"])
            recovered_job = get_job(DATABASE_FILE, recovered_job_id)
            source = recovered.get("source", {})
            organization = recovered.get("organization", {})
            snapshot = recovered.get("snapshot", {})
            outputs = recovered.get("outputs", {})

            upsert_backup_lifecycle(
                DATABASE_FILE,
                job_id=recovered_job_id,
                status="completed",
                source_path=str((recovered_job or {}).get("source_path") or ""),
                temporary_backup_path=str(
                    workspace_backup_root(WORKSPACE_PATH)
                    / recovered_job_id
                    / "Original"
                ),
                workspace_path=str(
                    organization.get("working_root")
                    or (
                        MAIN_LIBRARY_CONTEXT.work_root
                        if existing_main is not None
                        else WORKSPACE_PATH
                    )
                ),
                protocol_path=str(outputs.get("protocol") or ""),
                snapshot_backend=str(
                    snapshot.get("backend") or "simulation_receipt"
                ),
                snapshot_reference=str(snapshot.get("reference") or ""),
                file_count=int(source.get("file_count") or 0),
                total_size_bytes=int(source.get("size_bytes") or 0),
                moved_file_count=int(organization.get("file_count") or 0),
                temporary_backup_removed=True,
                details=recovered,
                error_message="",
                completed=True,
            )
            recover_failed_job_as_completed(
                DATABASE_FILE,
                recovered_job_id,
                stage="organized_verified",
                result=recovered,
                message=(
                    "Simulation erfolgreich wiederhergestellt. "
                    f"{organization.get('file_count', 0)} Dateien wurden verifiziert."
                ),
            )
            print(
                f"EXDEV-Protokollfehler für {recovered_job_id} "
                "wurde sicher wiederhergestellt.",
                flush=True,
            )

        interrupted = mark_running_jobs_interrupted(
            DATABASE_FILE
        )

        if interrupted:
            print(
                f"{interrupted} unterbrochene Aufträge "
                "wurden markiert.",
                flush=True,
            )

        interrupted_sort_runs = (
            mark_incomplete_sort_runs_interrupted(
                DATABASE_FILE
            )
        )

        if interrupted_sort_runs:
            print(
                f"{interrupted_sort_runs} unterbrochene Sortierläufe "
                "wurden erkannt.",
                flush=True,
            )

        sort_recovery = recover_interrupted_sort_runs(DATABASE_FILE)
        if sort_recovery["recovered"]:
            print(
                f"{sort_recovery['recovered']} unterbrochene Sortierläufe "
                "wurden anhand des Journals sicher zurückgesetzt.",
                flush=True,
            )
        if sort_recovery["blocked"]:
            print(
                f"{sort_recovery['blocked']} unterbrochene Sortierläufe "
                "bleiben wegen eines uneindeutigen Dateizustands gesperrt.",
                flush=True,
            )

        recovered_terminal_jobs = (
            repair_interrupted_jobs_from_terminal_evidence(
                DATABASE_FILE
            )
        )

        if recovered_terminal_jobs:
            print(
                f"{recovered_terminal_jobs} veraltete unterbrochene "
                "Auftragszustände wurden anhand abgeschlossener "
                "Folgevorgänge wiederhergestellt.",
                flush=True,
            )

        # 0.28.0: Rein datenbankseitige 0.27-planned_extension-Ereignisse
        # dürfen erst nach der Sortierlauf-Wiederherstellung vereinheitlicht
        # werden. Sobald physische Evidenz existiert, bleibt der Altbestand
        # unangetastet und wird als Wartungsfall behandelt.
        from app.legacy_multi_backup import normalize_unapplied_legacy_extensions
        legacy_normalization = normalize_unapplied_legacy_extensions(
            DATABASE_FILE
        )
        if legacy_normalization["merged_count"]:
            print(
                f"{legacy_normalization['merged_count']} rein geplante "
                "Legacy-Mehrsicherungs-Erweiterungen wurden sicher "
                "vereinheitlicht.",
                flush=True,
            )

        DATABASE_INITIALIZATION_ERROR = None

        # Unterbrochene Aufträge vor dem Workerstart zur Wiederaufnahme freigeben.
        for context in list_active_library_contexts(REGISTRY_DATABASE_FILE):
            ensure_library_database_schema(context)
            cancel_queue.recover_interrupted(context.database_path)

        WORKER_STOP.clear()

        if (
            WORKER_THREAD is None
            or not WORKER_THREAD.is_alive()
        ):
            WORKER_THREAD = Thread(
                target=worker_loop,
                name="kamera-job-worker",
                daemon=True,
            )
            WORKER_THREAD.start()

        start_cancel_worker()

        # 0.41.3: Persistente Mehrfach-Anwendungen und Sortierjournale
        # werden nach einem Neustart auch in sekundären Bibliotheken
        # wiederentdeckt.
        try:
            for context in list_active_library_contexts(
                REGISTRY_DATABASE_FILE
            ):
                ensure_library_database_schema(
                    context
                )
                if (
                    context.database_path.resolve(strict=False)
                    != DATABASE_FILE.resolve(strict=False)
                ):
                    mark_incomplete_sort_runs_interrupted(
                        context.database_path
                    )
                    recover_interrupted_sort_runs(
                        context.database_path
                    )
                for batch_id in recover_operation_batches(
                    context.database_path
                ):
                    Thread(
                        target=_apply_batch_thread_target,
                        args=(batch_id, context),
                        name=f"kamera-batch-recovery-{batch_id}",
                        daemon=True,
                    ).start()
        except Exception as batch_error:
            print(
                "Persistente Server-Batches konnten nicht vollständig "
                f"wiederaufgenommen werden: {batch_error}",
                flush=True,
            )

    except Exception as error:
        DATABASE_INITIALIZATION = None
        DATABASE_INITIALIZATION_ERROR = str(error)
        WORKSPACE_LAYOUT_INITIALIZATION = None
        WORKSPACE_LAYOUT_ERROR = str(error)
        LIBRARY_REGISTRY_INITIALIZATION = None
        LIBRARY_REGISTRY_ERROR = str(error)


@app.on_event("shutdown")
def shutdown_worker() -> None:
    WORKER_STOP.set()
    CANCEL_WORKER_STOP.set()
    CANCEL_WORKER_WAKE.set()
    if CANCEL_WORKER_THREAD is not None and CANCEL_WORKER_THREAD.is_alive():
        CANCEL_WORKER_THREAD.join(timeout=5)

    if (
        WORKER_THREAD is not None
        and WORKER_THREAD.is_alive()
    ):
        WORKER_THREAD.join(
            timeout=5
        )


def load_settings() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(
            "Die Konfiguration muss ein JSON-Objekt sein."
        )

    return data


def _event_payload_with_folder_layout(
    payload: dict[str, Any],
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    result = dict(payload)
    naming: dict[str, Any]
    with database_connection(current_database_file()) as connection:
        if event_id:
            state = ensure_event_layout_snapshot(
                connection,
                event_id,
                now=datetime.now(timezone.utc).isoformat(),
            )
            event_row = connection.execute(
                """SELECT folder_naming_json,folder_name,event_kind,name
                   FROM events WHERE id=?""",
                (event_id,),
            ).fetchone()
            snapshot: dict[str, Any] = {}
            if event_row is not None:
                try:
                    snapshot = json.loads(
                        str(event_row["folder_naming_json"] or "{}")
                    )
                except (TypeError, ValueError):
                    snapshot = {}
            if snapshot:
                naming = dict(snapshot)
                if (
                    str(event_row["event_kind"] or "event") == "event"
                    and not any(
                        key in naming
                        for key in (
                            "subevent_prefix_mode",
                            "subevent_date_mode",
                            "subevent_include_year",
                            "subevent_include_time",
                        )
                    )
                ):
                    # Existing 0.33–0.42 snapshots predate configurable
                    # Unterereignis-Präfixe. Keep their physical child-folder
                    # convention unless the event was explicitly created with
                    # the new 0.43 policy.
                    naming["subevent_prefix_mode"] = "legacy_datetime_range"
                    naming["subevent_prefix_enabled"] = True
            elif event_row is not None:
                # 0.32.x events keep the pre-0.33 naming convention instead
                # of adopting the current library template. Intentional later
                # edits may still rename/re-date the folder exactly as before.
                naming = legacy_naming_for_existing_event(
                    event_kind=event_row["event_kind"],
                    folder_name=event_row["folder_name"],
                    event_name=event_row["name"],
                )
            else:
                naming = naming_from_library_settings(
                    current_library_context().settings
                )
        else:
            state = get_global_event_folder_layout(connection)
            naming = naming_from_library_settings(
                current_library_context().settings
            )
    result.setdefault("folder_layout", {
        "structure_enabled": bool(state["structure_enabled"]),
        "input_path": str(state["input_path"]),
        "layout": state["layout"],
    })
    result.setdefault("folder_naming", naming)
    result.setdefault("create_subfolders", bool(state["structure_enabled"]))
    return result

def _naming_snapshot_from_event_context(context: dict[str, Any]) -> dict[str, Any]:
    event = dict(context.get("event") or {})
    snapshot = event.get("folder_naming")
    if isinstance(snapshot, dict) and snapshot:
        result = dict(snapshot)
        if (
            str(event.get("event_kind") or "event") == "event"
            and not any(
                key in result
                for key in (
                    "subevent_prefix_mode",
                    "subevent_date_mode",
                    "subevent_include_year",
                    "subevent_include_time",
                )
            )
        ):
            result["subevent_prefix_mode"] = "legacy_datetime_range"
            result["subevent_prefix_enabled"] = True
        return result
    return legacy_naming_for_existing_event(
        event_kind=event.get("event_kind"),
        folder_name=event.get("folder_name"),
        event_name=event.get("name"),
    )


def _canonical_membership_preflight(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], JSONResponse | None]:
    """Expand a visible UI selection to the complete active time membership."""
    with database_connection(current_database_file()) as connection:
        membership = resolve_payload_membership(connection, payload)
    expanded = {
        **payload,
        "selected_family_ids": membership["canonical_family_ids"],
    }
    if (
        membership.get("hidden_additional_family_count", membership["additional_family_count"])
        and not bool(payload.get("confirm_cross_backup_membership"))
    ):
        response = JSONResponse(
            status_code=409,
            content={
                "detail": (
                    "Weitere Aufnahmen aus einer ausgeblendeten aktiven Sicherung "
                    "liegen im gewählten Zeitraum und gehören deshalb zum selben Ereignis."
                ),
                "confirmation_required": "cross_backup_membership",
                "membership": membership,
            },
        )
        return expanded, membership, response
    return expanded, membership, None


def _available_families_for_event_payload(
    job_id: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve the explicit UI selection across backup provenance."""
    requested = sorted({
        int(value)
        for value in (payload.get("selected_family_ids") or [])
        if int(value) > 0
    })
    blocked = blocked_family_ids(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        job_id=job_id,
    )

    def with_released_assets(
        families: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ids = sorted({
            int(family["family_id"])
            for family in families
            if family.get("family_id") is not None
        })
        if not ids:
            return families
        placeholders = ",".join("?" for _ in ids)
        with database_connection(current_database_file()) as connection:
            asset_rows = connection.execute(
                f"""SELECT family_id,COUNT(*) AS file_count,
                           COALESCE(SUM(size_bytes),0) AS total_size_bytes,
                           GROUP_CONCAT(DISTINCT asset_kind) AS asset_kinds
                    FROM released_archive_assets
                    WHERE family_id IN ({placeholders})
                    GROUP BY family_id""",
                tuple(ids),
            ).fetchall()
        stats = {
            int(row["family_id"]): dict(row)
            for row in asset_rows
        }
        result: list[dict[str, Any]] = []
        for family in families:
            item = dict(family)
            extra = stats.get(int(item["family_id"]))
            if extra is not None:
                item["file_count"] = (
                    int(item.get("file_count") or 0)
                    + int(extra.get("file_count") or 0)
                )
                item["total_size_bytes"] = (
                    int(item.get("total_size_bytes") or 0)
                    + int(extra.get("total_size_bytes") or 0)
                )
                item["released_archive_asset_count"] = int(
                    extra.get("file_count") or 0
                )
                item["released_archive_asset_kinds"] = sorted({
                    value
                    for value in str(extra.get("asset_kinds") or "").split(",")
                    if value
                })
            result.append(item)
        return result

    if not requested:
        return with_released_assets(
            list_job_available_families(
                current_database_file(),
                job_id,
                excluded_family_ids=blocked,
            )
        )

    placeholders = ",".join("?" for _ in requested)
    blocked_sorted = sorted(blocked)
    blocked_sql = ""
    blocked_params: list[int] = []
    if blocked_sorted:
        blocked_placeholders = ",".join("?" for _ in blocked_sorted)
        blocked_sql = f" AND ff.id NOT IN ({blocked_placeholders})"
        blocked_params = blocked_sorted

    with database_connection(current_database_file()) as connection:
        rows = connection.execute(
            f"""SELECT ff.id AS family_id,ff.job_id,ff.family_key,ff.original_stem,
                       ff.selected_capture_time,ff.capture_time_confidence,
                       COUNT(f.id) AS file_count,
                       COALESCE(SUM(f.size_bytes),0) AS total_size_bytes,
                       COALESCE(SUM(CASE WHEN f.review_status='required' THEN 1 ELSE 0 END),0)
                         AS review_required_count
                FROM file_families ff
                LEFT JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
                WHERE ff.id IN ({placeholders})
                  AND ff.selected_capture_time IS NOT NULL
                  {blocked_sql}
                  AND NOT EXISTS (
                    SELECT 1 FROM event_assignments ea
                    JOIN events e ON e.id=ea.event_id
                    WHERE ea.family_id=ff.id
                      AND e.status IN ('draft','planned','applied','archived')
                  )
                GROUP BY ff.id
                ORDER BY ff.selected_capture_time,ff.id""",
            (*requested, *blocked_params),
        ).fetchall()

    if len(rows) != len(requested):
        raise ValueError(
            "Die Auswahl ist nicht mehr aktuell. Mindestens eine Dateifamilie "
            "ist nicht mehr frei oder gehört inzwischen zu einer anderen Bibliothek."
        )

    return with_released_assets([
        {
            **dict(row),
            "day_key": str(row["selected_capture_time"] or "")[:10] or None,
            "has_date": row["selected_capture_time"] is not None,
        }
        for row in rows
    ])

def _storage_settings_state() -> dict[str, Any]:
    names = load_storage_settings()
    paths = storage_paths(WORKSPACE_PATH)
    libraries = []
    for row in list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=False,
        registered_only=True,
    ):
        work = Path(str(row["work_root"])).resolve(strict=False)
        hardlink = (
            _same_filesystem(paths["backup_root"], work)
            if paths["backup_root"].exists() and work.exists()
            else None
        )
        libraries.append({
            "library_id": str(row["library_id"]),
            "display_name": str(row["display_name"]),
            "work_root": str(work),
            "archive_root": str(row["archive_root"]),
            "hardlink_to_central_stock": hardlink,
        })
    return {
        **names,
        "workspace_root": str(paths["workspace_root"]),
        "backup_root": str(paths["backup_root"]),
        "workspaces_root": str(paths["workspaces_root"]),
        "metadata_root": str(paths["metadata_root"]),
        "trash_root": str(paths["trash_root"]),
        "libraries": libraries,
    }


def _rewrite_job_working_path_prefix(
    database_path: Path,
    old_root: Path,
    new_root: Path,
) -> None:
    if not database_path.is_file():
        return
    old_text = str(old_root.resolve(strict=False))
    new_text = str(new_root.resolve(strict=False))
    with database_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT id,working_path FROM jobs WHERE working_path IS NOT NULL"
        ).fetchall()
        for row in rows:
            value = str(row["working_path"] or "")
            if value == old_text:
                replacement = new_text
            elif value.startswith(old_text.rstrip("/") + "/"):
                replacement = new_text.rstrip("/") + value[len(old_text):]
            else:
                continue
            connection.execute(
                "UPDATE jobs SET working_path=?,updated_at=? WHERE id=?",
                (
                    replacement,
                    datetime.now(timezone.utc).isoformat(),
                    str(row["id"]),
                ),
            )
        connection.commit()


@app.get("/api/settings/storage-paths", tags=["Einstellungen"])
def api_get_storage_paths() -> dict[str, Any]:
    return _storage_settings_state()


@app.put("/api/settings/storage-paths", tags=["Einstellungen"])
def api_set_storage_paths(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        old_names = load_storage_settings()
        new_names = normalize_storage_settings(payload)
    except StorageSettingsError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    root = WORKSPACE_PATH.expanduser().resolve(strict=False)
    if not root.is_dir():
        raise HTTPException(status_code=422, detail="Der Workspace-Mount ist nicht verfügbar.")

    key_map = {
        "backup_directory_name": "backup",
        "workspaces_directory_name": "workspaces",
        "metadata_directory_name": "metadata",
        "trash_directory_name": "trash",
    }
    moved: list[tuple[Path, Path]] = []
    previous_rows = list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=False,
        registered_only=True,
    )
    try:
        old_paths = {
            key: (root / old_names[key]).resolve(strict=False)
            for key in key_map
        }
        new_paths = {
            key: (root / new_names[key]).resolve(strict=False)
            for key in key_map
        }

        # Alle vier Namen vor dem ersten Dateisystemeingriff prüfen.
        for key in key_map:
            old_path = old_paths[key]
            new_path = new_paths[key]
            if old_path == new_path:
                continue
            if new_path.exists():
                raise StorageSettingsError(
                    "Der neue Ordnername ist bereits belegt: " + str(new_path)
                )
            if old_path.exists():
                if old_path.is_symlink() or not old_path.is_dir():
                    raise StorageSettingsError(
                        "Der bisherige verwaltete Pfad ist kein normaler Ordner: "
                        + str(old_path)
                    )

        # App-eigene Stammordner dürfen innerhalb desselben Workspace-Mounts
        # atomar umbenannt werden. Kein Dateiinhalt wird kopiert.
        for key in key_map:
            old_path = old_paths[key]
            new_path = new_paths[key]
            if old_path == new_path:
                continue
            if old_path.exists():
                old_path.rename(new_path)
                moved.append((new_path, old_path))
            else:
                new_path.mkdir(parents=True, exist_ok=True)
                moved.append((new_path, old_path))

        save_storage_settings(new_names)

        old_workspaces = old_paths["workspaces_directory_name"]
        new_workspaces = new_paths["workspaces_directory_name"]
        if old_workspaces != new_workspaces:
            for row in previous_rows:
                old_work = Path(str(row["work_root"])).resolve(strict=False)
                try:
                    relative = old_work.relative_to(old_workspaces)
                except ValueError:
                    continue
                replacement = (new_workspaces / relative).resolve(strict=False)
                update_library_paths(
                    REGISTRY_DATABASE_FILE,
                    str(row["library_id"]),
                    work_root=replacement,
                )

        # Den Legacy-Alias auf frischen Installationen nach einer
        # Umbenennung des Arbeitsbereiche-Stamms auf die neue kanonische
        # Main-Wurzel nachziehen. Ein echter historischer Arbeitsbereich wird
        # niemals angefasst.
        legacy_alias = root / WORK_DIRECTORY_NAME
        if legacy_alias.is_symlink():
            main_row = get_library(
                REGISTRY_DATABASE_FILE,
                MAIN_LIBRARY_ID,
                active_only=False,
            )
            if main_row is not None:
                legacy_alias.unlink()
                legacy_alias.symlink_to(
                    Path(str(main_row["work_root"])).resolve(strict=False),
                    target_is_directory=True,
                )

        old_backup = old_paths["backup_directory_name"]
        new_backup = new_paths["backup_directory_name"]
        if old_backup != new_backup:
            for row in previous_rows:
                _rewrite_job_working_path_prefix(
                    Path(str(row["database_path"])),
                    old_backup,
                    new_backup,
                )

        global MAIN_LIBRARY_CONTEXT
        current_main = get_library(
            REGISTRY_DATABASE_FILE,
            MAIN_LIBRARY_ID,
            active_only=False,
        )
        MAIN_LIBRARY_CONTEXT = (
            resolve_library_context(
                REGISTRY_DATABASE_FILE,
                MAIN_LIBRARY_ID,
            )
            if current_main is not None and bool(current_main.get("is_active"))
            else build_main_library_context()
        )
        return _storage_settings_state()
    except Exception as error:
        # Best effort: Konfiguration und atomare Verzeichnis-Renames zurück.
        try:
            save_storage_settings(old_names)
        except Exception:
            pass
        for current, previous in reversed(moved):
            try:
                if current.exists() and not previous.exists():
                    current.rename(previous)
            except OSError:
                pass
        # Registrypfade ebenfalls auf den vorherigen Stand zurückführen.
        for row in previous_rows:
            try:
                update_library_paths(
                    REGISTRY_DATABASE_FILE,
                    str(row["library_id"]),
                    work_root=Path(str(row["work_root"])),
                    archive_root=Path(str(row["archive_root"])),
                )
            except Exception:
                pass
        try:
            legacy_alias = root / WORK_DIRECTORY_NAME
            if legacy_alias.is_symlink():
                old_main = next(
                    (
                        row for row in previous_rows
                        if str(row["library_id"]) == MAIN_LIBRARY_ID
                    ),
                    None,
                )
                if old_main is not None:
                    legacy_alias.unlink()
                    legacy_alias.symlink_to(
                        Path(str(old_main["work_root"])).resolve(strict=False),
                        target_is_directory=True,
                    )
        except OSError:
            pass
        detail = str(error)
        if isinstance(error, OSError):
            detail += (
                " Der Ordner könnte als eigener TrueNAS-Hostpfad/Dataset-Mount "
                "eingebunden sein. Solche Mounts werden in TrueNAS umgestellt, "
                "nicht durch Bibliothekar umbenannt."
            )
        raise HTTPException(status_code=422, detail=detail) from error


@app.get("/api/settings/metadata-correction", tags=["Einstellungen"])
def api_get_metadata_correction_settings() -> dict[str, Any]:
    general = (
        storage_paths(WORKSPACE_PATH)["metadata_root"] / "Allgemein"
    ).resolve(strict=False)
    return {
        "general_root": str(general),
        "managed": True,
        "available": general.is_dir(),
        "writable": general.is_dir() and os.access(general, os.R_OK | os.W_OK | os.X_OK),
    }


@app.put("/api/settings/metadata-correction", tags=["Einstellungen"])
def api_set_metadata_correction_settings(payload: dict[str, Any]) -> dict[str, Any]:
    # Compatibility endpoint for 0.33.0 clients. Since 0.33.1 the location is
    # managed below /workspace/Metadatenkorrektur and cannot be redirected to
    # a technical "main" or external input/output tree.
    requested = str(payload.get("general_root") or "").strip()
    managed = str(
        (storage_paths(WORKSPACE_PATH)["metadata_root"] / "Allgemein").resolve(strict=False)
    )
    if requested and Path(requested).expanduser().resolve(strict=False) != Path(managed):
        raise HTTPException(
            status_code=422,
            detail="„Allgemein“ wird automatisch im Metadatenkorrektur-Ordner verwaltet.",
        )
    return api_get_metadata_correction_settings()


@app.get("/api/settings/event-naming", tags=["Einstellungen"])
def api_get_event_naming() -> dict[str, Any]:
    context = current_library_context()
    return {
        "library_id": context.library_id,
        **naming_from_library_settings(context.settings),
    }


@app.put("/api/settings/event-naming", tags=["Einstellungen"])
def api_set_event_naming(payload: dict[str, Any]) -> dict[str, Any]:
    context = current_library_context()
    try:
        naming = normalize_event_naming(payload)
        row = update_library_settings(
            REGISTRY_DATABASE_FILE,
            context.library_id,
            {"event_naming": naming},
        )
    except (EventNamingError, LibraryRegistryError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Existing events keep their persisted/locked naming snapshot. Only
    # future events read this library default.
    return {
        "library_id": context.library_id,
        **naming_from_library_settings(row.get("settings") or {}),
    }


@app.get("/api/settings/event-folder-layout", tags=["Einstellungen"])
def api_get_event_folder_layout() -> dict[str, Any]:
    with database_connection(current_database_file()) as connection:
        return get_global_event_folder_layout(connection)


@app.put("/api/settings/event-folder-layout", tags=["Einstellungen"])
def api_set_event_folder_layout(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with database_connection(current_database_file()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = set_global_event_folder_layout(
                connection,
                payload,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            connection.commit()
        return state
    except EventLayoutError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/events/{event_id}/folder-layout", tags=["Ereignisse"])
def api_event_folder_layout(event_id: str) -> dict[str, Any]:
    with database_connection(current_database_file()) as connection:
        event = connection.execute(
            "SELECT id FROM events WHERE id=? AND parent_event_id IS NULL",
            (event_id,),
        ).fetchone()
        if event is None:
            raise HTTPException(status_code=404, detail="Ereignis wurde nicht gefunden.")
        return ensure_event_layout_snapshot(
            connection,
            event_id,
            now=datetime.now(timezone.utc).isoformat(),
        )


def path_status(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_directory": path.is_dir(),
        "readable": os.access(path, os.R_OK),
        "writable": os.access(path, os.W_OK),
    }

    if path.is_dir():
        filesystem = os.statvfs(path)

        result["available_bytes"] = (
            filesystem.f_bavail
            * filesystem.f_frsize
        )

        result["total_bytes"] = (
            filesystem.f_blocks
            * filesystem.f_frsize
        )

    return result


def tool_version(
    name: str,
    arguments: list[str],
) -> dict[str, Any]:
    executable = shutil.which(name)

    if executable is None:
        return {
            "available": False,
            "path": None,
            "version": None,
        }

    try:
        result = subprocess.run(
            [executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        first_line = (
            output.splitlines()[0]
            if output
            else None
        )

        return {
            "available": result.returncode == 0,
            "path": executable,
            "version": first_line,
        }

    except Exception as error:
        return {
            "available": False,
            "path": executable,
            "version": None,
            "error": str(error),
        }


def get_health() -> dict[str, Any]:
    errors: list[str] = []

    try:
        settings = load_settings()
        config_loaded = True
    except Exception as error:
        settings = {}
        config_loaded = False
        errors.append(
            f"Konfiguration nicht lesbar: {error}"
        )

    onboarding = _onboarding_required()
    if onboarding:
        health_workspace = WORKSPACE_PATH.resolve(strict=False)
        try:
            setup_paths = storage_paths(health_workspace)
            health_backup_root = Path(setup_paths["backup_root"])
            health_work_area = Path(setup_paths["workspaces_root"])
        except Exception:
            health_backup_root = (
                health_workspace / BACKUP_DIRECTORY_NAME
            ).resolve(strict=False)
            health_work_area = (
                health_workspace / load_storage_settings()["workspaces_directory_name"]
            ).resolve(strict=False)
        archive_path = {
            "path": None,
            "exists": False,
            "is_directory": False,
            "readable": False,
            "writable": False,
            "configured": False,
        }
    else:
        health_workspace = current_workspace_root()
        try:
            health_backup_root = workspace_backup_root(health_workspace)
        except (WorkspaceLayoutError, StorageSettingsError, OSError):
            try:
                health_backup_root = storage_paths(
                    health_workspace
                )["backup_root"]
            except Exception:
                health_backup_root = (
                    health_workspace / BACKUP_DIRECTORY_NAME
                ).resolve(strict=False)
        health_work_area = current_work_root()
        archive_path = path_status(current_archive_root())

    paths = {
        "workspace": path_status(health_workspace),
        "sd_card_backups": path_status(health_backup_root),
        "shared_work_area": path_status(health_work_area),
        "database": path_status(DATABASE_DIRECTORY),
        "logs": path_status(LOG_PATH),
    }

    import_path = path_status(IMPORT_ROOT)

    for name, information in paths.items():
        if not information["exists"]:
            errors.append(
                f"Pfad fehlt: {name}"
            )
        elif not information["writable"]:
            errors.append(
                f"Pfad nicht schreibbar: {name}"
            )

    tools = {
        "exiftool": tool_version(
            "exiftool",
            ["-ver"],
        ),
        "ffmpeg": tool_version(
            "ffmpeg",
            ["-version"],
        ),
        "ffprobe": tool_version(
            "ffprobe",
            ["-version"],
        ),
        "rsync": tool_version(
            "rsync",
            ["--version"],
        ),
        "sha256sum": tool_version(
            "sha256sum",
            ["--version"],
        ),
    }

    for name, information in tools.items():
        if not information["available"]:
            errors.append(
                f"Werkzeug fehlt: {name}"
            )

    if DATABASE_INITIALIZATION_ERROR:
        errors.append(
            "Datenbankinitialisierung fehlgeschlagen: "
            + DATABASE_INITIALIZATION_ERROR
        )

    if WORKSPACE_LAYOUT_ERROR:
        errors.append(
            "Arbeitsbereichsstruktur fehlgeschlagen: "
            + WORKSPACE_LAYOUT_ERROR
        )

    if LIBRARY_REGISTRY_ERROR:
        errors.append(
            "Bibliotheks-Registry fehlgeschlagen: "
            + LIBRARY_REGISTRY_ERROR
        )

    trigger = settings.get("trigger", {})

    return {
        "application": "kamera-automatisierung",
        "version": RELEASE_VERSION,
        "deployment_version": DEPLOYMENT_VERSION,
        "status": "ok" if not errors else "degraded",
        "time": datetime.now().astimezone().isoformat(),
        "runtime": {
            "uid": os.getuid(),
            "gid": os.getgid(),
        },
        "configuration": {
            "path": str(CONFIG_PATH),
            "loaded": config_loaded,
        },
        "database": {
            "path": str(current_database_file()),
            "initialized":
                DATABASE_INITIALIZATION_ERROR is None
                and DATABASE_INITIALIZATION is not None,
            "error": DATABASE_INITIALIZATION_ERROR,
            "schema_versions": (
                DATABASE_INITIALIZATION.get(
                    "applied_versions",
                    [],
                )
                if DATABASE_INITIALIZATION
                else []
            ),
            "tables": (
                DATABASE_INITIALIZATION.get(
                    "tables",
                    [],
                )
                if DATABASE_INITIALIZATION
                else []
            ),
            "integrity": (
                DATABASE_INITIALIZATION.get(
                    "integrity"
                )
                if DATABASE_INITIALIZATION
                else None
            ),
        },
        "library_registry": {
            "path": str(REGISTRY_DATABASE_FILE),
            "initialized": (
                LIBRARY_REGISTRY_ERROR is None
                and LIBRARY_REGISTRY_INITIALIZATION is not None
            ),
            "error": LIBRARY_REGISTRY_ERROR,
            "details": LIBRARY_REGISTRY_INITIALIZATION,
        },
        "library": (
            None
            if onboarding
            else current_library_context().public_dict()
        ),
        "onboarding_required": onboarding,
        "workspace_layout": {
            "initialized": (
                WORKSPACE_LAYOUT_ERROR is None
                and WORKSPACE_LAYOUT_INITIALIZATION is not None
            ),
            "error": WORKSPACE_LAYOUT_ERROR,
            "details": WORKSPACE_LAYOUT_INITIALIZATION,
        },
        "trigger": {
            "active_mode": trigger.get(
                "active_mode"
            ),
            "supported_modes": trigger.get(
                "supported_modes",
                [],
            ),
        },
        "paths": paths,
        "archive": {
            **archive_path,
            "optional": True,
            "read_only_expected": True,
        },
        "import_sources": {
            **import_path,
            "optional": True,
            "read_only_expected": True,
        },
        "tools": tools,
        "errors": errors,
    }


def list_jobs() -> list[dict[str, Any]]:
    return list_database_jobs(
        DATABASE_FILE,
        limit=50,
    )


@app.get(
    "/api/health",
    tags=["System"],
)
def api_health() -> dict[str, Any]:
    return get_health()


def request_library_context(request: Request) -> LibraryContext:
    requested = _requested_library_id(request)
    current = get_current_library()
    if current is not None and current.library_id == requested:
        return current
    try:
        return resolve_library_context(
            REGISTRY_DATABASE_FILE,
            requested,
        )
    except LibraryRegistryError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


def _public_library_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "library_id": str(row["library_id"]),
        "display_name": str(row["display_name"]),
        "is_main": bool(row["is_main"]),
        "is_active": bool(row["is_active"]),
        "is_registered": bool(row.get("is_registered", True)),
        "work_root": str(row["work_root"]),
        "archive_root": str(row["archive_root"]),
    }


def _library_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:32] or "bibliothek"


def _mount_read_only(path: Path) -> bool:
    result = subprocess.run(
        [
            "findmnt",
            "--json",
            "--target",
            str(path),
            "--output",
            "TARGET,OPTIONS",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        rows = json.loads(result.stdout).get("filesystems") or []
        options = str(rows[0].get("options") or "") if rows else ""
    except (ValueError, TypeError, IndexError):
        return False
    return "ro" in {part.strip() for part in options.split(",")}


def _same_filesystem(path_a: Path, path_b: Path) -> bool | None:
    try:
        return int(path_a.stat().st_dev) == int(path_b.stat().st_dev)
    except OSError:
        return None


def inspect_library_paths(
    work_root_value: str,
    archive_root_value: str,
    *,
    exclude_library_id: str | None = None,
    default_library_id: str | None = None,
) -> dict[str, Any]:
    raw_work = str(work_root_value or "").strip()
    if not raw_work and default_library_id:
        work_root = default_library_work_root(
            WORKSPACE_PATH,
            default_library_id,
        )
        managed_default = True
    else:
        work_root = Path(raw_work).expanduser()
        managed_default = False

    archive_root = Path(str(archive_root_value or "").strip()).expanduser()
    errors: list[str] = []
    warnings: list[str] = []

    if not work_root.is_absolute():
        errors.append("Der Arbeitsbereich muss ein absoluter Containerpfad sein.")
    if not archive_root.is_absolute():
        errors.append("Das Archiv muss ein absoluter Containerpfad sein.")

    resolved_work = work_root.resolve(strict=False)
    resolved_archive = archive_root.resolve(strict=False)

    if not errors:
        try:
            if managed_default:
                managed_parent = storage_paths(WORKSPACE_PATH)["workspaces_root"]
                if not managed_parent.is_dir():
                    errors.append(
                        "Der verwaltete Stamm für Bibliotheks-Arbeitsbereiche "
                        "ist nicht verfügbar: " + str(managed_parent)
                    )
                elif not os.access(managed_parent, os.R_OK | os.W_OK | os.X_OK):
                    errors.append(
                        "Der verwaltete Stamm für Bibliotheks-Arbeitsbereiche "
                        "ist nicht vollständig zugreifbar."
                    )
            else:
                resolve_library_work_root(WORKSPACE_PATH, resolved_work)
        except (WorkspaceLayoutError, StorageSettingsError) as error:
            errors.append(str(error))

        if not resolved_archive.exists() or not resolved_archive.is_dir():
            errors.append("Der Archiv-Mount ist nicht verfügbar: " + str(resolved_archive))
        elif not os.access(resolved_archive, os.R_OK | os.X_OK):
            errors.append("Der Archiv-Mount ist nicht lesbar: " + str(resolved_archive))
        elif not _mount_read_only(resolved_archive):
            errors.append(
                "Der Archiv-Mount ist nicht nachweislich read-only. "
                "Bitte diesen Host Path in TrueNAS einzeln als Read Only einbinden."
            )

        if (
            resolved_work == resolved_archive
            or resolved_work in resolved_archive.parents
            or resolved_archive in resolved_work.parents
        ):
            errors.append("Arbeitsbereich und Archiv dürfen nicht ineinander liegen.")

        for row in list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        ):
            if exclude_library_id and str(row["library_id"]) == exclude_library_id:
                continue
            other_work = Path(str(row["work_root"])).resolve(strict=False)
            other_archive = Path(str(row["archive_root"])).resolve(strict=False)
            if (
                resolved_work == other_work
                or resolved_work in other_work.parents
                or other_work in resolved_work.parents
            ):
                errors.append(
                    "Der Arbeitsbereich überschneidet sich mit "
                    + str(row["display_name"])
                    + "."
                )
            if (
                resolved_archive == other_archive
                or resolved_archive in other_archive.parents
                or other_archive in resolved_archive.parents
            ):
                errors.append(
                    "Das Archiv überschneidet sich mit "
                    + str(row["display_name"])
                    + "."
                )

    try:
        central = workspace_backup_root(WORKSPACE_PATH)
        hardlink_compatible = (
            _same_filesystem(central, resolved_work)
            if resolved_work.exists()
            else None
        )
    except Exception:
        central = Path()
        hardlink_compatible = None

    if hardlink_compatible is False:
        warnings.append(
            "Arbeitsbereich und SD-Kartensicherungen liegen auf unterschiedlichen "
            "Dateisystemen. Hardlinks sind dort nicht möglich; Bibliothekar bietet "
            "bei Bedarf Kopieren oder Verschieben an."
        )

    return {
        "valid": not errors,
        "work_root": str(resolved_work),
        "archive_root": str(resolved_archive),
        "managed_default_work_root": managed_default,
        "archive_read_only": (
            bool(resolved_archive.exists())
            and _mount_read_only(resolved_archive)
        ),
        "hardlink_to_central_stock": hardlink_compatible,
        "central_stock_root": str(central) if str(central) != "." else "",
        "errors": errors,
        "warnings": warnings,
    }


@app.get(
    "/api/libraries",
    tags=["Bibliotheken"],
)
def api_libraries(include_inactive: bool = False) -> dict[str, Any]:
    rows = list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=not include_inactive,
        registered_only=True,
    )
    return {
        "libraries": [_public_library_row(row) for row in rows],
    }


@app.post(
    "/api/libraries/check",
    tags=["Bibliotheken"],
)
def api_check_library(payload: dict[str, Any]) -> dict[str, Any]:
    return inspect_library_paths(
        str(payload.get("work_root") or ""),
        str(payload.get("archive_root") or ""),
        exclude_library_id=(
            str(payload.get("library_id") or "").strip() or None
        ),
        default_library_id=(
            str(payload.get("default_library_id") or "").strip() or None
        ),
    )


@app.post(
    "/api/libraries",
    tags=["Bibliotheken"],
    status_code=201,
)
def api_create_library(payload: dict[str, Any]) -> dict[str, Any]:
    display_name = " ".join(
        str(payload.get("display_name") or "").split()
    ).strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Anzeigename fehlt.")

    existing_registered = list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=False,
        registered_only=True,
    )
    first_library = not existing_registered
    library_id = (
        MAIN_LIBRARY_ID
        if first_library
        else (
            _library_slug(display_name)
            + "-"
            + uuid.uuid4().hex[:8]
        )
    )
    requested_work = str(payload.get("work_root") or "").strip()
    default_work_id = None
    if not requested_work:
        default_work_id = (
            _library_slug(display_name)
            if first_library
            else library_id
        )
    checked = inspect_library_paths(
        requested_work,
        str(payload.get("archive_root") or ""),
        default_library_id=default_work_id,
    )
    if not checked["valid"]:
        raise HTTPException(status_code=422, detail=checked)

    database_path = (
        DATABASE_FILE
        if first_library
        else (
            DATABASE_DIRECTORY
            / "libraries"
            / f"{library_id}.sqlite3"
        )
    )
    created_database = (
        not first_library
        and not database_path.exists()
    )
    registration_created = False

    try:
        resolved_work = Path(str(checked["work_root"]))
        resolved_work.mkdir(parents=True, exist_ok=True)
        initialize_database(database_path)
        ensure_library_identity(database_path, library_id)
        projection = (
            {"jobs": 0, "families": 0, "files": 0}
            if first_library
            else project_all_imports(
                DATABASE_FILE,
                database_path,
            )
        )
        row = register_library(
            REGISTRY_DATABASE_FILE,
            library_id=library_id,
            display_name=display_name,
            database_path=database_path,
            workspace_root=WORKSPACE_PATH,
            work_root=resolved_work,
            archive_root=Path(str(checked["archive_root"])),
            is_main=first_library,
            is_active=True,
            settings={
                "created_by": f"bibliothekar-{DEPLOYMENT_VERSION}",
                "projected_imports": projection,
                "managed_default_work_root": bool(
                    checked.get("managed_default_work_root")
                ),
                "user_created_primary_library": bool(first_library),
            },
        )
        registration_created = True
        backfill_library_inventory(
            REGISTRY_DATABASE_FILE,
            database_path=database_path,
            library_id=library_id,
            claim_all_owned=False,
        )
        synchronize_global_central_stock()
        if first_library:
            global MAIN_LIBRARY_CONTEXT
            MAIN_LIBRARY_CONTEXT = resolve_library_context(
                REGISTRY_DATABASE_FILE,
                MAIN_LIBRARY_ID,
            )
    except Exception as error:
        # Eine fehlgeschlagene Neuanlage darf keinen Registry-Zombie
        # hinterlassen. Auch die erste, intern als Primärbibliothek geführte
        # Bibliothek wird aus der Registry zurückgerollt; die globale SQLite
        # selbst bleibt dabei erhalten.
        if registration_created:
            try:
                remove_library_registration(
                    REGISTRY_DATABASE_FILE,
                    library_id,
                    allow_main=first_library,
                )
            except Exception:
                pass
        if created_database:
            for candidate in (
                database_path,
                Path(str(database_path) + "-wal"),
                Path(str(database_path) + "-shm"),
            ):
                candidate.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {"library": _public_library_row(row)}


@app.patch(
    "/api/libraries/{library_id}",
    tags=["Bibliotheken"],
)
def api_update_library(library_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = get_library(
        REGISTRY_DATABASE_FILE,
        library_id,
        active_only=False,
    )
    if row is None or not row.get("is_registered", True):
        raise HTTPException(status_code=404, detail="Bibliothek wurde nicht gefunden.")

    if "display_name" in payload:
        try:
            row = update_library_display_name(
                REGISTRY_DATABASE_FILE,
                library_id,
                str(payload.get("display_name") or ""),
            )
        except LibraryRegistryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    # Eine aktive Bibliothek darf beim bloßen Pfadwechsel nicht an einem
    # veralteten DB-Eintrag scheitern, wenn ihre echte, identitätsgeprüfte
    # Standard-DB weiterhin vorhanden ist.
    if bool(row.get("is_active")):
        try:
            _, row = _resolve_registered_library_database(row)
        except LibraryRegistryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    wants_paths = "work_root" in payload or "archive_root" in payload
    if wants_paths:
        requested_work = str(
            payload.get("work_root")
            if "work_root" in payload
            else row["work_root"]
        )
        requested_archive = str(
            payload.get("archive_root")
            if "archive_root" in payload
            else row["archive_root"]
        )
        checked = inspect_library_paths(
            requested_work,
            requested_archive,
            exclude_library_id=library_id,
        )
        if not checked["valid"]:
            raise HTTPException(status_code=422, detail=checked)
        try:
            row = update_library_paths(
                REGISTRY_DATABASE_FILE,
                library_id,
                work_root=Path(str(checked["work_root"])),
                archive_root=Path(str(checked["archive_root"])),
            )
            if library_id == MAIN_LIBRARY_ID:
                global MAIN_LIBRARY_CONTEXT
                MAIN_LIBRARY_CONTEXT = resolve_library_context(
                    REGISTRY_DATABASE_FILE,
                    MAIN_LIBRARY_ID,
                )
                legacy_alias = WORKSPACE_PATH / WORK_DIRECTORY_NAME
                if legacy_alias.is_symlink():
                    _ensure_compatibility_link(
                        legacy_alias,
                        MAIN_LIBRARY_CONTEXT.work_root,
                    )
        except LibraryRegistryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return {"library": _public_library_row(row)}


@app.post(
    "/api/libraries/{library_id}/deactivate",
    tags=["Bibliotheken"],
)
def api_deactivate_library(library_id: str) -> dict[str, Any]:
    try:
        row = set_library_active(
            REGISTRY_DATABASE_FILE,
            library_id,
            False,
        )
    except LibraryRegistryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"library": _public_library_row(row)}


@app.post(
    "/api/libraries/{library_id}/activate",
    tags=["Bibliotheken"],
)
def api_activate_library(library_id: str) -> dict[str, Any]:
    try:
        existing = get_library(
            REGISTRY_DATABASE_FILE,
            library_id,
            active_only=False,
        )
        if existing is None or not existing.get("is_registered", True):
            raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")

        database_path, existing = _resolve_registered_library_database(
            existing
        )
        # Aktivieren darf niemals still eine neue leere Bibliotheks-DB
        # erzeugen. initialize_database() läuft erst nach dem Existenz- und
        # Identitätscheck und dient hier ausschließlich Schema-Migrationen.
        initialize_database(database_path)
        identity = read_library_identity(database_path)
        if identity != library_id:
            raise LibraryRegistryError(
                "Die SQLite-Datenbank gehört nicht zu dieser Bibliothek: "
                + str(database_path)
            )
        project_all_imports(
            DATABASE_FILE,
            database_path,
        )
        backfill_library_inventory(
            REGISTRY_DATABASE_FILE,
            database_path=database_path,
            library_id=library_id,
            claim_all_owned=False,
        )
        backfill_library_claims(
            REGISTRY_DATABASE_FILE,
            database_path=database_path,
            library_id=library_id,
        )
        row = set_library_active(
            REGISTRY_DATABASE_FILE,
            library_id,
            True,
        )
        synchronize_global_central_stock()
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"library": _public_library_row(row)}


@app.post(
    "/api/libraries/{library_id}/unregister",
    tags=["Bibliotheken"],
)
def api_unregister_library(library_id: str) -> dict[str, Any]:
    try:
        row = unregister_library(
            REGISTRY_DATABASE_FILE,
            library_id,
        )
    except LibraryRegistryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"library": _public_library_row(row)}


@app.get(
    "/api/libraries/current",
    tags=["Bibliotheken"],
)
def api_current_library(request: Request) -> dict[str, Any]:
    return request_library_context(request).public_dict()


@app.get(
    "/api/capabilities",
    tags=["System"],
)
def api_capabilities() -> dict[str, Any]:
    settings = load_settings()

    return {
        "trigger": settings.get("trigger", {}),
        "safety": settings.get("safety", {}),
        "storage": settings.get("storage", {}),
        "implemented": {
            "health_check": True,
            "manual_simulation_trigger": True,
            "persistent_job_queue": True,
            "background_worker": True,
            "metadata_analysis": True,
            "metadata_review_api": True,
            "workspace_day_groups": True,
            "event_read_api": True,
            "event_write_api": True,
            "event_delete_api": True,
            "event_management_ui": True,
            "sort_plan_read_only": True,
            "sort_apply": True,
            "sort_apply_progress": True,
            "sort_apply_rollback": True,
            "shared_workspace_layout": True,
            "legacy_applied_layout_migration": True,
            "automatic_backup_lifecycle_simulation": True,
            "folder_import_release_candidate": True,
            "real_metadata_day_grouping": True,
            "normalized_camera_names": True,
            "temporary_backup_cleanup": True,
            "archive_verification_read_only": True,
            "archive_transfer_ui": True,
            "ssd_release_after_archive": True,
            "archive_change_review_api": True,
            "approved_sd_trigger": True,
            "usb_key_trigger": True,
            "real_sd_pipeline": True,
            "external_drive_source": True,
            "folder_source_browser": True,
            "real_zfs_snapshot": False,
        },
    }



MEDIA_SOURCE_EXTENSIONS = {
    ".raf", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2",
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif",
    ".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts", ".xmp",
}


def source_root_path(root_key: str) -> Path | None:
    return {
        "saved": IMPORT_ROOT,
        "removable": REMOVABLE_ROOT,
        "nas": NAS_SOURCE_ROOT,
    }.get(str(root_key).strip())


def _safe_root(root_key: str) -> Path:
    root = source_root_path(root_key)
    if root is None:
        raise HTTPException(status_code=422, detail="Unbekannter Quellenbereich.")
    try:
        return root.resolve(strict=True)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quellenbereich ist nicht eingebunden.") from error


def resolve_import_source(relative_value: str, root_key: str = "saved") -> Path:
    relative = Path(str(relative_value).strip() or ".")
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=422, detail="Ungültiger relativer Quellpfad.")
    root = _safe_root(root_key)
    try:
        candidate = (root / relative).resolve(strict=True)
        candidate.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=404, detail="Die ausgewählte Importquelle wurde nicht gefunden.") from error
    if not candidate.is_dir() or candidate.is_symlink():
        raise HTTPException(status_code=422, detail="Importquelle ist kein zulässiger Ordner.")
    return candidate


def source_device_id_for_path(path: Path, root_key: str, root: Path) -> str | None:
    if root_key != "removable":
        return None
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def import_source_summary(path: Path, root_key: str, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix() or "."
    file_count = 0
    media_count = 0
    total_size = 0
    source_device_id = source_device_id_for_path(path, root_key, root)
    history_rows = (
        list_imported_source_files(DATABASE_FILE, source_device_id)
        if source_device_id
        else []
    )
    fast_history = {
        (str(row["relative_path"]), int(row["size_bytes"]), int(row.get("modified_at_ns") or 0))
        for row in history_rows
    }
    already_imported_fast = 0
    new_fast = 0
    changed_fast = 0
    ignored_fast = 0
    history_paths = {str(row["relative_path"]) for row in history_rows}
    for item in path.rglob("*"):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            stat = item.stat()
            size = stat.st_size
        except OSError:
            continue
        file_count += 1
        total_size += size
        relative_item = item.relative_to(path).as_posix()
        if item.suffix.lower() not in MEDIA_SOURCE_EXTENSIONS:
            ignored_fast += 1
            continue
        media_count += 1
        if (relative_item, int(size), int(stat.st_mtime_ns)) in fast_history:
            already_imported_fast += 1
        elif relative_item in history_paths:
            changed_fast += 1
        else:
            new_fast += 1
    signature = quick_source_signature(path)
    duplicate = find_folder_import_by_identity(
        DATABASE_FILE,
        source_signature=signature,
        include_active=True,
    )
    import_status = "available"
    if duplicate is not None:
        import_status = "already_imported" if duplicate.get("state") == "completed" else "import_running"
    elif source_device_id and history_rows and new_fast == 0 and changed_fast == 0:
        # Reused SD card with no new/changed camera media is a normal idle state,
        # not an import error. Non-media camera management files do not keep the
        # source artificially "new".
        import_status = "no_changes"
    return {
        "root_key": root_key,
        "relative_path": relative,
        "name": path.name,
        "file_count": file_count,
        "media_file_count": media_count,
        "total_size_bytes": total_size,
        "source_signature": signature,
        "source_device_id": source_device_id,
        "already_imported_file_count": already_imported_fast,
        "new_file_count": new_fast,
        "changed_file_count": changed_fast,
        "ignored_file_count": ignored_fast,
        "import_status": import_status,
        "existing_job_id": duplicate.get("id") if duplicate else None,
        "existing_job_created_at": duplicate.get("created_at") if duplicate else None,
    }


def discover_import_sources(root_key: str = "saved") -> list[dict[str, Any]]:
    root_path = source_root_path(root_key)
    if root_path is None or not root_path.is_dir():
        return []
    root = root_path.resolve()
    candidates: list[Path] = []
    for path in sorted([root, *root.rglob("*")]):
        if not path.is_dir() or path.is_symlink():
            continue
        try:
            relative_parts = path.relative_to(root).parts
            depth = len(relative_parts)
        except ValueError:
            continue
        if depth > 5 or any(part.startswith(".") for part in relative_parts):
            continue
        try:
            has_dcim = (path / "DCIM").is_dir()
            has_direct_media = any(
                child.is_file() and child.suffix.lower() in MEDIA_SOURCE_EXTENSIONS
                for child in path.iterdir()
            )
        except OSError:
            continue
        if has_dcim or has_direct_media:
            if any(existing == path or existing in path.parents for existing in candidates):
                continue
            candidates.append(path)
    return [import_source_summary(path, root_key, root) for path in candidates]


def _helper_request(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(SOURCE_HELPER_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("detail")
        except Exception:
            detail = None
        raise HTTPException(status_code=error.code, detail=detail or "Quellen-Helfer meldet einen Fehler.") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Quellen-Helfer ist nicht erreichbar.") from error


@app.get("/api/import-sources", tags=["Import"])
def api_import_sources(force_refresh: bool = False) -> dict[str, Any]:
    # Quellen können auch außerhalb von Bibliothekar verändert werden.
    # Die Darstellung bleibt kurz gecacht; Mount-Prüfung erfolgt unabhängig davon.
    db_path = DATABASE_FILE
    if not force_refresh:
        cached = view_cache.get_snapshot(db_path, "import-sources", max_age_seconds=15)
        if cached is not None and cached["mounted"] == IMPORT_ROOT.is_dir():
            return cached
    sources = discover_import_sources("saved") + discover_import_sources("removable")
    result = {
        "root": str(IMPORT_ROOT),
        "mounted": IMPORT_ROOT.is_dir(),
        "count": len(sources),
        "sources": sources,
    }
    view_cache.put_snapshot(db_path, "import-sources", result)
    return result


@app.get("/api/source-devices", tags=["Import"])
def api_source_devices() -> dict[str, Any]:
    return _helper_request("/devices")


@app.post("/api/source-devices/mount", tags=["Import"])
def api_mount_source_device(payload: dict[str, Any]) -> dict[str, Any]:
    return _helper_request("/mount", method="POST", payload=payload)


@app.post("/api/source-devices/unmount", tags=["Import"])
def api_unmount_source_device(payload: dict[str, Any]) -> dict[str, Any]:
    return _helper_request("/unmount", method="POST", payload=payload)


@app.get("/api/source-folders", tags=["Import"])
def api_source_folders(root_key: str = "nas", relative_path: str = ".") -> dict[str, Any]:
    root = _safe_root(root_key)
    relative = Path(relative_path or ".")
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=422, detail="Ungültiger Ordnerpfad.")
    try:
        current = (root / relative).resolve(strict=True)
        current.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=404, detail="Ordner wurde nicht gefunden.") from error
    if not current.is_dir():
        raise HTTPException(status_code=422, detail="Pfad ist kein Ordner.")
    directories = []
    try:
        for child in sorted(current.iterdir(), key=lambda item: item.name.casefold()):
            if child.name.startswith(".") or child.is_symlink() or not child.is_dir():
                continue
            directories.append({"name": child.name, "relative_path": child.relative_to(root).as_posix()})
    except PermissionError:
        pass
    rel = current.relative_to(root)
    parent = None if not rel.parts else Path(*rel.parts[:-1]).as_posix() or "."
    return {
        "root_key": root_key,
        "relative_path": rel.as_posix() or ".",
        "parent_relative_path": parent,
        "directories": directories,
    }


def _folder_import_runtime_blocker() -> str | None:
    startup_errors = [
        value
        for value in (
            DATABASE_INITIALIZATION_ERROR,
            WORKSPACE_LAYOUT_ERROR,
            LIBRARY_REGISTRY_ERROR,
        )
        if str(value or "").strip()
    ]
    if startup_errors:
        return (
            "Ordnerimport ist derzeit nicht verfügbar, weil die "
            "Bibliothekar-Initialisierung fehlgeschlagen ist: "
            + str(startup_errors[0])
        )

    # Direkte Unit-Test-Aufrufe laufen ohne Startup-Lifespan. Im echten
    # Prozess sind nach erfolgreicher Initialisierung alle drei Strukturen
    # gesetzt; dann muss auch der Queue-Worker tatsächlich leben.
    initialized = all(
        value is not None
        for value in (
            DATABASE_INITIALIZATION,
            WORKSPACE_LAYOUT_INITIALIZATION,
            LIBRARY_REGISTRY_INITIALIZATION,
        )
    )
    if initialized and (
        WORKER_THREAD is None
        or not WORKER_THREAD.is_alive()
    ):
        return (
            "Ordnerimport ist derzeit nicht verfügbar, weil der "
            "Hintergrund-Worker nicht läuft."
        )
    return None


@app.post(
    "/api/jobs/folder-import",
    tags=["Import"],
    status_code=202,
)
def api_run_folder_import(payload: dict[str, Any]) -> JSONResponse:
    blocker = _folder_import_runtime_blocker()
    if blocker:
        raise HTTPException(status_code=503, detail=blocker)

    relative_value = str(payload.get("source_relative_path") or "").strip()
    root_key = str(payload.get("source_root_key") or "saved").strip()
    source = resolve_import_source(relative_value, root_key)
    root = _safe_root(root_key)
    source_device_id = source_device_id_for_path(source, root_key, root)
    source_signature = quick_source_signature(source)
    duplicate = find_folder_import_by_identity(
        DATABASE_FILE,
        source_signature=source_signature,
        include_active=True,
    )
    if duplicate is not None:
        state_text = "bereits importiert" if duplicate.get("state") == "completed" else "wird bereits importiert"
        raise HTTPException(
            status_code=409,
            detail=(
                "Diese Quelle ist " + state_text + ". Technische ID: "
                + str(duplicate.get("id") or "unbekannt")
            ),
        )
    now = datetime.now().astimezone()
    job_id = now.strftime("FOLDER_IMPORT_%Y%m%d_%H%M%S_%f")
    label = str(payload.get("display_name") or source.name).strip() or source.name
    source_mode = str(payload.get("source_mode") or "folder").strip()
    trigger_type = {
        "sd_card": "approved_sd",
        "drive": "usb_key",
        "folder": "manual",
    }.get(source_mode, "manual")
    try:
        job = create_job(
            DATABASE_FILE,
            job_id=job_id,
            kind="sd_import",
            trigger_type=trigger_type,
            source_path=str(source),
            working_path=str(workspace_backup_root(WORKSPACE_PATH)),
            operation="folder_import",
            source_volume_label=label,
            source_signature=source_signature,
            source_device_id=source_device_id,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "message": "Ordnerimport wurde in die Warteschlange aufgenommen.",
            "job": job,
        },
    )


# Der Import-/Prüfverlauf ist eine separate, paginierte Anzeige und verändert
# weder die Sicherungsdateien noch die fachlichen Auftragszustände.
@app.get("/api/import-history", tags=["Import"])
def api_import_history(
    offset: int = 0, limit: int = 5, hidden: bool = False, count_only: bool = False,
) -> dict[str, Any]:
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 50))
    where = """(operation IN ('folder_import', 'metadata_fixture_analysis', 'sd_import')
                 OR (operation='legacy_simulation' AND kind IN ('sd_import','simulation')))
                 AND operation NOT IN ('metadata_general_import','metadata_multiple_import')
                 AND history_hidden=?"""
    with database_connection(DATABASE_FILE) as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE " + where, (int(hidden),)
        ).fetchone()[0])
        if count_only:
            return {"jobs": [], "total": total, "has_more": False}
        ids = [
            str(row[0]) for row in conn.execute(
                "SELECT id FROM jobs WHERE " + where
                + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (int(hidden), limit, offset),
            ).fetchall()
        ]
    rows: list[dict[str, Any]] = []
    for job_id in ids:
        item = get_job(DATABASE_FILE, job_id)
        if item is None:
            continue
        item["backup_delete_allowed"] = False
        item["backup_delete_reason"] = ""
        if (item.get("operation") == "folder_import"
                and item.get("kind") == "sd_import"
                and item.get("state") == "completed"):
            try:
                info = backup_deletion_status(
                    DATABASE_FILE,
                    REGISTRY_DATABASE_FILE,
                    workspace_backup_root(WORKSPACE_PATH),
                    job_id,
                )
                item["backup_delete_allowed"] = bool(info.get("allowed"))
                item["backup_delete_reason"] = str(info.get("reason") or "")
            except Exception as error:
                item["backup_delete_reason"] = str(error)
        rows.append(item)
    return {"jobs": rows, "total": total, "has_more": offset + len(rows) < total}


@app.post("/api/import-history/{job_id}/visibility", tags=["Import"])
def api_import_history_visibility(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    hidden = payload.get("hidden")
    if not isinstance(hidden, bool):
        raise HTTPException(status_code=422, detail="Sichtbarkeit muss true oder false sein.")
    with database_connection(DATABASE_FILE) as conn:
        row = conn.execute(
            "SELECT id, operation, kind, state FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Import nicht gefunden.")
        if not (
            row["operation"] in ("folder_import", "metadata_fixture_analysis", "sd_import")
            or (row["operation"] == "legacy_simulation" and row["kind"] in ("sd_import","simulation"))
        ):
            raise HTTPException(status_code=409, detail="Dieser Auftrag ist kein Importverlauf.")
        if hidden and row["state"] != "completed":
            raise HTTPException(status_code=409, detail="Nur abgeschlossene Importe ausblenden.")
        conn.execute(
            "UPDATE jobs SET history_hidden=? WHERE id=?", (int(hidden), job_id)
        )
    view_cache.invalidate(DATABASE_FILE)
    return {"job_id": job_id, "hidden": hidden}


@app.get(
    "/api/jobs",
    tags=["Aufträge"],
)
def api_jobs() -> dict[str, Any]:
    try:
        reconcile_global_central_stock_state(
            force=False
        )
    except Exception as error:
        print(
            f"Zentralbestands-Abgleich übersprungen: {error}",
            flush=True,
        )
    jobs = list_jobs()
    central_root = workspace_backup_root(WORKSPACE_PATH)

    lifecycle_by_job = {
        str(item.get("job_id") or ""): item
        for item in list_backup_lifecycles(DATABASE_FILE, limit=100)
    }
    stage_ranges = {
        "starting": (0, 5),
        "source_manifest": (5, 120),
        "copying": (120, 430),
        "backup_verification": (430, 620),
        "snapshot_created": (620, 630),
        "metadata_analysis": (630, 850),
        "organization_planning": (850, 900),
        "workspace_moving": (900, 970),
        "workspace_verification": (970, 995),
        "completed": (1000, 1000),
    }

    for job in jobs:
        job_id = str(job.get("id") or job.get("job_id") or "")
        lifecycle = lifecycle_by_job.get(job_id) or {}
        details = lifecycle.get("details") or {}
        stage = str(details.get("stage") or job.get("stage") or "")
        stage_current = max(0, int(details.get("progress_current") or 0))
        stage_total = max(0, int(details.get("progress_total") or 0))
        job["stage_progress_stage"] = stage
        job["stage_progress_current"] = stage_current
        job["stage_progress_total"] = stage_total

        if str(job.get("state") or "") == "completed":
            job["overall_progress_current"] = 1000
            job["overall_progress_total"] = 1000
        elif stage in stage_ranges:
            lower, upper = stage_ranges[stage]
            if stage_total > 0:
                ratio = max(0.0, min(1.0, stage_current / stage_total))
                overall = int(round(lower + (upper - lower) * ratio))
            else:
                overall = int(lower)
            job["overall_progress_current"] = overall
            job["overall_progress_total"] = 1000
        else:
            job["overall_progress_current"] = max(
                0, int(job.get("progress_current") or 0)
            )
            job["overall_progress_total"] = max(
                0, int(job.get("progress_total") or 0)
            )

        if (
            str(job.get("kind") or "") == "sd_import"
            and str(job.get("operation") or "") == "folder_import"
            and str(job.get("state") or "") == "completed"
        ):
            try:
                deletion = backup_deletion_status(
                    DATABASE_FILE,
                    REGISTRY_DATABASE_FILE,
                    central_root,
                    str(job.get("id") or job.get("job_id") or ""),
                )
            except Exception as error:
                deletion = {
                    "allowed": False,
                    "reason": str(error),
                }
            job["backup_delete_allowed"] = bool(deletion.get("allowed"))
            job["backup_delete_reason"] = str(deletion.get("reason") or "")
        else:
            job["backup_delete_allowed"] = False
            job["backup_delete_reason"] = ""

    return {
        "count": len(jobs),
        "jobs": jobs,
    }


@app.post(
    "/api/jobs/{job_id}/cancel",
    tags=["Import"],
    status_code=202,
)
def api_cancel_import(job_id: str) -> JSONResponse:
    job = get_job(DATABASE_FILE, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import wurde nicht gefunden.")
    if (
        str(job.get("kind") or "") != "sd_import"
        or str(job.get("operation") or "") != "folder_import"
    ):
        raise HTTPException(
            status_code=409,
            detail="Nur laufende Kameraimporte können hier abgebrochen werden.",
        )

    state = str(job.get("state") or "")
    if state == "queued":
        with database_connection(DATABASE_FILE) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM jobs WHERE id = ? AND state = 'queued'",
                (job_id,),
            )
            connection.commit()
        if cursor.rowcount == 1:
            _clear_import_cancel(job_id)
            return JSONResponse(
                status_code=202,
                content={
                    "accepted": True,
                    "cancelled": True,
                    "message": "Import wurde vor dem Start abgebrochen.",
                },
            )
        job = get_job(DATABASE_FILE, job_id)
        state = str((job or {}).get("state") or "")

    if state in {
        "copying",
        "verifying",
        "backup_verified",
        "analyzing_metadata",
        "organizing",
    }:
        _request_import_cancel(job_id)
        return JSONResponse(
            status_code=202,
            content={
                "accepted": True,
                "cancelled": False,
                "message": "Abbruch wurde angefordert. Der Import wird sicher zurückgerollt.",
            },
        )

    if state == "completed":
        raise HTTPException(
            status_code=409,
            detail="Der Import ist bereits abgeschlossen und kann nicht mehr abgebrochen werden.",
        )
    raise HTTPException(
        status_code=409,
        detail="Dieser Import kann in seinem aktuellen Zustand nicht abgebrochen werden.",
    )


@app.delete(
    "/api/jobs/{job_id}/discard",
    tags=["Import"],
)
def api_discard_terminal_import(job_id: str) -> dict[str, Any]:
    try:
        result = _discard_terminal_import_job(job_id)
    except ValueError as error:
        message = str(error)
        status_code = 404 if "nicht gefunden" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from error

    return {
        "deleted": True,
        "job_id": job_id,
        "message": "Unterbrochener Import wurde vollständig aus dem Verlauf entfernt.",
        **result,
    }


@app.delete(
    "/api/backups/{job_id}",
    tags=["Sicherungen"],
)
def api_delete_backup(job_id: str) -> dict[str, Any]:
    library_ids = [
        str(row.get("library_id") or MAIN_LIBRARY_ID)
        for row in list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=False,
        )
    ]
    try:
        result = delete_backup(
            DATABASE_FILE,
            REGISTRY_DATABASE_FILE,
            workspace_backup_root(WORKSPACE_PATH),
            job_id,
        )
    except BackupDeletionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    shutil.rmtree(LOG_PATH / "backups" / job_id, ignore_errors=True)
    for library_id in set([MAIN_LIBRARY_ID, *library_ids]):
        try:
            _thumbnail_path(job_id, library_id=library_id).unlink()
        except FileNotFoundError:
            pass

    return {
        "deleted": True,
        **result,
    }


@app.get(
    "/api/jobs/{job_id}/thumbnail",
    tags=["Aufträge"],
)
def api_job_thumbnail(job_id: str):
    job = get_job(DATABASE_FILE, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Auftrag wurde nicht gefunden.")
    path = ensure_job_thumbnail(job_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Kein JPEG-Vorschaubild verfügbar.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"{job_id}-thumbnail.jpg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get(
    "/api/jobs/{job_id}",
    tags=["Aufträge"],
)
def api_job_detail(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(
        DATABASE_FILE,
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    return job


@app.get(
    "/api/backups",
    tags=["Sicherungen"],
)
def api_backups() -> dict[str, Any]:
    backups = list_backup_lifecycles(
        DATABASE_FILE,
        limit=100,
    )

    return {
        "count": len(backups),
        "backups": backups,
    }


@app.get(
    "/api/archive/summary",
    tags=["Archivübernahme"],
)
def api_archive_summary(force_refresh: bool = False) -> dict[str, Any]:
    db_path = current_database_file()
    if not force_refresh:
        cached = view_cache.get_snapshot(db_path, "archive", max_age_seconds=20)
        if cached is not None:
            return cached
    result = list_archive_candidates(db_path, current_archive_root())
    view_cache.put_snapshot(db_path, "archive", result)
    return result


@app.post(
    "/api/jobs/{job_id}/events/{event_id}/archive-verify",
    tags=["Archivübernahme"],
)
def api_archive_verify(
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    try:
        verification = verify_event_archive(
            current_database_file(),
            current_archive_root(),
            job_id,
            event_id,
            workspace_path=current_workspace_root(),
        )
        if verification.get("verified"):
            return finalize_manually_moved_event_if_verified(
                current_database_file(),
                current_workspace_root(),
                current_archive_root(),
                job_id,
                event_id,
                verification,
            )
        return verification
    except (ArchiveVerificationError, SsdReleaseError) as error:
        message = str(error)
        status_code = 404 if "nicht gefunden" in message else 409
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error


@app.post(
    "/api/jobs/{job_id}/events/{event_id}/ssd-release",
    tags=["Archivübernahme"],
)
def api_ssd_release(
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    try:
        return release_event_ssd(
            current_database_file(),
            current_workspace_root(),
            current_archive_root(),
            job_id,
            event_id,
        )
    except SsdReleaseError as error:
        message = str(error)
        status_code = 404 if "nicht gefunden" in message else 409
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error


@app.get("/trash", response_class=HTMLResponse, tags=["Oberfläche"])
def trash_interface() -> HTMLResponse:
    return HTMLResponse(
        content=apply_shell(TRASH_HTML, active_area="trash"),
        status_code=200,
    )


@app.get("/api/trash", tags=["Papierkorb"])
def api_trash_inventory() -> dict[str, Any]:
    # The shared physical tree is the source of truth. Reconcile every
    # registered library so a Finder move cannot leave parallel active rows.
    results = []
    for row in list_libraries(
        REGISTRY_DATABASE_FILE,
        active_only=False,
        registered_only=True,
    ):
        path = Path(str(row["database_path"]))
        if path.is_file():
            results.append(
                reconcile_trash_inventory(path, WORKSPACE_PATH)
            )
    if not results:
        return reconcile_trash_inventory(current_database_file(), WORKSPACE_PATH)
    result = results[0]
    known_paths = {
        str(item["relative_path"])
        for state in results
        for item in state["entries"]
        if item.get("entry_type") == "file" and item.get("tracked")
    }
    entries = [
        {
            **item,
            "tracked": (
                str(item["relative_path"]) in known_paths
                if item.get("entry_type") == "file"
                else False
            ),
        }
        for item in result["entries"]
    ]
    return {
        **result,
        "tracked_file_count": sum(
            1 for item in entries
            if item.get("entry_type") == "file" and item.get("tracked")
        ),
        "untracked_file_count": sum(
            1 for item in entries
            if item.get("entry_type") == "file" and not item.get("tracked")
        ),
        "entries": entries,
    }


@app.post("/api/trash/empty", tags=["Papierkorb"])
def api_empty_trash(payload: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("confirmation") or "") != TRASH_CONFIRMATION:
        raise HTTPException(
            status_code=422,
            detail="Die ausdrückliche Sicherheitsbestätigung fehlt.",
        )
    try:
        api_trash_inventory()
        empty_trash_filesystem(WORKSPACE_PATH)
        # A failed/partial filesystem deletion raises and leaves DB rows
        # untouched; only a fully empty physical root permits DB cleanup.
        state = reconcile_trash_inventory(current_database_file(), WORKSPACE_PATH)
        if state["entry_count"] or state["directory_count"]:
            raise TrashError("Papierkorb ist noch nicht vollständig leer.")
        databases = {
            Path(str(row["database_path"])).resolve(strict=False)
            for row in list_libraries(
                REGISTRY_DATABASE_FILE,
                active_only=False,
                registered_only=True,
            )
            if Path(str(row["database_path"])).is_file()
        }
        databases.add(current_database_file().resolve(strict=False))
        for database in sorted(databases):
            purge_trash_database(database)
        return api_trash_inventory()
    except (OSError, TrashError, ValueError) as error:
        raise HTTPException(
            status_code=409,
            detail="Papierkorb konnte nicht sicher geleert werden: " + str(error),
        ) from error


@app.get(
    "/workspace",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def workspace_interface() -> HTMLResponse:
    return HTMLResponse(
        content=apply_shell(
            WORKSPACE_HTML,
            active_area="workspace",
            subarea="captures",
        ),
        status_code=200,
    )


@app.get(
    "/events",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def events_interface() -> HTMLResponse:
    return HTMLResponse(
        content=apply_shell(
            EVENTS_HTML,
            active_area="workspace",
            subarea="events",
        ),
        status_code=200,
    )


@app.get(
    "/transfer",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def transfer_interface() -> HTMLResponse:
    return HTMLResponse(
        content=apply_shell(
            TRANSFER_HTML,
            active_area="archive",
        ),
        status_code=200,
    )


def _shell_placeholder_html(message: str = "") -> str:
    body = (
        f'<section class="card" style="margin-top:12px"><p style="margin:0">{message}</p></section>'
        if message
        else ""
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bibliothekar</title>
</head>
<body>
  <main>{body}</main>
</body>
</html>"""


@app.get(
    "/assistant",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def assistant_interface() -> HTMLResponse:
    return HTMLResponse(
        content=apply_shell(
            _shell_placeholder_html(
                "Der KI-Assistent ist in diesem Designstand noch nicht verbunden."
            ),
            active_area="assistant",
        ),
        status_code=200,
    )


@app.get(
    "/metadata-correction",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def metadata_correction_interface(area: str = "library") -> HTMLResponse:
    subarea = area if area in {"library", "general", "multiple"} else "library"
    return HTMLResponse(
        content=apply_shell(
            METADATA_CORRECTION_HTML,
            active_area="metadata",
            subarea=subarea,
        ),
        status_code=200,
    )


@app.get(
    "/files",
    response_class=HTMLResponse,
    tags=["Oberfläche"],
)
def file_browser_interface() -> HTMLResponse:
    return HTMLResponse(
        content=r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <title>Dateiprüfung</title>

  <style>
    :root {
      color-scheme: dark;
      --background: #101114;
      --surface: #191b20;
      --surface-2: #22252b;
      --border: #343842;
      --text: #f2f3f5;
      --muted: #a8adb7;
      --danger: #ff786f;
      --warning: #f2c15f;
      --success: #73d49a;
      --accent: #8ab4ff;
    }

    * {
      box-sizing: border-box;
    }

    html {
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
    }

    body {
      margin: 0;
      background: var(--background);
      color: var(--text);
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
    }

    button,
    select,
    input {
      font: inherit;
    }

    button,
    select,
    input {
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--text);
      padding: 10px 12px;
    }

    button {
      cursor: pointer;
    }

    button:hover {
      border-color: var(--accent);
    }

    button:focus-visible,
    select:focus-visible,
    input:focus-visible {
      outline: 3px solid var(--accent);
      outline-offset: 3px;
    }

    main {
      width: min(1180px, 100%);
      margin: 0 auto;
      padding: 18px;
    }

    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 20px;
    }

    h1,
    h2,
    h3,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 5px;
      font-size: clamp(1.7rem, 5vw, 2.5rem);
    }

    h2 {
      font-size: 1.2rem;
    }

    .muted {
      color: var(--muted);
    }

    .navigation {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .toolbar {
      display: grid;
      grid-template-columns:
        minmax(220px, 1fr)
        minmax(170px, 230px)
        minmax(170px, 230px);
      gap: 10px;
      margin-bottom: 12px;
    }

    label {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    input,
    select {
      width: 100%;
      min-width: 0;
    }

    .job-row {
      display: flex;
      gap: 10px;
      margin-bottom: 18px;
    }

    .job-row select {
      flex: 1 1 auto;
      min-width: 0;
    }

    .status {
      min-height: 24px;
      margin-bottom: 14px;
    }

    .error {
      color: var(--danger);
    }

    .summary {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .summary > * {
      min-width: 0;
    }

    .card {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface);
      padding: 15px;
    }

    .number {
      display: block;
      min-width: 0;
      margin-top: 5px;
      font-size: 1.8rem;
      font-weight: 700;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }

    #summary-job,
    #summary-state {
      font-size: 1rem;
      line-height: 1.35;
    }

    .layout {
      display: grid;
      grid-template-columns:
        minmax(0, 1.25fr)
        minmax(320px, 0.75fr);
      gap: 16px;
    }

    .file-list {
      display: grid;
      gap: 10px;
    }

    .file-button {
      width: 100%;
      min-width: 0;
      text-align: left;
      padding: 14px;
      background: var(--surface);
    }

    .file-button.active {
      border-color: var(--accent);
      background: #202838;
    }

    .file-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }

    .file-main {
      min-width: 0;
    }

    .file-name {
      display: block;
      margin-bottom: 6px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .file-path,
    .family {
      display: block;
      color: var(--muted);
      overflow-wrap: anywhere;
    }

    .family {
      margin-top: 6px;
      font-size: 0.85rem;
    }

    .file-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 7px 13px;
      margin-top: 11px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .badge {
      display: inline-flex;
      width: fit-content;
      flex: 0 0 auto;
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 0.78rem;
      font-weight: 700;
    }

    .high {
      color: var(--success);
    }

    .low {
      color: var(--warning);
    }

    .conflict {
      color: var(--danger);
    }

    .missing {
      color: var(--muted);
    }

    .details {
      position: sticky;
      top: 14px;
      height: fit-content;
    }

    .details p {
      overflow-wrap: anywhere;
    }

    .candidate-list {
      display: grid;
      gap: 10px;
    }

    .candidate {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface-2);
      padding: 12px;
    }

    .candidate.selected {
      border-color: var(--success);
    }

    .candidate.conflicting {
      border-color: var(--danger);
    }

    .candidate-tag {
      margin-bottom: 7px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .candidate-value {
      color: var(--muted);
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 0.85rem;
      overflow-wrap: anywhere;
    }

    .source-device-card { margin:1rem 0; padding:1rem; border:1px solid var(--border); border-radius:14px; background:var(--surface-soft); line-height:1.5; }
    .other-source-panel { margin-top:1rem; }
    .other-source-content { display:grid; gap:.8rem; padding-top:.9rem; }
    .other-source-content h3 { margin:1rem 0 0; font-size:1rem; }
    .folder-browser { display:grid; gap:.7rem; }
    .folder-path { padding:.65rem .8rem; border:1px solid var(--border); border-radius:10px; color:var(--muted); overflow-wrap:anywhere; }
    .folder-list { display:grid; gap:.35rem; max-height:18rem; overflow:auto; }
    .folder-entry { width:100%; text-align:left; }

    .empty {
      border: 1px dashed var(--border);
      border-radius: 14px;
      padding: 22px;
      color: var(--muted);
    }

    @media (max-width: 800px) {
      main {
        padding: 14px;
      }

      header {
        display: block;
      }

      .navigation {
        margin-top: 12px;
      }

      .toolbar {
        grid-template-columns: 1fr;
      }

      .layout {
        grid-template-columns: 1fr;
      }

      .details {
        position: static;
      }

      .summary {
        grid-template-columns:
          repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 430px) {
      main {
        padding: 12px;
      }

      h1 {
        font-size: 1.75rem;
      }

      .job-row {
        display: grid;
        grid-template-columns: 1fr;
      }

      .summary {
        grid-template-columns: 1fr;
      }

      .file-header {
        display: block;
      }

      .file-header .badge {
        margin-top: 9px;
      }

      .navigation {
        display: grid;
        grid-template-columns: 1fr;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
      }
    }
    html, body { background: #090b0d !important; min-height: 100%; }
    body::before { content: ""; position: fixed; inset: -120px 0; background: #090b0d; z-index: -1000; pointer-events: none; }
  
    #refresh-button { display: none !important; }
  </style>
</head>

<body>
  <main>
    <header>
      <div>
        <h1>Dateiprüfung</h1>

        <p class="muted">
          Einzelne Dateien, Dateifamilien und
          Metadaten kontrollieren.
        </p>
      </div>

      <nav
        class="navigation"
        aria-label="Seitennavigation"
      >
        <button type="button" onclick="location.href='/'">
          Importübersicht
        </button>
        <button type="button" onclick="location.href='/workspace'">
          Sortieren
        </button>
      </nav>
    </header>

    <div class="job-row">
      <select
        id="job-select"
        aria-label="Metadatenauftrag auswählen"
      >
        <option value="">
          Aufträge werden geladen …
        </option>
      </select>

      <button
        id="refresh-button"
        type="button"
      >
        Aktualisieren
      </button>
    </div>

    <p
      id="status"
      class="status muted"
      role="status"
      aria-live="polite"
    ></p>

    <section class="summary">
      <div class="card">
        <span class="muted">Auftrag</span>
        <span
          id="summary-job"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Dateien</span>
        <span
          id="summary-files"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Sichtbar</span>
        <span
          id="summary-visible"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Zustand</span>
        <span
          id="summary-state"
          class="number"
        >
          –
        </span>
      </div>
    </section>

    <section
      class="toolbar"
      aria-label="Dateifilter"
    >
      <label>
        <span class="muted">Suche</span>

        <input
          id="search"
          type="search"
          placeholder="Dateiname, Pfad oder Familie"
          autocomplete="off"
        >
      </label>

      <label>
        <span class="muted">Medientyp</span>

        <select id="media-filter">
          <option value="">Alle</option>
          <option value="jpeg">JPEG</option>
          <option value="raw">RAW</option>
          <option value="xmp">XMP</option>
          <option value="video">Video</option>
          <option value="image">Bild</option>
          <option value="other">Sonstige</option>
        </select>
      </label>

      <label>
        <span class="muted">Prüfstatus</span>

        <select id="review-filter">
          <option value="">Alle</option>
          <option value="required">
            Prüfung nötig
          </option>
          <option value="not_required">
            Keine Prüfung nötig
          </option>
        </select>
      </label>
    </section>

    <section class="layout">
      <div>
        <h2>Dateien</h2>

        <div
          id="file-list"
          class="file-list"
        >
          <div class="empty">
            Noch kein Auftrag ausgewählt.
          </div>
        </div>
      </div>

      <aside class="card details">
        <h2>Dateidetails</h2>

        <div id="details">
          <p class="muted">
            Links eine Datei auswählen.
          </p>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const jobSelect =
      document.getElementById("job-select");

    const refreshButton =
      document.getElementById("refresh-button");

    const statusElement =
      document.getElementById("status");

    const searchInput =
      document.getElementById("search");

    const mediaFilter =
      document.getElementById("media-filter");

    const reviewFilter =
      document.getElementById("review-filter");

    const fileListElement =
      document.getElementById("file-list");

    const detailsElement =
      document.getElementById("details");

    const summaryJob =
      document.getElementById("summary-job");

    const summaryFiles =
      document.getElementById("summary-files");

    const summaryVisible =
      document.getElementById("summary-visible");

    const summaryState =
      document.getElementById("summary-state");

    let jobs = [];
    let files = [];
    let activeFileId = null;


    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }


    function setStatus(
      message,
      isError = false
    ) {
      statusElement.textContent = message;
      statusElement.classList.toggle(
        "error",
        isError
      );
    }


    function formatDate(value) {
      if (!value) {
        return "Kein Datum ermittelt";
      }

      const date = new Date(value);

      if (Number.isNaN(date.getTime())) {
        return value;
      }

      return new Intl.DateTimeFormat(
        "de-DE",
        {
          dateStyle: "medium",
          timeStyle: "medium"
        }
      ).format(date);
    }


    function formatJobLabel(job) {
      const title =
        job?.operation === "metadata_fixture_analysis"
          ? "Metadaten-Testbestand"
          : (
              job?.source_volume_label
              || "SD-Kartenimport"
            );

      if (!job?.created_at) {
        return title;
      }

      const date = new Date(job.created_at);

      if (Number.isNaN(date.getTime())) {
        return title;
      }

      const timestamp = new Intl.DateTimeFormat(
        "de-DE",
        {
          dateStyle: "short",
          timeStyle: "medium"
        }
      ).format(date);

      return `${title} · ${timestamp}`;
    }


    function stateLabel(value) {
      const labels = {
        queued: "Wartet",
        copying: "Wird kopiert",
        verifying: "Wird geprüft",
        backup_verified: "Sicherung bestätigt",
        analyzing_metadata: "Metadatenanalyse",
        waiting_for_review: "Prüfung nötig",
        organizing: "Wird sortiert",
        completed: "Abgeschlossen",
        failed: "Fehlgeschlagen",
        interrupted: "Unterbrochen"
      };

      return labels[value] || value || "unbekannt";
    }


    function confidenceLabel(value) {
      const labels = {
        high: "sicher",
        medium: "mittel",
        low: "unsicher",
        conflict: "Konflikt",
        missing: "fehlend"
      };

      return labels[value] || value || "unbekannt";
    }


    function mediaTypeLabel(value) {
      const labels = {
        jpeg: "JPEG",
        raw: "RAW",
        xmp: "XMP",
        video: "Video",
        image: "Bild",
        other: "Sonstige"
      };

      return labels[value] || value || "unbekannt";
    }


    async function getJson(url) {
      const response = await fetch(url);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Anfrage fehlgeschlagen."
        );
      }

      return data;
    }


    async function loadJobs() {
      // Liste und Zähler als gemeinsame frische Ansicht laden: keine Cache-Zahl 0/1.
      const requestId = ++importHistoryRequestId;
      const openDetails = openJobDetailKeys();
      const [data, hiddenCount] = await Promise.all([
        requestHistoryPages(false, jobHistoryLimit),
        loadHiddenCount()
      ]);
      if(requestId !== importHistoryRequestId) return;
      const previous = new Map(jobHistoryJobs.map(job => [String(job.id), job.state]));
      jobHistoryJobs = data.jobs || [];
      jobHistoryTotal = Number(data.total || 0);
      hiddenHistoryTotal = hiddenCount;
      for(const job of jobHistoryJobs) {
        const id = String(job.id);
        const old = previous.get(id);
        if(old && old !== "completed" && job.state === "completed") openHistoryIds.delete(id);
        else if(!seenHistoryStates.has(id) && job.state !== "completed") openHistoryIds.add(id);
        seenHistoryStates.set(id, job.state);
      }
      // Die Schublade bleibt auch bei null sichtbaren Importen erreichbar.
      renderJobHistory(openDetails);
    }

    async function refreshAll({forceSources=false}={}) {
      refreshButton.disabled = true;
      refreshButton.classList.add("bk-busy");
      refreshButton.setAttribute("aria-busy", "true");
      noticeElement.classList.add("bk-loading-status");
      noticeElement.textContent = "Import & Prüfung wird aktualisiert …";

      try {
        await Promise.all([
          loadHealth(),
          loadSources({forceRefresh:forceSources}),
          loadJobs(),
          loadSourceDevices(),
          loadFolderBrowser().catch(() => null)
        ]);

        noticeElement.textContent =
          "Zuletzt aktualisiert: "
          + new Date().toLocaleTimeString(
            "de-DE"
          );
      } catch (error) {
        noticeElement.textContent =
          error.message;

        noticeElement.classList.add(
          "error-text"
        );
      } finally {
        refreshButton.disabled = false;
        refreshButton.classList.remove("bk-busy");
        refreshButton.removeAttribute("aria-busy");
        noticeElement.classList.remove("bk-loading-status");
      }
    }

    sdMountButton.addEventListener("click", async () => {
      if (!selectedSdDevice) return;
      sdMountButton.disabled = true;
      try {
        const device = await mountDevice(selectedSdDevice.device_path);
        selectedSdDevice = device;
        noticeElement.textContent = "SD-Karte wurde ausschließlich lesend eingebunden.";
      } catch (error) { showError(error); }
    });

    sdUnmountButton.addEventListener("click", async () => {
      if (!selectedSdDevice) return;
      sdUnmountButton.disabled = true;
      try { await unmountDevice(selectedSdDevice.device_path); noticeElement.textContent = "SD-Karte wurde sicher ausgeworfen."; }
      catch (error) { showError(error); }
    });

    sdImportButton.addEventListener("click", async () => {
      const source = mountedSourceForDevice(selectedSdDevice);
      if (!source) { showError(new Error("Auf der eingebundenen SD-Karte wurde noch keine geeignete Kartenwurzel erkannt.")); return; }
      sourceSelect.value = source.root_key + "::" + source.relative_path;
      updateSourceDetail();
      await startFolderImportSelection(
        source.root_key,
        source.relative_path,
        "",
        "sd_card"
      );
    });

    deviceSelect.addEventListener("change", () => {
      driveFolderBrowser.hidden = true;
      driveFolderBoundary = null;
      updateDriveControls();
    });

    deviceMountButton.addEventListener("click", async () => {
      if (!deviceSelect.value) return;
      const selectedPath = deviceSelect.value;
      deviceMountButton.disabled = true;
      try {
        await mountDevice(selectedPath);
        deviceSelect.value = selectedPath;
        updateDriveControls();
        noticeElement.textContent = "Externes Laufwerk wurde ausschließlich lesend eingebunden.";
      } catch (error) { showError(error); }
    });

    deviceUnmountButton.addEventListener("click", async () => {
      const device = currentExternalDevice();
      if (!device?.mounted) return;
      deviceUnmountButton.disabled = true;
      try {
        await unmountDevice(device.device_path);
        driveFolderBrowser.hidden = true;
        driveFolderBoundary = null;
        noticeElement.textContent = "Externes Laufwerk wurde sicher ausgeworfen.";
      } catch (error) { showError(error); }
    });

    deviceImportButton.addEventListener("click", async () => {
      const device = currentExternalDevice();
      if (!device?.mounted || !device?.read_only || !device.device_id) {
        showError(new Error("Bitte das externe Laufwerk zuerst ausschließlich lesend einbinden."));
        return;
      }
      await startFolderImportSelection(
        "removable",
        device.device_id,
        device.label || device.model || "Externes Laufwerk",
        "drive"
      );
    });

    deviceFolderButton.addEventListener("click", async () => {
      const device = currentExternalDevice();
      if (!device?.mounted || !device?.read_only || !device.device_id) {
        showError(new Error("Bitte das externe Laufwerk zuerst ausschließlich lesend einbinden."));
        return;
      }
      driveFolderBoundary = device.device_id;
      driveFolderBrowser.hidden = false;
      try {
        await loadDriveFolderBrowser(driveFolderBoundary);
        driveFolderBrowser.scrollIntoView({behavior:"smooth", block:"nearest"});
      } catch (error) {
        showError(error);
      }
    });

    driveFolderUpButton.addEventListener("click", () => {
      if (driveFolderParent !== null) {
        loadDriveFolderBrowser(driveFolderParent).catch(showError);
      }
    });

    driveFolderImportButton.addEventListener("click", async () => {
      const device = currentExternalDevice();
      if (!device?.mounted || !device?.read_only || !driveFolderPathValue) {
        showError(new Error("Bitte zuerst einen Ordner im eingebundenen Laufwerk auswählen."));
        return;
      }
      const leaf = driveFolderPathValue.split("/").filter(Boolean).at(-1) || "Ordner";
      await startFolderImportSelection(
        "removable",
        driveFolderPathValue,
        leaf,
        "folder"
      );
    });

    folderRootSelect.addEventListener("change", () => loadFolderBrowser(folderRootSelect.value, ".").catch(showError));
    folderUpButton.addEventListener("click", () => {
      if (currentFolderParent !== null) loadFolderBrowser(currentFolderRoot, currentFolderParent).catch(showError);
    });
    folderImportButton.addEventListener("click", async () => {
      const selected = currentFolderRoot + "::" + currentFolderPath;
      sourceSelect.innerHTML += `<option value="${escapeHtml(selected)}">${escapeHtml(currentFolderPath)}</option>`;
      sourceSelect.value = selected;
      const leaf = currentFolderPath.split("/").filter(Boolean).at(-1) || "Sicherungsordner";
      await startFolderImportSelection(currentFolderRoot, currentFolderPath, leaf, "folder");
    });

    sourceSelect.addEventListener("change", updateSourceDetail);

    async function startFolderImportSelection(rootKey, relativePath, displayName="", sourceMode="folder") {
      if (!rootKey || !relativePath) {
        noticeElement.textContent = "Bitte zuerst eine Importquelle auswählen.";
        noticeElement.classList.add("error-text");
        return;
      }

      importButton.disabled = true;
      importButton.classList.add("bk-busy");
      importButton.setAttribute("aria-busy", "true");
      deviceImportButton.disabled = true;
      driveFolderImportButton.disabled = true;
      noticeElement.classList.remove("error-text");
      noticeElement.classList.add("bk-loading-status");
      noticeElement.textContent = "Ordnerimport wird angelegt …";

      try {
        const response = await fetch(
          "/api/jobs/folder-import",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_root_key: rootKey,
              source_relative_path: relativePath,
              display_name: displayName || undefined,
              source_mode: sourceMode
            })
          }
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(
            data.detail || "Ordnerimport konnte nicht gestartet werden."
          );
        }
        noticeElement.textContent = "Ordnerimport wurde angenommen.";
        await loadJobs();
      } catch (error) {
        noticeElement.textContent = error.message;
        noticeElement.classList.add("error-text");
      } finally {
        await Promise.all([loadSources(), loadSourceDevices()]);
        updateDriveControls();
        importButton.classList.remove("bk-busy");
        importButton.removeAttribute("aria-busy");
        noticeElement.classList.remove("bk-loading-status");
      }
    }

    async function startFolderImport() {
      const selected = sourceSelect.value;
      if (!selected) {
        noticeElement.textContent = "Bitte zuerst eine Importquelle auswählen.";
        noticeElement.classList.add("error-text");
        return;
      }
      const separator = selected.indexOf("::");
      const rootKey = separator >= 0 ? selected.slice(0, separator) : "saved";
      const relativePath = separator >= 0 ? selected.slice(separator + 2) : selected;
      await startFolderImportSelection(rootKey, relativePath);
    }

    importButton.addEventListener(
      "click",
      startFolderImport
    );

    sourceSelect.addEventListener(
      "change",
      updateSourceDetail
    );

    refreshButton.addEventListener(
      "click",
      () => refreshAll({forceSources:true})
    );

    refreshAll().catch(showError);

    // Nur aktive Vorgänge benötigen eine laufende Fortschrittsanzeige.
    window.setInterval(() => {
      if(document.hidden)return;
      const active=jobHistoryJobs.some(job => !["completed","failed","interrupted"].includes(job.state));
      if(active || Date.now()-lastImportHistoryPoll>60000){
        lastImportHistoryPoll=Date.now();loadJobs().catch(showError);
      }
    }, 2000);

    window.setInterval(
      loadHealth,
      15000
    );
  </script>
</body>
</html>
""", active_area="import")


@app.get(
    "/healthz",
    include_in_schema=False,
)
def healthz() -> JSONResponse:
    health = get_health()

    status_code = (
        200
        if health["status"] == "ok"
        else 503
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "status": health["status"],
        },
    )

# ─────────────────────────────────────────────────────────────────
# Neu-Zuordnung herausfallender Familien (0.16.3)
# ─────────────────────────────────────────────────────────────────


@app.get("/api/jobs/{job_id}/events/{event_id}/reassignments")
def api_list_event_reassignments(job_id: str, event_id: str) -> JSONResponse:
    try:
        from app.event_reassignment import list_event_reassignments, EventReassignmentError
        result = list_event_reassignments(current_database_file(), job_id, event_id)
        return JSONResponse(content=result)
    except EventReassignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/jobs/{job_id}/events/{event_id}/reassignments")
def api_assign_event_reassignments(job_id: str, event_id: str, body: dict) -> JSONResponse:
    try:
        from app.event_reassignment import assign_event_reassignments, EventReassignmentError
        result = assign_event_reassignments(
            current_database_file(), job_id, event_id, body.get("family_ids") or [],
            target_mode=str(body.get("target_mode") or ""),
            target_event_id=body.get("target_event_id"),
            new_event_name=body.get("new_event_name"),
            segments=body.get("segments") or [],
            preserve_day_folders=bool(body.get("preserve_day_folders", False)),
        )
        return JSONResponse(content=result)
    except EventReassignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────
# Change-Request-Workflow (0.16.0) — Archivierte Ereignisse bearbeiten
# ─────────────────────────────────────────────────────────────────


@app.get("/api/change-requests")
def api_list_change_requests(
    job_id: str = "",
    event_id: str | None = None,
    status: str | None = None,
) -> JSONResponse:
    """Aenderungsauftraege auflisten."""
    try:
        requests = list_event_change_requests(
            current_database_file(), job_id,
            event_id=event_id, status=status,
        )
        return JSONResponse(content={"requests": requests})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/change-requests/{cr_id}")
def api_get_change_request(cr_id: str) -> JSONResponse:
    """Aenderungsauftrag lesen."""
    cr = get_event_change_request(current_database_file(), cr_id)
    if cr is None:
        raise HTTPException(status_code=404, detail="ChangeRequest nicht gefunden.")
    return JSONResponse(content=cr)


@app.get("/api/change-requests/{cr_id}/assistant")
def api_get_change_request_assistant(
    cr_id: str,
    refresh: bool = False,
) -> JSONResponse:
    """Kompakter Archivassistent; refresh scannt den realen Bestand read-only."""
    try:
        context = current_library_context()
        archive_label = (
            "Kamerabibliothek"
            if context.is_main
            else (context.archive_root.name or "Kamerabibliothek")
        )
        work_label = context.work_root.name or "Arbeitsbereich"
        return JSONResponse(content=build_archive_change_assistant(
            current_database_file(),
            current_archive_root(),
            current_workspace_root(),
            cr_id,
            scan_live=bool(refresh),
            archive_display_root=archive_label,
            work_display_root=work_label,
            backup_display_root=BACKUP_DIRECTORY_NAME,
        ))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/change-requests/{cr_id}/files")
def api_get_change_request_files(cr_id: str) -> JSONResponse:
    """Datei-Bestaetigungen eines Aenderungsauftrags."""
    files = get_event_change_files(current_database_file(), cr_id)
    return JSONResponse(content=files)


@app.get("/api/change-requests/{cr_id}/preview")
def api_get_change_request_preview(cr_id: str) -> JSONResponse:
    """Vorschau der Aenderung (alte/neue Pfade) fuer einen ChangeRequest."""
    try:
        cr = get_event_change_request(current_database_file(), cr_id)
        if cr is None:
            raise HTTPException(status_code=404, detail="ChangeRequest nicht gefunden.")

        # Hole Event-Details via get_event_edit_context
        try:
            ctx = get_event_edit_context(current_database_file(), cr["job_id"], cr["event_id"])
            event = ctx.get("event")
        except Exception:
            event = {"id": cr["event_id"], "name": "Unbekannt"}

        if event is None:
            event = {"id": cr["event_id"], "name": "Unbekannt"}

        # Berechne den neuen Zustand via build_event_preview
        from app.event_structure import build_event_preview
        try:
            preview_data = {
                "parent_folder": cr["parent_folder"],
                "child_folder": cr["child_folder"],
                "uses_time_range": bool(cr["uses_time_range"]),
                "preserve_day_folders": bool(cr["preserve_day_folders"]),
                "start_date": cr["start_date"],
                "end_date": cr["end_date"],
                "start_time": cr["start_time"],
                "end_time": cr["end_time"],
                "selected_day_keys": json.loads(cr["selected_day_keys"]) if cr["selected_day_keys"] else [],
                "selected_family_ids": json.loads(cr["selected_family_ids"]) if cr["selected_family_ids"] else [],
            }
            structure_result = build_event_preview(preview_data, [])
            structure_lines = structure_result.get("structure_lines", [])
        except Exception:
            structure_lines = ["Berechnung fehlgeschlagen"]

        file_reviews = get_event_change_files(current_database_file(), cr_id)

        # Vergleiche old/new Pfade mit den file_reviews
        diff_entries = []
        for fr in file_reviews:
            if fr["action"] in ("move", "delete"):
                diff_entries.append({
                    "family_id": fr["family_id"],
                    "old_path": fr["old_path"],
                    "new_path": fr["new_path"],
                    "action": fr["action"],
                    "confirmed": bool(fr["confirmed"]),
                })

        return JSONResponse(content={
            "event_id": event["id"],
            "event_name": event["name"],
            "structure_lines": structure_lines,
            "diff": diff_entries,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/change-requests/{event_id}/propose")
def api_propose_event_change(
    event_id: str,
    body: dict,
    job_id: str,
) -> JSONResponse:
    """Aenderungsauftrag fuer ein archiviertes Ereignis vorschlagen."""
    try:
        # 0.28.3: Auch ein archivierter Editor-Auftrag trägt die aktuell
        # konfigurierte Ordnerdefinition mit. create_subfolders aus dem
        # Formular darf structure_enabled dabei gezielt übersteuern.
        body = _event_payload_with_folder_layout(body, event_id=event_id)
        preview = body.get("preview")
        if isinstance(preview, dict):
            preview = _event_payload_with_folder_layout(preview, event_id=event_id)
        from app.database import get_event_edit_context
        # Archivänderungen werden unmittelbar vor der Planung noch einmal aus
        # dem realen Bibliotheksordner inventarisiert. Dadurch basiert die
        # Zeit-/Dateiauswahl nicht auf einem möglicherweise älteren Editor-
        # Snapshot oder nur auf historischen SQLite-Aufnahmezeiten.
        refresh_live_event_inventories(
            current_database_file(),
            current_workspace_root(),
            current_archive_root(),
            job_id=job_id,
            event_id=event_id,
        )
        ctx = get_event_edit_context(current_database_file(), job_id, event_id, workspace_path=current_workspace_root())
        if not preview and body.get("start_date") and body.get("end_date"):
            editable_families = [
                {
                    "family_id": int(f["family_id"]),
                    "family_key": f["family_key"],
                    "selected_capture_time": f["selected_capture_time"],
                    "capture_time_confidence": f["capture_time_confidence"],
                    "day_key": f["day_key"],
                    "has_date": f["has_date"],
                    "file_count": int(f["file_count"]),
                    "total_size_bytes": int(f["total_size_bytes"]),
                    "review_required_count": int(f["review_required_count"]),
                }
                for f in ctx["families"]
                if not f["assigned_elsewhere"] or f["assigned_here"]
            ]
            edit_body = _event_edit_payload_within_new_range(body, editable_families)
            preview = build_event_preview(edit_body, editable_families)
        elif not preview:
            ev = ctx.get("event", {})
            child = ctx.get("child_event")
            sd = str(ev.get("start_datetime") or "")[:10]
            ed = str(ev.get("end_datetime") or "")[:10]
            uses_time_range = bool(ev.get("uses_time_range"))
            start_time = "00:00"
            end_time = "23:59"
            if uses_time_range and child:
                start_time = str(child.get("start_datetime") or "")[11:16] or "00:00"
                end_time = str(child.get("end_datetime") or "")[11:16] or "23:59"
            preview = {
                "event_kind": str(ev.get("event_kind") or "event"),
                "event_name": str(ev.get("name") or ""),
                "parent_folder": str(ev.get("folder_name") or ev.get("name") or ""),
                "child_folder": str(child.get("folder_name") or "") if child else "",
                "child_event_name": str(child.get("name") or "") if child else "",
                "uses_time_range": uses_time_range,
                "preserve_day_folders": bool(ev.get("preserve_day_folders", 1)),
                "start_date": sd,
                "end_date": ed,
                "start_time": start_time,
                "end_time": end_time,
                "selected_day_keys": [],
                "selected_family_ids": ctx.get("assigned_family_ids", []),
                "selected_file_count": sum(int(f.get("file_count") or 0) for f in ctx.get("families", []) if f.get("assigned_here")),
                "selected_family_count": len(ctx.get("assigned_family_ids", [])),
            }
        # Nur dieser direkte Archiv-Editor darf das per-event Layout
        # verändern. Automatische Archiv-Erweiterungen behalten ihren bisherigen
        # Layoutzustand und setzen dieses Kennzeichen bewusst nicht.
        preview["_folder_layout_explicit"] = True
        archive_reservation = _reserve_archive_change_preview(
            event_id,
            preview,
        )
        try:
            result = propose_event_change(
                current_database_file(), job_id, event_id, preview,
                event_name=body.get("event_name") or preview.get("event_name"),
                notes=body.get("notes", ""),
                archive_root=current_archive_root(),
                workspace_path=current_workspace_root(),
            )
        except Exception:
            _release_new_global_reservations(archive_reservation)
            raise
        return JSONResponse(content=result, status_code=201)
    except LibraryRegistryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EventChangeRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/change-requests/{cr_id}/reassignments")
def api_change_request_reassignments(cr_id: str):
    try:
        return list_archive_reassignments(current_database_file(), cr_id)
    except ArchiveReassignmentError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/change-requests/{cr_id}/reassignments")
def api_change_request_reassignments_assign(cr_id: str, payload: dict[str, Any]):
    raise HTTPException(
        status_code=409,
        detail=(
            "Direkte Neu-Zuordnung innerhalb einer Archivänderung ist deaktiviert. "
            "Freigewordene Archivdateien werden zuerst sicher in den SSD-Arbeitsbereich zurückgeholt "
            "und nach Abschluss über „Aufnahmen“ neu zugeordnet."
        ),
    )


@app.post("/api/change-requests/{cr_id}/confirm")
def api_confirm_change(cr_id: str, body: dict[str, Any] | None = None) -> JSONResponse:
    """Aenderungsauftrag bestaetigen."""
    try:
        payload = body or {}
        transfer_mode = str(payload.get("transfer_mode") or "").strip() or None
        if transfer_mode not in {None, "copy", "move"}:
            raise EventChangeApplyError("Ungültige Transferauswahl.")
        result = confirm_event_change(
            current_database_file(),
            cr_id,
            current_archive_root(),
            current_workspace_root(),
            transfer_mode=transfer_mode,
        )
        return JSONResponse(content=result)
    except EventChangeApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/change-requests/{cr_id}/cancel")
def api_cancel_change(cr_id: str) -> JSONResponse:
    """Aenderungsauftrag abbrechen."""
    try:
        change_request = get_event_change_request(current_database_file(), cr_id)
        if change_request is None:
            raise EventChangeApplyError("ChangeRequest nicht gefunden.")
        selected_ids = _change_request_selected_family_ids(change_request)
        assigned_ids = _assigned_family_ids_for_root_event(
            str(change_request["event_id"])
        )
        result = cancel_event_change(
            current_database_file(), cr_id, current_archive_root(), current_workspace_root()
        )
        release_family_ids_claims(
            REGISTRY_DATABASE_FILE,
            database_path=current_database_file(),
            library_id=current_library_context().library_id,
            family_ids=selected_ids - assigned_ids,
            allowed_states={"reserved"},
        )
        return JSONResponse(content=result)
    except EventChangeApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/change-requests/{cr_id}/reversal")
def api_get_change_reversal(cr_id: str, refresh: bool = False) -> JSONResponse:
    try:
        from app.archive_reversal import build_archive_reversal_assistant
        context = current_library_context()
        archive_label = (
            "Kamerabibliothek"
            if context.is_main
            else (context.archive_root.name or "Kamerabibliothek")
        )
        work_label = context.work_root.name or "Arbeitsbereich"
        return JSONResponse(content=build_archive_reversal_assistant(
            current_database_file(),
            current_archive_root(),
            current_workspace_root(),
            cr_id,
            scan_live=bool(refresh),
            archive_display_root=archive_label,
            work_display_root=work_label,
        ))
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/reversal/prepare")
def api_prepare_change_reversal(cr_id: str) -> JSONResponse:
    try:
        from app.archive_reversal import prepare_archive_reversal
        context = current_library_context()
        archive_label = (
            "Kamerabibliothek"
            if context.is_main
            else (context.archive_root.name or "Kamerabibliothek")
        )
        work_label = context.work_root.name or "Arbeitsbereich"
        return JSONResponse(content=prepare_archive_reversal(
            current_database_file(),
            current_archive_root(),
            current_workspace_root(),
            cr_id,
            archive_display_root=archive_label,
            work_display_root=work_label,
        ))
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/reversal/verify")
def api_verify_change_reversal(cr_id: str) -> JSONResponse:
    try:
        from app.archive_reversal import verify_archive_reversal
        return JSONResponse(content=verify_archive_reversal(
            current_database_file(), current_archive_root(), current_workspace_root(), cr_id
        ))
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/reversal/finish")
def api_finish_change_reversal(cr_id: str) -> JSONResponse:
    try:
        from app.archive_reversal import finish_archive_reversal
        return JSONResponse(content=finish_archive_reversal(
            current_database_file(), current_archive_root(), current_workspace_root(), cr_id
        ))
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/release-copy/create")
def api_create_archive_release_copy(cr_id: str) -> JSONResponse:
    """Freigewordene Archivdateien nach ausdrücklicher Freigabe auf die SSD kopieren."""
    try:
        from app.archive_release_copy import create_archive_release_copies
        result = create_archive_release_copies(
            current_database_file(), current_archive_root(), current_workspace_root(), cr_id
        )
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/release-copy/verify")
def api_verify_archive_release_copy(cr_id: str) -> JSONResponse:
    """Freigewordene Archivdateien auf der SSD gegen gespeicherte SHA-256 prüfen."""
    try:
        from app.archive_release_stock import verify_archive_release_copies
        result = verify_archive_release_copies(
            current_database_file(), current_archive_root(), current_workspace_root(), cr_id
        )
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/release-removal/verify")
def api_verify_archive_release_removal(cr_id: str) -> JSONResponse:
    """Nach bestätigter SSD-Kopie prüfen, dass die Archivoriginale entfernt wurden."""
    try:
        from app.archive_release_stock import verify_archive_release_removal
        result = verify_archive_release_removal(
            current_database_file(), current_archive_root(), current_workspace_root(), cr_id
        )
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/change-requests/{cr_id}/verify")
def api_verify_change(cr_id: str) -> JSONResponse:
    """Manuelle Archivänderung rein lesend gegen die Kamerabibliothek prüfen."""
    try:
        result = verify_event_change(
            current_database_file(), cr_id, current_archive_root(), current_workspace_root()
        )
        return JSONResponse(content=result)
    except EventChangeApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/change-requests/{cr_id}/archive")
def api_archive_change(cr_id: str) -> JSONResponse:
    """Geprüften manuellen Änderungsauftrag abschließen; Archiv bleibt read-only."""
    try:
        change_request = get_event_change_request(current_database_file(), cr_id)
        if change_request is None:
            raise EventChangeApplyError("ChangeRequest nicht gefunden.")
        event_id = str(change_request["event_id"])
        selected_ids = _change_request_selected_family_ids(change_request)
        previously_assigned = _assigned_family_ids_for_root_event(event_id)
        result = finish_event_change(
            current_database_file(), cr_id, current_archive_root(), current_workspace_root()
        )
        if selected_ids:
            _promote_global_family_ids_owned(
                event_id,
                selected_ids,
            )
        removed_ids = previously_assigned - selected_ids
        if removed_ids:
            release_family_ids_claims(
                REGISTRY_DATABASE_FILE,
                database_path=current_database_file(),
                library_id=current_library_context().library_id,
                family_ids=removed_ids,
                allowed_states={"owned", "reserved"},
            )
        backfill_library_claims(
            REGISTRY_DATABASE_FILE,
            database_path=current_database_file(),
            library_id=current_library_context().library_id,
        )
        synchronize_global_central_stock()
        return JSONResponse(content=result)
    except EventChangeApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
