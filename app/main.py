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
from app.trash_restore import restore_trash_files
from app.trash import (
    TRASH_CONFIRMATION, TrashError, reconcile_trash_inventory,
    empty_trash_filesystem, purge_trash_database,
)
from app.ui_shell import apply_shell
from app import view_cache
from app import background_mutation_cancel as cancel_queue
from app.background_activity import current_activity
from app import ssd_release_background as release_queue
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
    ENGLISH_NEW_INSTALL_SETTING,
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
    PipelineError,
    recover_cross_device_protocol_failures,
    run_simulated_job,
    sha256_file,
)
from app.folder_import import (
    ImportCancelled,
    cleanup_completed_folder_import,
    run_folder_import_job,
    quick_source_signature,
    preflight_folder_import,
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
from app.archive_change_assistant import build_archive_change_assistant
from app.archive_reassignment import (
    list_archive_reassignments,
    assign_archive_reassignments,
    ArchiveReassignmentError,
)


APP_VERSION = __version__
RELEASE_VERSION = "0.53.1"
DEPLOYMENT_VERSION = "0.53.1"

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


def _import_cancel_marker(job_id: str, *, force: bool = False) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", str(job_id)):
        raise ValueError("Ungültige Importkennung.")
    suffix = ".force" if force else ".cancel"
    return LOG_PATH / "import-cancellations" / (str(job_id) + suffix)


def _request_import_cancel(job_id: str, *, force: bool = False) -> None:
    # Dauerhafte, jobspezifische Anforderung: auch nach einem HTTP-Reload
    # oder Workerwechsel sichtbar. Der Job-Worker allein führt den Rollback aus.
    marker = _import_cancel_marker(job_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker.open("x", encoding="utf-8") as handle:
            handle.write(datetime.now(timezone.utc).isoformat())
    except FileExistsError:
        pass
    if force:
        escalation = _import_cancel_marker(job_id, force=True)
        try:
            with escalation.open("x", encoding="utf-8") as handle:
                handle.write(datetime.now(timezone.utc).isoformat())
        except FileExistsError:
            pass
    with IMPORT_CANCEL_LOCK:
        IMPORT_CANCEL_REQUESTS.add(str(job_id))


def _import_cancel_requested(job_id: str) -> bool:
    marker = _import_cancel_marker(job_id)
    if marker.is_file():
        return True
    with IMPORT_CANCEL_LOCK:
        return str(job_id) in IMPORT_CANCEL_REQUESTS


def _import_cancel_info(job_id: str) -> dict[str, Any]:
    marker = _import_cancel_marker(job_id)
    if not marker.is_file():
        return {"cancel_requested": False, "cancel_forced": False}
    return {
        "cancel_requested": True,
        "cancel_forced": _import_cancel_marker(job_id, force=True).is_file(),
        "cancel_requested_at": datetime.fromtimestamp(
            marker.stat().st_mtime, timezone.utc
        ).isoformat(),
    }


def _clear_import_cancel(job_id: str) -> None:
    with IMPORT_CANCEL_LOCK:
        IMPORT_CANCEL_REQUESTS.discard(str(job_id))
    for force in (False, True):
        _import_cancel_marker(job_id, force=force).unlink(missing_ok=True)


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
    from app.ui_i18n import I18N_UI_JS
    workspaces_root = str(
        storage_paths(WORKSPACE_PATH)["workspaces_root"]
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekar · Set up library</title>
<script src="/auth/client.js"></script>
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
    return html.replace("</body>", f"<script>{I18N_UI_JS}</script></body>")


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
        "trash_import",
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
            managed_trash_import = operation == "trash_import"
            managed_metadata_import = managed_multiple_import or managed_general_import or managed_trash_import
            if managed_trash_import:
                from app.trash_import import stage_parent
                expected_trash_root = stage_parent(workspace_path)
                resolved_source = source.resolve(strict=False)
                if resolved_source.parent != expected_trash_root or resolved_source.is_symlink() or resolved_source.name != job_id:
                    raise RuntimeError("Unerwarteter Papierkorb-Stagingordner.")
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
            if managed_multiple_import or managed_general_import:
                start_day=str(organization.get("capture_start_date") or "")
                end_day=str(organization.get("capture_end_date") or "")
                origin=("Mehrfachkorrektur" if managed_multiple_import
                        else "Metadatenkorrektur · Allgemein")
                if start_day:
                    origin += " · " + start_day + (
                        " – " + end_day if end_day and end_day != start_day else ""
                    )
                set_job_source_volume_label(database_file,job_id,origin)
            if managed_trash_import:
                from app.trash_import import cleanup_successful_trash_import
                try:
                    result["trash_source_cleanup"] = cleanup_successful_trash_import(
                        workspace_path, job_id,
                        list((result.get("organization") or {}).get("imported_source_files") or []),
                    )
                except (OSError, ValueError, RuntimeError) as cleanup_error:
                    result["trash_source_cleanup"] = {"warning":str(cleanup_error)}
                time_start=str(organization.get("capture_start_date") or "")
                time_end=str(organization.get("capture_end_date") or "")
                source_label="Aus Papierkorb"
                if time_start:
                    source_label += " · " + time_start + (" – " + time_end if time_end and time_end != time_start else "")
                set_job_source_volume_label(database_file,job_id,source_label)
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
                    else "Ausgewählte Papierkorb-Dateien wurden in den Tagesbestand übernommen."
                    if managed_trash_import
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


RELEASE_WORKER_STOP = Event()
RELEASE_WORKER_WAKE = Event()
RELEASE_WORKER_THREAD: Thread | None = None


def process_background_release() -> bool:
    """Claim one persisted SSD release without relying on an HTTP connection."""
    for context in list_active_library_contexts(REGISTRY_DATABASE_FILE):
        ensure_library_database_schema(context)
        task = release_queue.claim_release(context.database_path)
        if task is None:
            continue
        release_queue.process_release(
            context.database_path, compatibility_workspace_root(context),
            context.archive_root, task,
        )
        return True
    return False


def release_worker_loop() -> None:
    while not RELEASE_WORKER_STOP.is_set():
        try:
            while not RELEASE_WORKER_STOP.is_set() and process_background_release():
                pass
        except Exception as error:
            print("SSD-Freigabeworker fehlgeschlagen:", error, flush=True)
        RELEASE_WORKER_WAKE.wait(3.0)
        RELEASE_WORKER_WAKE.clear()


def start_release_worker() -> None:
    global RELEASE_WORKER_THREAD
    RELEASE_WORKER_STOP.clear()
    if RELEASE_WORKER_THREAD is None or not RELEASE_WORKER_THREAD.is_alive():
        RELEASE_WORKER_THREAD = Thread(
            target=release_worker_loop,
            name="bibliothekar-ssd-release-worker",
            daemon=True,
        )
        RELEASE_WORKER_THREAD.start()
    RELEASE_WORKER_WAKE.set()


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
            if global_import is None:
                global_import = claim_next_job(
                    DATABASE_FILE,
                    operation="trash_import",
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
        main_database_was_new = not DATABASE_FILE.is_file() or DATABASE_FILE.stat().st_size == 0
        DATABASE_INITIALIZATION = initialize_database(
            DATABASE_FILE
        )
        # Provision English event-folder names only for a genuinely new database.
        # Existing databases and saved per-event layouts retain their exact paths.
        if main_database_was_new:
            with database_connection(DATABASE_FILE) as connection:
                set_global_event_folder_layout(
                    connection, ENGLISH_NEW_INSTALL_SETTING,
                    updated_at=datetime.now(timezone.utc).isoformat(),
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
            start_release_worker()
            return

        if existing_main is not None:
            # BA-02: Resume/rollback crash-interrupted backup deletions
            # BEFORE global projections and the import worker start.
            from app.backup_management import recover_backup_deletions
            deletion_recovery = recover_backup_deletions(
                DATABASE_FILE, REGISTRY_DATABASE_FILE,
                workspace_backup_root(WORKSPACE_PATH),
            )
            if deletion_recovery["blocked"]:
                raise BackupDeletionError(
                    "Unterbrochene Sicherungslöschung muss geprüft werden: "
                    + " | ".join(deletion_recovery["errors"][:5])
                )
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
            release_queue.recover_releases(context.database_path)
            # BA-01: Repair portable event.json files from committed SQLite
            # outbox rows before accepting new background mutations.
            try:
                from app.event_document_sync import recover_event_document_sync_tasks
                document_repairs = recover_event_document_sync_tasks(
                    context.database_path, context.workspace_root,
                    app_version=APP_VERSION,
                )
                if document_repairs["blocked"]:
                    print(
                        "Ereignisdokument-Wiederherstellung nicht vollständig: "
                        f"{document_repairs['blocked']} offene Aufgaben in "
                        f"Bibliothek {context.library_id}.",
                        flush=True,
                    )
            except Exception as document_error:
                print(
                    f"Fehler bei der Ereignisdokument-Wiederherstellung "
                    f"({context.library_id}): {document_error}",
                    flush=True,
                )

        # BA-12: physical metadata swaps must be reconciled BEFORE a
        # background worker or new correction can touch any file. Fail closed
        # on foreign/ambiguous bytes, never overwrite them heuristically.
        from app.metadata_swap_recovery import recover_metadata_swaps
        from app.storage_config import storage_paths as metadata_storage_paths
        metadata_db_allowlist = {DATABASE_FILE}
        metadata_db_allowlist.update(
            Path(str(row["database_path"]))
            for row in list_libraries(
                REGISTRY_DATABASE_FILE, active_only=False,
                registered_only=False,
            )
            if str(row.get("database_path") or "").strip()
        )
        metadata_recovery = recover_metadata_swaps(
            metadata_storage_paths(WORKSPACE_PATH)["metadata_root"],
            allowed_databases=metadata_db_allowlist,
        )
        if metadata_recovery["blocked"]:
            raise RuntimeError(
                "Unterbrochene Metadatenkorrektur erfordert Prüfung: "
                + " | ".join(metadata_recovery["errors"][:5])
            )

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
        start_release_worker()

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
    RELEASE_WORKER_STOP.set()
    RELEASE_WORKER_WAKE.set()
    if RELEASE_WORKER_THREAD is not None and RELEASE_WORKER_THREAD.is_alive():
        RELEASE_WORKER_THREAD.join(timeout=5)
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
        # BA-10: Die Jobpfade wurden je Bibliotheks-DB separat bestätigt.
        # Ein Rückbau der Ordner/Settings muss diese Teil-Commits ebenfalls
        # zurücknehmen, statt jobs.working_path auf verschwundene Ziele zu lassen.
        path_rollback_errors: list[str] = []
        if old_names["backup_directory_name"] != new_names["backup_directory_name"]:
            original_backup_root = (root / old_names["backup_directory_name"]).resolve(strict=False)
            renamed_backup_root = (root / new_names["backup_directory_name"]).resolve(strict=False)
            if original_backup_root.is_dir() and not renamed_backup_root.exists():
                for library in previous_rows:
                    try:
                        _rewrite_job_working_path_prefix(
                            Path(str(library["database_path"])),
                            renamed_backup_root,
                            original_backup_root,
                        )
                    except Exception as rollback_error:
                        path_rollback_errors.append(
                            str(library["library_id"]) + ": " + str(rollback_error)
                        )
            else:
                path_rollback_errors.append(
                    "Sicherungsordner konnte physisch nicht vollständig zurückbenannt werden."
                )
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
        if path_rollback_errors:
            detail += " Datenbank-Pfadrückbau nicht vollständig: " + " | ".join(path_rollback_errors)
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
        # The compatibility root is a temporary filesystem holding symlinks.
        # statvfs() must inspect the real shared dataset, not /tmp (often 64 MiB).
        health_workspace = current_library_context().workspace_root
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
        new_library_database = not database_path.is_file() or database_path.stat().st_size == 0
        initialize_database(database_path)
        if new_library_database:
            with database_connection(database_path) as connection:
                set_global_event_folder_layout(
                    connection, ENGLISH_NEW_INSTALL_SETTING,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
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


@app.get("/api/source-folder-summary", tags=["Import"])
def api_source_folder_summary(root_key: str = "nas", relative_path: str = ".") -> dict[str, Any]:
    """Return statistics for the selected folder, not a discovered backup."""
    root = _safe_root(root_key)
    source = resolve_import_source(relative_path, root_key)
    if source == root:
        raise HTTPException(status_code=422, detail="Bitte einen einzelnen Quellordner auswählen.")
    return import_source_summary(source, root_key, root)


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
    if root_key == "nas" and source == root:
        raise HTTPException(
            status_code=422,
            detail="Der gesamte NAS-Quellenbereich kann nicht importiert werden. Bitte einen einzelnen Unterordner wählen.",
        )
    try:
        try:
            storage = load_settings().get("storage", {})
        except FileNotFoundError:
            # Frische Test-/Setup-Installationen haben noch keine settings.json.
            storage = {}
        preflight_folder_import(
            source, WORKSPACE_PATH, WORKSPACE_PATH,
            processing_buffer_percent=int(storage.get("processing_buffer_percent", 10)),
            safety_reserve_gib=int(storage.get("safety_reserve_gib", 20)),
        )
    except (PipelineError, OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
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
        if item.get("operation") == "folder_import":
            item.update(_import_cancel_info(job_id))
            if item.get("state") in {
                "copying", "verifying", "backup_verified",
                "analyzing_metadata", "organizing",
            }:
                lifecycle = next(
                    (row for row in list_backup_lifecycles(DATABASE_FILE, limit=100)
                     if str(row.get("job_id") or "") == job_id), None
                ) or {}
                details = lifecycle.get("details") or {}
                stage = str(details.get("stage") or item.get("stage") or "")
                item["stage_progress_stage"] = stage
                item["stage_progress_current"] = int(details.get("progress_current") or 0)
                item["stage_progress_total"] = int(details.get("progress_total") or 0)
                item["overall_progress_current"] = int(item.get("progress_current") or 0)
                item["overall_progress_total"] = int(item.get("progress_total") or 0)
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
def api_cancel_import(job_id: str, force: bool = False) -> JSONResponse:
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
        if force:
            # Ein eskalierter Abbruch darf erst nach einer Wartefrist erfolgen.
            info = _import_cancel_info(job_id)
            if not info["cancel_requested"]:
                raise HTTPException(status_code=409, detail="Zuerst normalen Abbruch anfordern.")
            if datetime.now(timezone.utc).timestamp() - _import_cancel_marker(job_id).stat().st_mtime < 15:
                raise HTTPException(status_code=409, detail="Die Sicherheitswartefrist ist noch nicht abgelaufen.")
        _request_import_cancel(job_id, force=force)
        return JSONResponse(
            status_code=202,
            content={
                "accepted": True,
                "cancelled": False,
                "force": force,
                "message": (
                    "Erzwungener Abbruch angefordert. Nur eigene Importdateien werden sicher zurückgerollt."
                    if force else "Abbruch wurde angefordert. Der Import wird sicher zurückgerollt."
                ),
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
    status_code=202,
)
def api_ssd_release(job_id: str, event_id: str) -> dict[str, Any]:
    """Only enqueue. Worker verifies archive and performs durable SSD cleanup."""
    try:
        task = release_queue.enqueue_release(current_database_file(), job_id, event_id)
        start_release_worker()
        RELEASE_WORKER_WAKE.set()
        return {"status": str(task["status"]), "task_id": str(task["id"]),
                "message": "SSD-Freigabe im Hintergrund angenommen."}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/jobs/{job_id}/events/{event_id}/ssd-release/task", tags=["Archivübernahme"])
def api_ssd_release_task(job_id: str, event_id: str) -> dict[str, Any]:
    task = release_queue.get_release_task(current_database_file(), job_id, event_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Freigabeauftrag nicht gefunden.")
    return task


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


_TRASH_RESTORE_LOCK = Lock()


@app.post("/api/trash/restore", tags=["Papierkorb"])
def api_restore_trash(payload: dict[str, Any]) -> dict[str, Any]:
    choice = payload.get("relative_paths", None)
    if choice is not None and not isinstance(choice, list):
        raise HTTPException(status_code=422, detail="Ungültige Dateiauswahl.")
    with _TRASH_RESTORE_LOCK:
        databases = {
            Path(str(row["database_path"])).resolve(strict=False)
            for row in list_libraries(
                REGISTRY_DATABASE_FILE, active_only=False, registered_only=True
            )
            if Path(str(row["database_path"])).is_file()
        }
        databases.add(current_database_file().resolve(strict=False))
        from app.source_filter import should_ignore_source_relative
        from app.trash_import import stage_trash_import
        from app.trash import _physical_entries, reconcile_trash_inventory
        from app.trash_restore import _relative
        try:
            for db in databases:
                reconcile_trash_inventory(db, WORKSPACE_PATH)
            _root, entries, _dirs = _physical_entries(WORKSPACE_PATH)
            physical = {str(e["relative_path"]) for e in entries if e["entry_type"] == "file"}
            selected = sorted(physical) if choice is None else list(choice)
            if not selected or len(set(selected)) != len(selected):
                raise TrashError("Keine gültige Dateiauswahl.")
            for rel in selected:
                _relative(rel)
                if rel not in physical:
                    raise TrashError("Datei nicht im Papierkorb: " + rel)
            ignored = [rel for rel in selected if should_ignore_source_relative(rel)]
            requested = [rel for rel in selected if rel not in ignored]
            known, unknown = [], []
            for rel in requested:
                linked = False
                for db in databases:
                    with database_connection(db) as conn:
                        if conn.execute(
                            "SELECT 1 FROM files WHERE current_root_kind='trash' "
                            "AND current_relative_path=? LIMIT 1", (rel,)
                        ).fetchone():
                            linked = True
                            break
                (known if linked else unknown).append(rel)
            result = {"restored_file_count":0,"restored_paths":[],
                      "queued_file_count":0,"skipped_paths":ignored}
            # Stage unknown originals before touching any known catalogued ones.
            # Source originals remain in trash until verified by the worker.
            if unknown:
                queued = stage_trash_import(DATABASE_FILE,WORKSPACE_PATH,unknown)
                result["queued_file_count"] = int(queued["queued_file_count"])
                result["queued_job_id"] = queued["job_id"]
            if known:
                try:
                    restored = restore_trash_files(sorted(databases), WORKSPACE_PATH,
                                                   relative_paths=known)
                    result.update(restored)
                except (TrashError, OSError, ValueError) as error:
                    if unknown:
                        result["restore_warning"] = str(error)
                    else:
                        raise
            if not known and not unknown and ignored:
                result["note"] = "Systemdateien wurden nicht als Aufnahmen importiert."
        except (TrashError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        for db in databases:
            view_cache.invalidate(db)
        try:
            synchronize_global_central_stock()
        except Exception as error:
            result["synchronization_warning"] = str(error)
        result["inventory"] = api_trash_inventory()
        return result


@app.post("/api/trash/empty-selection", tags=["Papierkorb"])
def api_empty_trash_selection(payload: dict[str, Any]) -> dict[str, Any]:
    """Delete only explicitly selected regular trash files, retaining all others."""
    from app.trash_selective import delete_selected_trash_files
    paths = payload.get("relative_paths")
    if not isinstance(paths, list):
        raise HTTPException(status_code=422, detail="Ungültige Lösch-Auswahl.")
    with _TRASH_RESTORE_LOCK:
        databases = {
            Path(str(row["database_path"])).resolve(strict=False)
            for row in list_libraries(REGISTRY_DATABASE_FILE,
                                      active_only=False,registered_only=True)
            if Path(str(row["database_path"])).is_file()
        }
        databases.add(current_database_file().resolve(strict=False))
        databases.add(DATABASE_FILE.resolve(strict=False))
        try:
            result = delete_selected_trash_files(sorted(databases), WORKSPACE_PATH, paths)
        except (OSError, TrashError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        for db in databases:
            view_cache.invalidate(db)
        result["inventory"] = api_trash_inventory()
        return result


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
  <script src="/auth/client.js"></script>

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
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
      setStatus("Metadatenaufträge werden geladen …");

      const data = await getJson("/api/jobs");

      jobs = (data.jobs || [])
        .filter(
          job =>
            job.operation ===
            "metadata_fixture_analysis"
        )
        .sort(
          (a, b) =>
            String(b.created_at).localeCompare(
              String(a.created_at)
            )
        );

      jobSelect.innerHTML = "";

      if (jobs.length === 0) {
        const option =
          document.createElement("option");

        option.value = "";
        option.textContent =
          "Keine Metadatenaufträge vorhanden";

        jobSelect.appendChild(option);

        setStatus(
          "Noch kein Metadatenauftrag vorhanden."
        );

        return;
      }

      for (const job of jobs) {
        const option =
          document.createElement("option");

        option.value = job.id;

        option.textContent =
          `${formatJobLabel(job)} · `
          + stateLabel(job.state);

        jobSelect.appendChild(option);
      }

      const parameters =
        new URLSearchParams(location.search);

      const requestedJob =
        parameters.get("job");

      if (
        requestedJob
        && jobs.some(
          job => job.id === requestedJob
        )
      ) {
        jobSelect.value = requestedJob;
      }

      await loadSelectedJob();
    }


    async function loadSelectedJob() {
      const jobId = jobSelect.value;

      if (!jobId) {
        return;
      }

      activeFileId = null;
      detailsElement.innerHTML =
        '<p class="muted">'
        + "Links eine Datei auswählen."
        + "</p>";

      setStatus("Dateien werden geladen …");

      const data = await getJson(
        `/api/jobs/${encodeURIComponent(jobId)}/files`
      );

      files = data.files || [];

      const job = jobs.find(
        item => item.id === jobId
      );

      summaryJob.textContent =
        formatJobLabel(job);

      summaryJob.title =
        job?.id || "";

      summaryFiles.textContent =
        files.length;

      summaryState.textContent =
        stateLabel(job?.state);

      renderFiles();

      setStatus(
        `${files.length} Dateien geladen.`
      );
    }


    function filteredFiles() {
      const query = searchInput.value
        .trim()
        .toLocaleLowerCase("de-DE");

      const mediaType =
        mediaFilter.value;

      const reviewStatus =
        reviewFilter.value;

      return files.filter(file => {
        const searchable = (
          String(file.original_filename || "")
          + " "
          + String(file.original_relative_path || "")
          + " "
          + String(file.family_key || "")
        ).toLocaleLowerCase("de-DE");

        if (
          query
          && !searchable.includes(query)
        ) {
          return false;
        }

        if (
          mediaType
          && file.media_type !== mediaType
        ) {
          return false;
        }

        if (
          reviewStatus
          && file.review_status !== reviewStatus
        ) {
          return false;
        }

        return true;
      });
    }


    function renderFiles() {
      const visible = filteredFiles();

      summaryVisible.textContent =
        visible.length;

      fileListElement.innerHTML = "";

      if (visible.length === 0) {
        fileListElement.innerHTML =
          '<div class="empty">'
          + "Keine Dateien entsprechen "
          + "den gewählten Filtern."
          + "</div>";

        return;
      }

      for (const file of visible) {
        const button =
          document.createElement("button");

        button.type = "button";
        button.className = "file-button";

        if (file.id === activeFileId) {
          button.classList.add("active");
        }

        const badgeClass =
          file.review_status === "required"
            ? file.capture_time_confidence
            : "high";

        const badgeText =
          file.review_status === "required"
            ? confidenceLabel(
                file.capture_time_confidence
              )
            : "keine Prüfung nötig";

        button.innerHTML = `
          <span class="file-header">
            <span class="file-main">
              <span class="file-name">
                ${escapeHtml(file.original_filename)}
              </span>

              <span class="file-path">
                ${
                  escapeHtml(
                    file.original_relative_path
                  )
                }
              </span>

              <span class="family">
                Familie:
                ${escapeHtml(file.family_key || "–")}
              </span>
            </span>

            <span class="badge ${
              escapeHtml(badgeClass)
            }">
              ${escapeHtml(badgeText)}
            </span>
          </span>

          <span class="file-meta">
            <span>
              ${
                escapeHtml(
                  mediaTypeLabel(file.media_type)
                )
              }
            </span>

            <span>
              ${
                escapeHtml(
                  formatDate(
                    file.selected_capture_time
                  )
                )
              }
            </span>

            <span>
              Quelle:
              ${
                escapeHtml(
                  file.selected_capture_source
                  || "keine"
                )
              }
            </span>
          </span>
        `;

        button.addEventListener(
          "click",
          () => loadDetails(file)
        );

        fileListElement.appendChild(button);
      }
    }


    async function loadDetails(file) {
      activeFileId = file.id;
      renderFiles();

      detailsElement.innerHTML =
        '<p class="muted">'
        + "Metadatenkandidaten werden geladen …"
        + "</p>";

      try {
        const metadata = await getJson(
          `/api/files/${file.id}/metadata`
        );

        let candidateHtml = "";

        for (
          const candidate
          of metadata.candidates || []
        ) {
          const classes = ["candidate"];

          if (candidate.is_selected) {
            classes.push("selected");
          }

          if (
            candidate.conflicts_with_selected
          ) {
            classes.push("conflicting");
          }

          candidateHtml += `
            <div class="${classes.join(" ")}">
              <div class="candidate-tag">
                ${escapeHtml(candidate.tag_name)}
              </div>

              <div class="candidate-value">
                Rohwert:
                ${escapeHtml(candidate.raw_value)}
              </div>

              <div class="candidate-value">
                Normalisiert:
                ${
                  escapeHtml(
                    candidate.normalized_datetime
                    || "nicht verwendbar"
                  )
                }
              </div>

              ${
                candidate.is_selected
                  ? '<div class="badge high">'
                    + "automatisch ausgewählt"
                    + "</div>"
                  : ""
              }

              ${
                candidate.conflicts_with_selected
                  ? '<div class="badge conflict">'
                    + "widerspricht der Auswahl"
                    + "</div>"
                  : ""
              }
            </div>
          `;
        }

        if (!candidateHtml) {
          candidateHtml =
            '<div class="empty">'
            + "Keine Metadatenkandidaten vorhanden."
            + "</div>";
        }

        detailsElement.innerHTML = `
          <h3>
            ${escapeHtml(file.original_filename)}
          </h3>

          <p class="muted">
            ${escapeHtml(file.original_relative_path)}
          </p>

          <p>
            <strong>Medientyp:</strong><br>
            ${
              escapeHtml(
                mediaTypeLabel(file.media_type)
              )
            }
          </p>

          <p>
            <strong>Dateifamilie:</strong><br>
            ${escapeHtml(file.family_key || "–")}
          </p>

          <p>
            <strong>Erkanntes Datum:</strong><br>
            ${
              escapeHtml(
                formatDate(
                  file.selected_capture_time
                )
              )
            }
          </p>

          <p>
            <strong>Quelle:</strong><br>
            ${
              escapeHtml(
                file.selected_capture_source
                || "keine"
              )
            }
          </p>

          <p>
            <strong>Dateigröße:</strong><br>
            ${
              new Intl.NumberFormat(
                (document.documentElement.lang === "de" ? "de-DE" : "en-US")
              ).format(file.size_bytes || 0)
            }
            Byte
          </p>

          <h3>Metadatenkandidaten</h3>

          <div class="candidate-list">
            ${candidateHtml}
          </div>
        `;

      } catch (error) {
        detailsElement.innerHTML =
          '<p class="error">'
          + escapeHtml(error.message)
          + "</p>";
      }
    }


    refreshButton.addEventListener(
      "click",
      () => {
        loadJobs().catch(
          error => setStatus(
            error.message,
            true
          )
        );
      }
    );

    jobSelect.addEventListener(
      "change",
      () => {
        loadSelectedJob().catch(
          error => setStatus(
            error.message,
            true
          )
        );
      }
    );

    searchInput.addEventListener(
      "input",
      renderFiles
    );

    mediaFilter.addEventListener(
      "change",
      renderFiles
    );

    reviewFilter.addEventListener(
      "change",
      renderFiles
    );

    loadJobs().catch(
      error => setStatus(
        error.message,
        true
      )
    );
  </script>
</body>
</html>
""",
        status_code=200,
    )




@app.get(
    "/api/jobs/{job_id}/days",
    tags=["Arbeitsbereich"],
)
def api_job_day_groups(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    blocked = blocked_family_ids(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        job_id=job_id,
    )
    groups = list_job_day_groups(
        current_database_file(),
        job_id,
        excluded_family_ids=blocked,
    )

    dated_groups = [
        group
        for group in groups
        if group.get("has_date")
    ]

    undated_groups = [
        group
        for group in groups
        if not group.get("has_date")
    ]

    return {
        "job_id": job_id,
        "count": len(groups),
        "dated_count": len(dated_groups),
        "has_without_date": bool(undated_groups),
        "groups": groups,
    }

@app.get(
    "/api/jobs/{job_id}/events",
    tags=["Ereignisse"],
)
def api_job_events(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    refresh_live_event_inventories(
        current_database_file(),
        current_workspace_root(),
        current_archive_root(),
        job_id=job_id,
    )

    events = list_job_events(
        current_database_file(),
        job_id,
    )

    parent_events = [
        event
        for event in events
        if event.get("event_level") == "parent"
    ]

    child_events = [
        event
        for event in events
        if event.get("event_level") == "child"
    ]

    return {
        "job_id": job_id,
        "count": len(events),
        "parent_count": len(parent_events),
        "child_count": len(child_events),
        "events": events,
    }


def _reserve_global_family_ids(
    event_id: str,
    family_ids: list[int] | set[int],
) -> dict[str, Any]:
    return reserve_family_ids(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        event_id=event_id,
        family_ids=family_ids,
    )


def _release_new_global_reservations(reservation: dict[str, Any] | None) -> None:
    if not reservation:
        return
    release_new_reservations(
        REGISTRY_DATABASE_FILE,
        library_id=current_library_context().library_id,
        source_family_keys=list(reservation.get("newly_reserved") or []),
    )


def _promote_global_family_ids_owned(
    event_id: str,
    family_ids: list[int] | set[int],
) -> None:
    promote_family_ids_owned(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        event_id=event_id,
        family_ids=family_ids,
    )


def _change_request_selected_family_ids(change_request: dict[str, Any]) -> set[int]:
    raw = change_request.get("selected_family_ids")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    return {
        int(value)
        for value in (raw or [])
        if str(value).strip() and int(value) > 0
    }


def _assigned_family_ids_for_root_event(event_id: str) -> set[int]:
    with database_connection(current_database_file()) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT ea.family_id
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            WHERE (
                assigned.id = ?
                OR assigned.parent_event_id = ?
            )
              AND ea.family_id IS NOT NULL
            """,
            (event_id, event_id),
        ).fetchall()
    return {int(row["family_id"]) for row in rows}


def _reserve_archive_change_preview(
    event_id: str,
    preview: dict[str, Any],
) -> dict[str, Any]:
    return _reserve_global_family_ids(
        event_id,
        {
            int(value)
            for value in (preview.get("selected_family_ids") or [])
            if int(value) > 0
        },
    )


@app.get(
    "/api/jobs/{job_id}/event-suggestions",
    tags=["Ereignisse"],
)
def api_event_suggestions(job_id: str) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    suggestions = list_event_suggestions(current_database_file(), job_id)
    return {"job_id": job_id, "count": len(suggestions), "suggestions": suggestions}


@app.post(
    "/api/jobs/{job_id}/event-suggestions/accept",
    tags=["Ereignisse"],
)
def api_accept_event_suggestion(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    family_ids = [
        int(value)
        for value in (payload.get("family_ids") or [payload.get("family_id")])
        if value is not None
    ]
    target_event_id = str(payload.get("target_event_id") or "")
    reservation: dict[str, Any] | None = None
    mutation_committed = False
    try:
        with database_connection(current_database_file()) as connection:
            target = connection.execute(
                """SELECT * FROM events
                   WHERE id=? AND parent_event_id IS NULL
                     AND event_kind='event'""",
                (target_event_id,),
            ).fetchone()

        target_job_id = str(target["job_id"]) if target is not None else None
        if target is None:
            raise EventSuggestionError("Das passende Ereignis ist nicht mehr verfügbar.")

        reservation = _reserve_global_family_ids(
            target_event_id,
            family_ids,
        )

        if str(target["status"] or "") == "archived":
            context = get_event_edit_context(
                current_database_file(), target_job_id, target_event_id
            )
            incoming_available = {
                int(family["family_id"]): dict(family)
                for family in _available_families_for_event_payload(
                    job_id,
                    {"selected_family_ids": family_ids},
                )
                if int(family["family_id"]) in set(family_ids)
            }
            if set(incoming_available) != set(family_ids):
                raise ValueError(
                    "Mindestens eine ausgewählte Familie ist nicht mehr frei."
                )
            family_map = {
                int(family["family_id"]): dict(family)
                for family in (context.get("families") or [])
                if family.get("assigned_here")
            }
            family_map.update(incoming_available)
            target_start = str(target["start_datetime"] or "")[:19]
            target_end = str(target["end_datetime"] or "")[:19]
            preview = build_event_preview(
                {
                    "event_kind": "event",
                    "event_name": str(target["name"]),
                    "start_date": target_start[:10],
                    "end_date": target_end[:10],
                    "start_time": target_start[11:16],
                    "end_time": target_end[11:16],
                    "uses_time_range": bool(target["uses_time_range"]),
                    "preserve_day_folders": bool(target["preserve_day_folders"]),
                    "folder_naming": _naming_snapshot_from_event_context(context),
                    "subevents": [
                        {
                            "id": child.get("id"),
                            "name": child.get("name"),
                            "start_datetime": child.get("start_datetime"),
                            "end_datetime": child.get("end_datetime"),
                        }
                        for child in (context.get("child_events") or [])
                    ],
                },
                list(family_map.values()),
            )
            result = propose_event_change(
                current_database_file(),
                target_job_id,
                target_event_id,
                preview,
                event_name=str(target["name"]),
                notes=str(target["notes"] or ""),
                archive_root=current_archive_root(),
                workspace_path=current_workspace_root(),
            )
            return {
                "job_id": job_id,
                "target_job_id": target_job_id,
                "event_id": target_event_id,
                "target_event_id": target_event_id,
                "target_status": "archived",
                "linkage_kind": "archive_change_request",
                "name": str(target["name"]),
                "family_ids": family_ids,
                "family_count": len(family_ids),
                "status": "archive_change_request_created",
                "change_request_id": result["change_request_id"],
                "prepared_structure_path": result.get("prepared_structure_path") or "",
            }

        result = accept_event_suggestion(
            current_database_file(),
            job_id,
            family_ids,
            target_event_id,
        )
        mutation_committed = True
        if str(result.get("target_status") or "") == "applied":
            _promote_global_family_ids_owned(
                target_event_id,
                family_ids,
            )
        return {"job_id": job_id, "target_job_id": target_job_id, **result}
    except (
        ValueError,
        TypeError,
        EventSuggestionError,
        EventChangeRequestError,
        LibraryRegistryError,
    ) as error:
        if reservation is not None and not mutation_committed:
            _release_new_global_reservations(reservation)
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        if reservation is not None and not mutation_committed:
            _release_new_global_reservations(reservation)
        raise

@app.get(
    "/api/jobs/{job_id}/archive-change-reviews",
    tags=["Archivprüfung"],
)
def api_archive_change_reviews(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    reviews = list_archive_change_reviews(
        current_database_file(),
        job_id,
    )

    manual_actions = [
        review
        for review in reviews
        if review.get("review_status")
        in {
            "manual_move_required",
            "missing",
            "ambiguous",
        }
    ]

    return {
        "job_id": job_id,
        "count": len(reviews),
        "manual_action_count":
            len(manual_actions),
        "reviews": reviews,
    }


@app.post(
    "/api/jobs/{job_id}/events",
    tags=["Ereignisse"],
)
def api_create_event(
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    existing_parent_event_id = str(payload.get("existing_parent_event_id") or "").strip()
    payload = _event_payload_with_folder_layout(
        payload,
        event_id=existing_parent_event_id or None,
    )

    try:
        payload, canonical_membership, confirmation = _canonical_membership_preflight(payload)
        if confirmation is not None:
            return confirmation
        available_families = _available_families_for_event_payload(job_id, payload)
    except (ValueError, EventPreviewError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    try:
        archived_target = None
        if existing_parent_event_id:
            with database_connection(current_database_file()) as connection:
                archived_target = connection.execute(
                    """SELECT * FROM events
                       WHERE id=? AND job_id=? AND parent_event_id IS NULL
                         AND event_kind='event' AND status='archived'""",
                    (existing_parent_event_id, job_id),
                ).fetchone()

        if archived_target is not None:
            context = get_event_edit_context(
                current_database_file(), job_id, existing_parent_event_id
            )
            current_start = str(archived_target["start_datetime"] or "")[:19]
            current_end = str(archived_target["end_datetime"] or "")[:19]
            selected_intervals = [
                item for item in (payload.get("selected_intervals") or [])
                if item.get("start_datetime") and item.get("end_datetime")
            ]
            if not selected_intervals:
                raise ValueError(
                    "Für die Archiv-Erweiterung fehlt der ausgewählte freie Zeitraum."
                )
            from app.database import _validated_adjacent_extension
            extension = _validated_adjacent_extension(
                (current_start, current_end),
                selected_intervals,
            )
            extension_start = extension["extension_start"]
            extension_end = extension["extension_end"]

            editable_families = [
                family
                for family in (context.get("families") or [])
                if not family.get("assigned_elsewhere") or family.get("assigned_here")
            ]
            from app.subevents import normalize_subevents
            archived_naming = _naming_snapshot_from_event_context(context)
            added_subevents = normalize_subevents(
                payload.get("subevents") or [],
                extension_start,
                extension_end,
                naming=archived_naming,
            )
            combined_payload = {
                "event_kind": "event",
                "event_name": str(archived_target["name"]),
                "start_date": extension["new_start"][:10],
                "end_date": extension["new_end"][:10],
                "start_time": extension["new_start"][11:16],
                "end_time": extension["new_end"][11:16],
                "uses_time_range": True,
                "preserve_day_folders": bool(archived_target["preserve_day_folders"]),
                "folder_naming": archived_naming,
                "subevents": [
                    *[
                        {
                            "id": child.get("id"),
                            "name": child.get("name"),
                            "start_datetime": child.get("start_datetime"),
                            "end_datetime": child.get("end_datetime"),
                        }
                        for child in (context.get("child_events") or [])
                    ],
                    *added_subevents,
                ],
            }
            preview = build_event_preview(combined_payload, editable_families)
            archive_reservation = _reserve_archive_change_preview(
                existing_parent_event_id,
                preview,
            )
            try:
                result = propose_event_change(
                    current_database_file(),
                    job_id,
                    existing_parent_event_id,
                    preview,
                    event_name=str(archived_target["name"]),
                    notes=str(archived_target["notes"] or ""),
                    archive_root=current_archive_root(),
                    workspace_path=current_workspace_root(),
                )
            except Exception:
                _release_new_global_reservations(archive_reservation)
                raise
            return {
                "job_id": job_id,
                "status": "archive_change_request_created",
                "preview": preview,
                "parent_event": dict(archived_target),
                "assigned_family_count": int(
                    result.get("diff_summary", {}).get("added_count") or 0
                ),
                "change_request_id": result["change_request_id"],
                "prepared_structure_path": result.get("prepared_structure_path") or "",
            }

        preview = build_event_preview(
            payload,
            available_families,
        )

        if preview.get("empty_subevents") and not bool(payload.get("confirm_empty_subevents")):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Mindestens ein Unterereignis enthält aktuell keine passenden Dateifamilien.",
                    "confirmation_required": "empty_subevents",
                    "empty_subevents": preview["empty_subevents"],
                },
            )

        result = create_planned_event(
            current_database_file(),
            job_id,
            preview,
        )
        parent_event_id = str(
            (result.get("parent_event") or {}).get("id") or ""
        )
        try:
            claim_event_families(
                REGISTRY_DATABASE_FILE,
                database_path=current_database_file(),
                library_id=current_library_context().library_id,
                event_id=parent_event_id,
                claim_state="reserved",
            )
        except Exception:
            if parent_event_id:
                delete_planned_event(
                    current_database_file(),
                    job_id,
                    parent_event_id,
                )
            raise

    except EventPreviewError as error:
        message = str(error)

        status_code = (
            409
            if "nicht mehr aktuell" in message
            else 422
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    except (ValueError, LibraryRegistryError) as error:
        message = str(error)

        status_code = (
            409
            if (
                "bereits" in message
                or "nicht mehr aktuell" in message
            )
            else 422
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    return {
        "job_id": job_id,
        "status": "planned",
        "preview": preview,
        "source_job_ids": sorted({
            str(family.get("job_id") or "")
            for family in available_families
            if int(family.get("family_id") or 0) in set(result.get("assigned_family_ids") or [])
            and str(family.get("job_id") or "")
        }),
        "canonical_membership": canonical_membership,
        **result,
    }

@app.get("/api/jobs/{job_id}/events/{event_id}/structure")
def api_event_structure(job_id: str, event_id: str):
    """Return the visible target tree plus the persisted event facts.

    The workspace uses this endpoint as a read-only inspector.  Keeping the
    database facts next to the rendered tree prevents the UI from having to
    infer time boundaries from file names or from the folder layout.
    """
    live_refresh = refresh_live_event_inventories(
        current_database_file(),
        current_workspace_root(),
        current_archive_root(),
        job_id=job_id,
        event_id=event_id,
    )
    context = get_event_edit_context(current_database_file(), job_id, event_id, workspace_path=current_workspace_root())
    event = context["event"]
    from app.structure_view import render_structure
    from app.event_leaf_layouts import stored_leaf_layouts
    from app.event_structure_changes import _tree_text, _snapshot_from_inventory

    with database_connection(current_database_file()) as c:
        cr = c.execute(
            """SELECT * FROM event_change_requests
               WHERE event_id=?
                 AND status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')
               ORDER BY version DESC
               LIMIT 1""",
            (event_id,),
        ).fetchone()
        from app.event_structure import assigned_day_keys_by_event
        assignment_days = assigned_day_keys_by_event(c, event_id)
        saved_leaf_layouts = list(stored_leaf_layouts(c, event_id).values())
        root_kind = "camera_archive" if str(event.get("status") or "") == "archived" else "shared_workspace"
        scan_errors = [item for item in (live_refresh or {}).get("errors", []) if str(item.get("event_id")) == str(event_id)]
        if str(event.get("status") or "") not in {"applied", "archived"}:
            physical_state = {
                "available": False,
                "reason": "Not applied yet – only the target structure exists.",
            }
        elif scan_errors:
            physical_state = {"available": False, "reason": str(scan_errors[0].get("message") or "Inventory unavailable")}
        else:
            event_row = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            try:
                measured = _snapshot_from_inventory(c, dict(event_row), get_event_layout(c, event_id), root_kind)
                # Real directory inventory, not the saved tree and not a projection of event.json.
                observed = list(measured.get("observed_directories") or [])
                observed_files = [str(row["event_relative_path"]) for row in c.execute(
                    "SELECT event_relative_path FROM event_inventory_files WHERE event_id=? AND root_kind=?",
                    (event_id, root_kind),
                ).fetchall()]
                actual_dirs = set(observed)
                for rel in observed_files:
                    parts = rel.split("/")
                    for depth in range(1, len(parts)):
                        actual_dirs.add("/".join(parts[:depth]))
                physical_state = {
                    "available": True,
                    "directories": sorted(actual_dirs),
                    "directory_added": measured.get("directory_added") or [],
                    "directory_removed": measured.get("directory_removed") or [],
                    "file_count": len(observed_files),
                }
                physical_state["tree_text"] = _tree_text(sorted(actual_dirs))
            except (ValueError, TypeError) as exc:
                physical_state = {"available": False, "reason": str(exc)}

    assigned_families = [
        family
        for family in context["families"]
        if family.get("assigned_here")
    ]

    if cr:
        import json
        children = json.loads(cr["child_segments_json"] or "[]")
        if cr["child_folder"]:
            children = [{"folder_name": cr["child_folder"]}]
        lines = render_structure(
            str(cr["start_date"])[:4],
            cr["parent_folder"],
            json.loads(cr["selected_day_keys"] or "[]"),
            children,
            bool(cr["preserve_day_folders"]),
            layout_state=context.get("folder_layout"),
            leaf_layouts=saved_leaf_layouts,
            parent_event_id=event_id,
        )
    else:
        structure_children = [
            {
                **child,
                "day_keys": assignment_days.get(str(child.get("id") or ""), []),
            }
            for child in context.get("child_events", [])
        ]
        lines = render_structure(
            str(event["start_datetime"])[:4],
            event["folder_name"],
            assignment_days.get(str(event_id), []),
            structure_children,
            bool(event["preserve_day_folders"]),
            layout_state=context.get("folder_layout"),
            leaf_layouts=saved_leaf_layouts,
            parent_event_id=event_id,
        )

    event_facts = {
        "id": str(event.get("id") or event_id),
        "name": str(event.get("display_title") or event.get("name") or ""),
        "status": str(event.get("status") or ""),
        "event_kind": str(event.get("event_kind") or "event"),
        "start_datetime": str(event.get("start_datetime") or ""),
        "end_datetime": str(event.get("end_datetime") or ""),
        "preserve_day_folders": bool(event.get("preserve_day_folders")),
        "folder_layout": context.get("folder_layout") or {},
        "assigned_family_count": len(assigned_families),
        "child_events": [
            {
                "id": str(child.get("id") or ""),
                "name": str(child.get("name") or ""),
                "folder_name": str(child.get("folder_name") or ""),
                "start_datetime": str(child.get("start_datetime") or ""),
                "end_datetime": str(child.get("end_datetime") or ""),
            }
            for child in context.get("child_events", [])
        ],
        "time_segments": [
            {
                "id": str(segment.get("id") or ""),
                "day_key": str(
                    segment.get("day_key")
                    or str(segment.get("start_datetime") or "")[:10]
                ),
                "start_time": str(
                    segment.get("start_time")
                    or str(segment.get("start_datetime") or "")[11:16]
                ),
                "end_time": str(
                    segment.get("end_time")
                    or str(segment.get("end_datetime") or "")[11:16]
                ),
                "start_datetime": str(segment.get("start_datetime") or ""),
                "end_datetime": str(segment.get("end_datetime") or ""),
            }
            for segment in context.get("time_segments", [])
        ],
    }

    return {
        "structure_text": "\n".join(lines),
        "physical_state": physical_state,
        "planned_change": bool(cr or event.get("resort_required")),
        "event": event_facts,
    }


@app.get(
    "/api/jobs/{job_id}/events/{event_id}/edit",
    tags=["Ereignisse"],
)
def api_event_edit_context(job_id: str, event_id: str) -> dict[str, Any]:
    if get_job(current_database_file(), job_id) is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    refresh_live_event_inventories(
        current_database_file(),
        current_workspace_root(),
        current_archive_root(),
        job_id=job_id,
        event_id=event_id,
    )
    try:
        context = get_event_edit_context(
            current_database_file(),
            job_id,
            event_id,
            workspace_path=current_workspace_root(),
        )
        globally_blocked = blocked_family_ids(
            REGISTRY_DATABASE_FILE,
            database_path=current_database_file(),
            library_id=current_library_context().library_id,
        )
        for family in context.get("families") or []:
            family_id = int(family.get("family_id") or 0)
            if family_id in globally_blocked and not family.get("assigned_here"):
                family["assigned_elsewhere"] = True
                family["blocked_by_other_library"] = True
        return context
    except ValueError as error:
        raise HTTPException(status_code=404 if "nicht gefunden" in str(error) else 409, detail=str(error)) from error


def _event_edit_payload_within_new_range(
    payload: dict[str, Any],
    families: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive event membership exclusively from date/time definitions.

    Since 0.16.5 the editor no longer accepts manual family membership. A
    normal event is its continuous time interval; a no-event collection is
    its explicit set of day/time segments.
    """
    normalized = dict(payload)
    if str(payload.get("event_kind") or "event") == "no_event" and payload.get("no_event_segments"):
        from app.event_timeline import normalize_no_event_segments
        segments = normalize_no_event_segments(payload.get("no_event_segments"))
        eligible = []
        for family in families:
            capture = str(family.get("selected_capture_time") or "")[:19]
            if capture and any(s["start_datetime"] <= capture <= s["end_datetime"] for s in segments):
                eligible.append(int(family["family_id"]))
        normalized["selected_family_ids"] = sorted(set(eligible))
        normalized["selected_day_keys"] = []
        normalized["no_event_segments"] = segments
        return normalized

    start_date = str(payload.get("start_date") or "")
    end_date = str(payload.get("end_date") or "")
    child_segments = list(payload.get("child_segments") or [])
    if child_segments:
        eligible = []
        for family in families:
            capture = str(family.get("selected_capture_time") or "")[:19]
            if not capture:
                continue
            for seg in child_segments:
                seg_start = f"{start_date}T{str(seg.get('start_time') or '00:00')}:00"
                seg_end = f"{end_date}T{str(seg.get('end_time') or '23:59')}:59"
                if seg_start <= capture <= seg_end:
                    eligible.append(int(family["family_id"]))
                    break
        normalized["selected_family_ids"] = sorted(set(eligible))
        normalized["selected_day_keys"] = []
        normalized["uses_time_range"] = True
        return normalized
    uses_time = bool(payload.get("uses_time_range"))
    start_time = str(payload.get("start_time") or "00:00")
    end_time = str(payload.get("end_time") or "23:59")
    start_second = f"{start_date}T{start_time}:00" if uses_time else f"{start_date}T00:00:00"
    end_second = f"{end_date}T{end_time}:59" if uses_time else f"{end_date}T23:59:59"
    eligible = []
    for family in families:
        capture = str(family.get("selected_capture_time") or "")[:19]
        if capture and start_second <= capture <= end_second:
            eligible.append(int(family["family_id"]))
    normalized["selected_family_ids"] = sorted(set(eligible))
    normalized["selected_day_keys"] = []
    return normalized



def _no_event_normal_conflicts(
    connection: Any,
    job_id: str,
    event_id: str,
    segments: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Return named-event occupancies that a no-event edit would cover.

    „Ohne Ereignis“ fills free time; it must never trim or steal time from a
    normal event. Keep this separate from the normal cascade path, which is
    allowed to coordinate edits between named events.
    """
    from app.event_timeline import continuous_event_overlaps

    found: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for segment in segments:
        for row in continuous_event_overlaps(
            connection,
            job_id,
            str(segment["start_datetime"]),
            str(segment["end_datetime"]),
            exclude_event_id=event_id,
        ):
            key = (
                str(row.get("id") or ""),
                str(row.get("effective_child_id") or ""),
                str(row.get("effective_start") or "")[:19],
                str(row.get("effective_end") or "")[:19],
            )
            found[key] = {
                "event_id": str(row.get("id") or ""),
                "child_event_id": (
                    str(row.get("effective_child_id"))
                    if row.get("effective_child_id")
                    else None
                ),
                "name": str(row.get("name") or ""),
                "status": str(row.get("status") or ""),
                "start_datetime": str(row.get("effective_start") or "")[:19],
                "end_datetime": str(row.get("effective_end") or "")[:19],
            }
    return list(found.values())


def _applied_edit_is_metadata_only(context: dict[str, Any], payload: dict[str, Any]) -> bool:
    """True when an applied event changes only visible metadata.

    UI and backend use slightly different field names for organizational
    subevents. Compare their canonical time/structure semantics instead of
    comparing the raw payload shape.
    """
    event = context["event"]
    if str(event.get("status") or "") != "applied" or not event.get("applied_at"):
        return False

    if str(event.get("event_kind") or "event") == "no_event":
        try:
            from app.event_timeline import normalize_no_event_segments
            requested_segments = normalize_no_event_segments(payload.get("no_event_segments") or [])
        except Exception:
            return False
        current_segments = [
            {
                "day_key": str(seg.get("day_key") or ""),
                "start_time": str(seg.get("start_time") or ""),
                "end_time": str(seg.get("end_time") or ""),
            }
            for seg in context.get("time_segments", [])
        ]
        requested_simple = [
            {"day_key": seg["day_key"], "start_time": seg["start_time"], "end_time": seg["end_time"]}
            for seg in requested_segments
        ]
        return (
            requested_simple == current_segments
            and str(payload.get("event_kind") or "no_event") == "no_event"
            and bool(payload.get("preserve_day_folders")) == bool(event.get("preserve_day_folders"))
        )

    if str(payload.get("event_kind") or "event") != "event":
        return False
    current_layout = context.get("folder_layout") or {}
    if bool(payload.get("create_subfolders", current_layout.get("structure_enabled", True))) != bool(
        current_layout.get("structure_enabled", True)
    ):
        return False
    if bool(payload.get("preserve_day_folders")) != bool(event.get("preserve_day_folders")):
        return False

    start_date = str(payload.get("start_date") or "")
    end_date = str(payload.get("end_date") or "")
    if not start_date or not end_date:
        return False

    requested_children = list(
        payload.get("subevents")
        or payload.get("child_segments")
        or []
    )
    current_children = list(context.get("child_events") or [])
    if len(requested_children) != len(current_children):
        return False

    current_by_id = {str(child.get("id") or ""): child for child in current_children}
    for index, segment in enumerate(requested_children):
        segment_id = str(segment.get("id") or "")
        current = current_by_id.get(segment_id) if segment_id else (
            current_children[index] if index < len(current_children) else None
        )
        if current is None:
            return False
        requested_start = str(
            segment.get("start_datetime")
            or f"{start_date}T{str(segment.get('start_time') or '00:00')}:00"
        )[:19]
        requested_end = str(
            segment.get("end_datetime")
            or f"{end_date}T{str(segment.get('end_time') or '23:59')}:59"
        )[:19]
        if (
            str(segment.get("name") or "") != str(current.get("name") or "")
            or requested_start != str(current.get("start_datetime") or "")[:19]
            or requested_end != str(current.get("end_datetime") or "")[:19]
        ):
            return False

    uses_time = bool(payload.get("uses_time_range"))
    requested_start = (
        f"{start_date}T{str(payload.get('start_time') or '00:00')}:00"
        if uses_time
        else f"{start_date}T00:00:00"
    )
    requested_end = (
        f"{end_date}T{str(payload.get('end_time') or '23:59')}:59"
        if uses_time
        else f"{end_date}T23:59:59"
    )

    # Legacy V1 parents may keep full-day parent bounds while one child carries
    # the effective time range. Their child graph was compared above.
    if int(event.get("time_model_version") or 1) < 2 and current_children:
        return (
            start_date == str(event.get("start_datetime") or "")[:10]
            and end_date == str(event.get("end_datetime") or "")[:10]
        )

    return (
        requested_start == str(event.get("start_datetime") or "")[:19]
        and requested_end == str(event.get("end_datetime") or "")[:19]
    )


@app.put(
    "/api/jobs/{job_id}/events/{event_id}",
    tags=["Ereignisse"],
)
def api_update_event(job_id: str, event_id: str, payload: dict[str, Any]):
    if get_job(current_database_file(), job_id) is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    try:
        manual_change_id = str(payload.get("manual_structure_change_id") or "").strip()
        if manual_change_id:
            from app.workspace_layout import shared_work_root
            from app.event_inventory import scan_event_inventory, EventInventoryError
            # 0.52.1 P0: a guided structural shortcut must NEVER authorize
            # family reassignment on a size-only fast refresh. Hash every
            # currently present file, including those whose path is unchanged.
            try:
                scan_event_inventory(
                    current_database_file(), shared_work_root(current_workspace_root()),
                    job_id, event_id, root_kind="shared_workspace",
                    persist=True, fast_refresh=False,
                    update_known_file_locations=False,
                )
            except EventInventoryError as error:
                raise ValueError("Die Dateibestandsprüfung vor der manuellen Übernahme ist fehlgeschlagen: " + str(error)) from error
        context = get_event_edit_context(current_database_file(), job_id, event_id, workspace_path=current_workspace_root())
        payload = _event_payload_with_folder_layout(payload, event_id=event_id)
        preview = None
        if payload.get("cascade_confirmed") or payload.get("child_segments"):
            raise ValueError("Getrennte Belegungssegmente und automatische gemeinsame Anpassungen werden nicht mehr unterstützt.")
        cascade_confirmed = False

        if context["structural_editable"] and not _applied_edit_is_metadata_only(context, payload):
            event_kind = str(payload.get("event_kind") or context["event"].get("event_kind") or "event")
            cascade_preview = {"has_conflicts": False, "can_apply_automatically": True, "items": []}
            if event_kind == "no_event":
                from app.event_timeline import normalize_no_event_segments
                requested_no_event_segments = normalize_no_event_segments(
                    payload.get("no_event_segments") or []
                )
                with database_connection(current_database_file()) as connection:
                    occupied = _no_event_normal_conflicts(
                        connection,
                        job_id,
                        event_id,
                        requested_no_event_segments,
                    )
                if occupied:
                    names = sorted({str(item.get("name") or "Ereignis") for item in occupied})
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": (
                                "„Ohne Ereignis“ darf keine bereits von einem normalen Ereignis "
                                "belegte Zeit überdecken. Konflikt: " + ", ".join(names)
                            ),
                            "occupied_by_events": occupied,
                        },
                    )
            elif event_kind == "event":
                start_date = str(payload.get("start_date") or "")
                end_date = str(payload.get("end_date") or "")
                child_segments = list(payload.get("child_segments") or [])
                uses_time = bool(payload.get("uses_time_range")) or bool(child_segments)
                from app.event_timeline import cascade_preview_for_interval
                if child_segments:
                    combined = []
                    can_auto = True
                    with database_connection(current_database_file()) as connection:
                        for seg in child_segments:
                            start_dt = f"{start_date}T{seg.get('start_time') or '00:00'}:00"
                            end_dt = f"{end_date}T{seg.get('end_time') or '23:59'}:59"
                            part = cascade_preview_for_interval(connection, job_id, event_id, start_dt, end_dt)
                            combined.extend(part.get("items") or [])
                            can_auto = can_auto and bool(part.get("can_apply_automatically", True))
                    unique = {(str(x.get("event_id")), str(x.get("action")), str(x.get("start_datetime")), str(x.get("end_datetime"))): x for x in combined}
                    cascade_preview = {"has_conflicts": bool(unique), "can_apply_automatically": can_auto, "items": list(unique.values())}
                else:
                    start_dt = f"{start_date}T{payload.get('start_time') or '00:00'}:00" if uses_time else f"{start_date}T00:00:00"
                    end_dt = f"{end_date}T{payload.get('end_time') or '23:59'}:59" if uses_time else f"{end_date}T23:59:59"
                    with database_connection(current_database_file()) as connection:
                        cascade_preview = cascade_preview_for_interval(connection, job_id, event_id, start_dt, end_dt)
                if cascade_preview["has_conflicts"] and not cascade_confirmed:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Die Änderung überschneidet sich mit belegter Zeit. Bitte zuerst das andere Ereignis bearbeiten und die Zeit freigeben.",
                            "conflicts": cascade_preview["items"],
                        },
                    )
                if cascade_preview["has_conflicts"] and cascade_confirmed and not cascade_preview["can_apply_automatically"]:
                    hard_items = [
                        item for item in cascade_preview.get("items", [])
                        if str(item.get("status")) != "archived" and not bool(item.get("automatic"))
                    ]
                    if hard_items:
                        return JSONResponse(
                            status_code=409,
                            content={
                                "detail": "Die Änderung würde ein nicht archiviertes Ereignis teilen oder vollständig überdecken. Dieser Sonderfall muss zuerst eindeutig aufgelöst werden.",
                                "cascade_preview": cascade_preview,
                            },
                        )

            archived_family_ids: set[int] = set()
            archived_event_ids = [str(item.get("event_id")) for item in cascade_preview.get("items", []) if str(item.get("status")) == "archived"]
            if archived_event_ids:
                placeholders = ",".join("?" for _ in archived_event_ids)
                with database_connection(current_database_file()) as connection:
                    archived_rows = connection.execute(
                        f"""SELECT DISTINCT ea.family_id FROM event_assignments ea JOIN events e ON e.id=ea.event_id
                            WHERE ea.family_id IS NOT NULL AND COALESCE(e.parent_event_id,e.id) IN ({placeholders})""",
                        archived_event_ids,
                    ).fetchall()
                archived_family_ids = {int(row["family_id"]) for row in archived_rows}

            globally_blocked_family_ids = blocked_family_ids(
                REGISTRY_DATABASE_FILE,
                database_path=current_database_file(),
                library_id=current_library_context().library_id,
            )
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
                for f in context["families"]
                if int(f["family_id"]) not in archived_family_ids
                and int(f["family_id"]) not in globally_blocked_family_ids
                and (cascade_confirmed or not f["assigned_elsewhere"] or f["assigned_here"])
            ]
            edit_payload = _event_edit_payload_within_new_range(payload, editable_families)
            child_segments = list(edit_payload.get("child_segments") or [])
            if child_segments:
                first = child_segments[0]
                # Multi-segment edits derive membership from the UNION of all
                # child segments. build_event_preview can only model one child
                # interval at a time, so passing the union as selected ids while
                # asking it to validate only the first interval incorrectly
                # rejects every family that belongs to another child segment.
                # Build the structural preview from the first segment without a
                # manual family constraint, then restore the union membership
                # derived above. update_event_definition validates every family
                # against all child segments again before committing.
                preview_payload = dict(edit_payload)
                preview_payload.pop("selected_family_ids", None)
                preview_payload.pop("selected_day_keys", None)
                preview_payload.update({
                    "uses_time_range": True,
                    "child_event_name": first.get("name") or payload.get("event_name"),
                    "start_time": first.get("start_time") or "00:00",
                    "end_time": first.get("end_time") or "23:59",
                })
                preview = build_event_preview(preview_payload, editable_families)
                selected_ids = sorted({int(v) for v in (edit_payload.get("selected_family_ids") or [])})
                preview["selected_family_ids"] = selected_ids
                preview["selected_family_count"] = len(selected_ids)
                selected_set = set(selected_ids)
                preview["selected_file_count"] = sum(
                    int(f.get("file_count") or 0)
                    for f in editable_families
                    if int(f["family_id"]) in selected_set
                )
                preview["child_segments"] = child_segments
            else:
                preview = build_event_preview(edit_payload, editable_families)

            if preview.get("empty_subevents") and not bool(payload.get("confirm_empty_subevents")):
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Mindestens ein Unterereignis enthält aktuell keine passenden Dateifamilien.",
                        "confirmation_required": "empty_subevents",
                        "empty_subevents": preview["empty_subevents"],
                    },
                )

        old_status = str((context.get("event") or {}).get("status") or "")
        edit_reservation: dict[str, Any] | None = None
        if preview is not None:
            # Reserve every newly selected family before mutating SQLite.
            # The UI's blocked-family projection is only a snapshot; this
            # registry reservation is the race-safe multi-library guard.
            edit_reservation = _reserve_global_family_ids(
                event_id,
                {
                    int(value)
                    for value in (preview.get("selected_family_ids") or [])
                    if int(value) > 0
                },
            )
        released_reservations = 0
        if old_status in {"draft", "planned"}:
            released_reservations = release_event_reservations(
                REGISTRY_DATABASE_FILE,
                database_path=current_database_file(),
                library_id=current_library_context().library_id,
                event_id=event_id,
            )
        try:
            result = update_event_definition(
                current_database_file(), job_id, event_id, preview,
                workspace_path=current_workspace_root(),
                app_version=APP_VERSION,
                guided_structure_change_id=manual_change_id or None,
                event_name=str(payload.get("event_name") or context["event"]["name"]),
                notes=str(payload.get("notes") or ""),
                expected_revision=int(payload.get("revision") or 0),
                cascade_confirmed=cascade_confirmed,
                allow_archived_manual=False,
            )
            claim_event_families(
                REGISTRY_DATABASE_FILE,
                database_path=current_database_file(),
                library_id=current_library_context().library_id,
                event_id=event_id,
                claim_state=(
                    "owned"
                    if old_status in {"applied", "archived"}
                    else "reserved"
                ),
            )
        except Exception:
            if released_reservations:
                try:
                    claim_event_families(
                        REGISTRY_DATABASE_FILE,
                        database_path=current_database_file(),
                        library_id=current_library_context().library_id,
                        event_id=event_id,
                        claim_state="reserved",
                    )
                except Exception:
                    pass
            _release_new_global_reservations(edit_reservation)
            raise
    except (ValueError, EventPreviewError, TypeError, LibraryRegistryError) as error:
        message = str(error)
        raise HTTPException(status_code=404 if "nicht gefunden" in message else 409, detail=message) from error
    except Exception as error:
        from app.event_structure_changes import EventStructureChangeError
        if isinstance(error, EventStructureChangeError):
            raise HTTPException(status_code=409, detail=str(error)) from error
        raise
    return {"status": "updated", **result}


@app.delete(
    "/api/jobs/{job_id}/events/{event_id}",
    tags=["Ereignisse"],
)
def api_delete_event(
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    released_reservations = release_event_reservations(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        event_id=event_id,
    )
    try:
        result = delete_planned_event(
            current_database_file(),
            job_id,
            event_id,
            archive_root=current_archive_root(),
        )

    except ValueError as error:
        if released_reservations:
            try:
                claim_event_families(
                    REGISTRY_DATABASE_FILE,
                    database_path=current_database_file(),
                    library_id=current_library_context().library_id,
                    event_id=event_id,
                    claim_state="reserved",
                )
            except Exception:
                pass
        message = str(error)

        status_code = (
            404
            if "nicht gefunden" in message
            else 409
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    # Nach dem Löschen eines geplanten Ereignisses ist die lokale DB bereits
    # wieder frei. Jetzt die globale Claim-Wahrheit sofort nachziehen, damit
    # dieselben Familien in allen Bibliotheken wieder angeboten werden.
    backfill_library_claims(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
    )
    synchronize_global_central_stock()

    return {
        "status": "deleted",
        **result,
    }


def _apply_batch_thread_target(
    batch_id: str,
    library_context: LibraryContext,
) -> None:
    try:
        def after_run() -> None:
            backfill_library_claims(
                REGISTRY_DATABASE_FILE,
                database_path=library_context.database_path,
                library_id=library_context.library_id,
            )
            synchronize_global_central_stock()

        execute_apply_batch(
            library_context.database_path,
            batch_id,
            compatibility_workspace_root(
                library_context
            ),
            after_run=after_run,
        )
    except Exception as error:
        print(
            f"Server-Batch {batch_id} beendet mit Fehler: {error}",
            flush=True,
        )


def _sort_run_thread_target(
    run_id: str,
    library_context: LibraryContext,
) -> None:
    try:
        with database_connection(library_context.database_path) as connection:
            run_row = connection.execute(
                "SELECT event_id FROM sort_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        execute_sort_run(
            library_context.database_path,
            run_id,
            compatibility_workspace_root(library_context),
        )
        backfill_library_claims(
            REGISTRY_DATABASE_FILE,
            database_path=library_context.database_path,
            library_id=library_context.library_id,
        )
        synchronize_global_central_stock()

    except Exception as error:
        print(
            f"Sortierlauf {run_id} beendet mit Fehler: {error}",
            flush=True,
        )


def _reconcile_run_thread_target(
    run_id: str,
    library_context: LibraryContext,
) -> None:
    try:
        execute_workspace_reconcile_run(
            library_context.database_path,
            run_id,
            compatibility_workspace_root(library_context),
        )
        backfill_library_claims(
            REGISTRY_DATABASE_FILE,
            database_path=library_context.database_path,
            library_id=library_context.library_id,
        )
        synchronize_global_central_stock()
    except Exception as error:
        print(f"Arbeitsbereich-Abgleich {run_id} beendet mit Fehler: {error}", flush=True)


@app.post(
    "/api/operation-batches/apply-events",
    tags=["Sortierung"],
    status_code=202,
)
def api_create_apply_batch(
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        batch = create_apply_batch(
            current_database_file(),
            list(payload.get("items") or []),
            confirmation_phrase=str(
                payload.get("confirmation_phrase") or ""
            ),
        )
    except OperationBatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    thread = Thread(
        target=_apply_batch_thread_target,
        args=(
            str(batch["id"]),
            current_library_context(),
        ),
        name=f"kamera-batch-{batch['id']}",
        daemon=True,
    )
    thread.start()
    return {
        "status": "queued",
        "batch": batch,
    }


@app.get(
    "/api/operation-batches/active",
    tags=["Sortierung"],
)
def api_active_operation_batches() -> dict[str, Any]:
    batches = list_active_operation_batches(
        current_database_file()
    )
    return {
        "batches": batches,
        "count": len(batches),
    }


@app.get(
    "/api/operation-batches/{batch_id}",
    tags=["Sortierung"],
)
def api_operation_batch(
    batch_id: str,
) -> dict[str, Any]:
    try:
        return get_operation_batch(
            current_database_file(),
            batch_id,
        )
    except OperationBatchError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.get(
    "/api/jobs/{job_id}/events/{event_id}/sort-plan",
    tags=["Sortierplanung"],
)
def api_event_sort_plan(
    job_id: str,
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    try:
        return build_event_sort_plan(
            current_database_file(),
            job_id,
            event_id,
            current_workspace_root(),
            verify_sha256=verify_sha256,
        )

    except SortPlanError as error:
        message = str(error)

        status_code = (
            404
            if "nicht gefunden" in message
            else 409
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error


@app.post(
    "/api/jobs/{job_id}/events/{event_id}/apply-sort",
    tags=["Sortierung"],
    status_code=202,
)
def api_apply_event_sort(
    job_id: str,
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    try:
        run = prepare_sort_run(
            current_database_file(),
            job_id,
            event_id,
            current_workspace_root(),
            expected_plan_token=str(
                payload.get("plan_token") or ""
            ),
            confirmation_phrase=str(
                payload.get("confirmation_phrase") or ""
            ),
        )

    except (SortApplyError, SortPlanError) as error:
        message = str(error)
        status_code = (
            404
            if "nicht gefunden" in message
            else 409
        )
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    thread = Thread(
        target=_sort_run_thread_target,
        args=(str(run["id"]), current_library_context()),
        name=f"kamera-sort-{run['id']}",
        daemon=True,
    )
    thread.start()

    return {
        "status": "queued",
        "run": run,
        "files_changed": False,
        "folders_changed": False,
        "database_changed": True,
    }

@app.get(
    "/api/jobs/{job_id}/events/{event_id}/reconcile-plan",
    tags=["Sortierung"],
)
def api_event_reconcile_plan(
    job_id: str,
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    try:
        return build_workspace_reconcile_plan(
            current_database_file(), job_id, event_id, current_workspace_root(), verify_sha256=verify_sha256
        )
    except (SortApplyError, SortPlanError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/api/jobs/{job_id}/events/{event_id}/reconcile-sort",
    tags=["Sortierung"],
    status_code=202,
)
def api_event_reconcile_sort(job_id: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sicherung wurde nicht gefunden.")
    try:
        run = prepare_workspace_reconcile_run(
            current_database_file(), job_id, event_id, current_workspace_root(),
            expected_plan_token=str(payload.get("plan_token") or ""),
            confirmation_phrase=str(payload.get("confirmation_phrase") or ""),
        )
    except (SortApplyError, SortPlanError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    thread = Thread(
        target=_reconcile_run_thread_target,
        args=(str(run["id"]), current_library_context()),
        name=f"kamera-reconcile-{run['id']}", daemon=True,
    )
    thread.start()
    return {"status":"queued","run":run,"database_changed":True,"files_changed":False,"folders_changed":False}


@app.get(
    "/api/jobs/{job_id}/events/{event_id}/reapply-plan",
    tags=["Sortierung"],
)
def api_event_reapply_plan(
    job_id: str,
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    try:
        return build_event_sort_plan(
            current_database_file(),
            job_id,
            event_id,
            current_workspace_root(),
            verify_sha256=verify_sha256,
            allow_reapply=True,
        )
    except SortPlanError as error:
        message = str(error)
        status_code = 404 if "nicht gefunden" in message else 409
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error


@app.post(
    "/api/jobs/{job_id}/events/{event_id}/reapply-sort",
    tags=["Sortierung"],
    status_code=202,
)
def api_event_reapply(
    job_id: str,
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job = get_job(current_database_file(), job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    try:
        run = prepare_reapply_sort_run(
            current_database_file(),
            job_id,
            event_id,
            current_workspace_root(),
            expected_plan_token=str(payload.get("plan_token") or ""),
            confirmation_phrase=str(payload.get("confirmation_phrase") or ""),
        )
    except (SortApplyError, SortPlanError) as error:
        message = str(error)
        status_code = 404 if "nicht gefunden" in message else 409
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    thread = Thread(
        target=_sort_run_thread_target,
        args=(str(run["id"]), current_library_context()),
        name=f"kamera-reapply-{run['id']}",
        daemon=True,
    )
    thread.start()

    return {
        "status": "queued",
        "run": run,
        "files_changed": False,
        "folders_changed": False,
        "database_changed": True,
    }


@app.get(
    "/api/jobs/{job_id}/sort-runs/{run_id}",
    tags=["Sortierung"],
)
def api_sort_run(
    job_id: str,
    run_id: str,
) -> dict[str, Any]:
    run = get_sort_run(
        current_database_file(),
        job_id,
        run_id,
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Sortierlauf wurde nicht gefunden.",
        )

    return run


@app.get(
    "/api/jobs/{job_id}/events/{event_id}/latest-sort-run",
    tags=["Sortierung"],
)
def api_latest_event_sort_run(
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    run = latest_event_sort_run(
        current_database_file(),
        job_id,
        event_id,
    )

    return {
        "run": run,
    }


@app.post(
    "/api/jobs/{job_id}/event-preview",
    tags=["Arbeitsbereich"],
)
def api_event_preview(
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Sicherung wurde nicht gefunden.",
        )

    payload = _event_payload_with_folder_layout(
        payload,
        event_id=str(payload.get("existing_parent_event_id") or "").strip() or None,
    )
    try:
        with database_connection(current_database_file()) as connection:
            membership = resolve_payload_membership(connection, payload)
        payload = {
            **payload,
            "selected_family_ids": membership["canonical_family_ids"],
        }
        available_families = _available_families_for_event_payload(job_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    try:
        preview = build_event_preview(
            payload,
            available_families,
        )

    except EventPreviewError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return {
        "job_id": job_id,
        "preview": preview,
        "membership": membership,
    }


@app.get("/api/events/search", tags=["Ereignisse"])
def api_search_events(
    q: str = "", limit: int = 25, offset: int = 0,
    physical_refresh: bool = True,
) -> dict[str, Any]:
    db_path = current_database_file()
    must_check = physical_refresh or view_cache.needs_first_physical_check(db_path)
    if must_check:
        refresh_live_event_inventories(
            db_path, current_workspace_root(), current_archive_root()
        )
        reconcile_global_central_stock_state(force=True)
        detect_all_event_structure_changes(db_path, current_workspace_root())
        view_cache.mark_physical_checked(db_path)
        view_cache.invalidate(db_path)
    if not must_check:
        result = view_cache.get_snapshot(db_path, "events", q, limit, offset)
        if result is not None:
            return result
    result = search_events(db_path, query=q, limit=limit, offset=offset)
    view_cache.put_snapshot(db_path, "events", result, q, limit, offset)
    return result



def _canonical_event_anchor_job_id(event_id: str) -> str:
    with database_connection(current_database_file()) as connection:
        row = connection.execute(
            "SELECT job_id FROM events WHERE id=? AND parent_event_id IS NULL",
            (event_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ereignis wurde nicht gefunden.")
    return str(row["job_id"])


@app.get("/api/events/{event_id}", tags=["Ereignisse"])
def api_canonical_event(event_id: str) -> dict[str, Any]:
    anchor_job_id = _canonical_event_anchor_job_id(event_id)
    context = get_event_edit_context(current_database_file(), anchor_job_id, event_id, workspace_path=current_workspace_root())
    with database_connection(current_database_file()) as connection:
        source_job_ids = [
            str(row["job_id"])
            for row in connection.execute(
                "SELECT job_id FROM event_source_jobs WHERE event_id=? ORDER BY job_id",
                (event_id,),
            ).fetchall()
        ]
    return {
        **context,
        "event_id": event_id,
        "anchor_job_id": anchor_job_id,
        "source_job_ids": source_job_ids or [anchor_job_id],
    }


@app.get("/api/events/{event_id}/structure", tags=["Ereignisse"])
def api_canonical_event_structure(event_id: str) -> dict[str, Any]:
    anchor_job_id = _canonical_event_anchor_job_id(event_id)
    context = get_event_edit_context(current_database_file(), anchor_job_id, event_id, workspace_path=current_workspace_root())
    return {
        "event_id": event_id,
        "anchor_job_id": anchor_job_id,
        "folder_layout": context.get("folder_layout"),
        "child_events": context.get("child_events") or [],
        "time_segments": context.get("time_segments") or [],
    }


@app.get("/api/events/{event_id}/sort-plan", tags=["Sortierplanung"])
def api_canonical_event_sort_plan(
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    return api_event_sort_plan(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        verify_sha256,
    )


@app.post("/api/events/{event_id}/apply", tags=["Sortierung"], status_code=202)
def api_canonical_event_apply(event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api_apply_event_sort(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        payload,
    )


@app.get("/api/events/{event_id}/reconcile-plan", tags=["Sortierung"])
def api_canonical_event_reconcile_plan(
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    return api_event_reconcile_plan(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        verify_sha256,
    )


@app.post("/api/events/{event_id}/reconcile", tags=["Sortierung"], status_code=202)
def api_canonical_event_reconcile(
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return api_event_reconcile_sort(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        payload,
    )


@app.get("/api/events/{event_id}/reapply-plan", tags=["Sortierung"])
def api_canonical_event_reapply_plan(
    event_id: str,
    verify_sha256: bool = False,
) -> dict[str, Any]:
    return api_event_reapply_plan(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        verify_sha256,
    )


@app.post("/api/events/{event_id}/reapply", tags=["Sortierung"], status_code=202)
def api_canonical_event_reapply(
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return api_event_reapply(
        _canonical_event_anchor_job_id(event_id),
        event_id,
        payload,
    )


@app.get("/api/jobs/{job_id}/no-event/targets", tags=["Ereignisse"])
def api_no_event_targets(job_id: str, months: str = "") -> dict[str, Any]:
    month_keys = [part.strip() for part in str(months or "").split(",") if part.strip()]
    return {"targets": list_no_event_month_targets(current_database_file(), month_keys, prefer_job_id=job_id)}


@app.post("/api/jobs/{job_id}/no-event/assign-existing", tags=["Ereignisse"])
def api_assign_existing_no_event(job_id: str, body: dict) -> dict[str, Any]:
    target_event_id = str(body.get("target_event_id") or "")
    segments = list(body.get("segments") or [])
    selected_family_ids = sorted({
        int(value) for value in (body.get("family_ids") or []) if int(value) > 0
    })

    if segments:
        membership_payload = {
            "event_kind": "no_event",
            "no_event_segments": segments,
            "selected_family_ids": selected_family_ids,
            "confirm_cross_backup_membership": bool(
                body.get("confirm_cross_backup_membership")
            ),
        }
        try:
            membership_payload, membership, confirmation = _canonical_membership_preflight(
                membership_payload
            )
        except (ValueError, EventPreviewError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if confirmation is not None:
            return confirmation
        selected_family_ids = list(membership_payload["selected_family_ids"])

    try:
        with database_connection(current_database_file()) as connection:
            target_row = connection.execute(
                "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
                (target_event_id,),
            ).fetchone()

        # 0.27.0: Archivierte Monatssammlungen werden unabhaengig vom
        # Sicherungsauftrag direkt ueber den manuellen, read-only Archivworkflow
        # erweitert. Neue SSD-Familien werden unter "Später zuordnen" vorbereitet
        # und erst nach erfolgreicher Archiv-SHA-Pruefung dauerhaft gebunden.
        if target_row is not None and str(target_row["status"] or "") == "archived":
            from app.event_timeline import normalize_no_event_segments

            normalized_new = normalize_no_event_segments(segments) if segments else []
            target_job_id = str(target_row["job_id"])
            context = get_event_edit_context(
                current_database_file(), target_job_id, target_event_id
            )
            existing_segments = [
                {
                    "day_key": str(
                        item.get("day_key")
                        or str(item.get("start_datetime") or "")[:10]
                    ),
                    "start_time": str(
                        item.get("start_time")
                        or str(item.get("start_datetime") or "")[11:16]
                    ),
                    "end_time": str(
                        item.get("end_time")
                        or str(item.get("end_datetime") or "")[11:16]
                    ),
                }
                for item in (context.get("time_segments") or [])
            ]
            combined_segments = normalize_no_event_segments([
                *existing_segments,
                *[
                    {
                        "day_key": item["day_key"],
                        "start_time": item["start_time"],
                        "end_time": item["end_time"],
                    }
                    for item in normalized_new
                ],
            ])
            scope_segments = normalized_new or normalize_no_event_segments(existing_segments)

            incoming_available = (
                _available_families_for_event_payload(
                    job_id, {"selected_family_ids": selected_family_ids}
                )
                if selected_family_ids
                else list_job_available_families(current_database_file(), job_id)
            )
            requested_set = set(selected_family_ids)
            incoming_ids = {
                int(family["family_id"])
                for family in incoming_available
                if (not requested_set or int(family["family_id"]) in requested_set)
                and any(
                    segment["start_datetime"]
                    <= str(family.get("selected_capture_time") or "")[:19]
                    <= segment["end_datetime"]
                    for segment in scope_segments
                )
            }
            if not incoming_ids:
                raise ValueError(
                    "In den gewählten Zeitsegmenten gibt es keine freien Dateifamilien."
                )

            family_map = {
                int(family["family_id"]): dict(family)
                for family in (context.get("families") or [])
                if family.get("assigned_here")
            }
            for family in incoming_available:
                family_id = int(family["family_id"])
                if family_id in incoming_ids:
                    family_map[family_id] = dict(family)

            preview = build_event_preview(
                {
                    "event_kind": "no_event",
                    "event_name": str(target_row["name"] or "Ohne Ereignis"),
                    "no_event_segments": combined_segments,
                    "preserve_day_folders": bool(target_row["preserve_day_folders"]),
                    "folder_naming": _naming_snapshot_from_event_context(context),
                    "uses_time_range": False,
                    "start_date": combined_segments[0]["day_key"],
                    "end_date": combined_segments[-1]["day_key"],
                },
                list(family_map.values()),
            )
            archive_reservation = _reserve_archive_change_preview(
                target_event_id,
                preview,
            )
            try:
                result = propose_event_change(
                    current_database_file(),
                    target_job_id,
                    target_event_id,
                    preview,
                    event_name=str(target_row["name"] or "Ohne Ereignis"),
                    notes=str(target_row["notes"] or ""),
                    archive_root=current_archive_root(),
                    workspace_path=current_workspace_root(),
                )
            except Exception:
                _release_new_global_reservations(archive_reservation)
                raise
            return {
                "status": "archive_change_request_created",
                "event_id": target_event_id,
                "canonical_target_event_id": target_event_id,
                "assigned_family_count": len(incoming_ids),
                "family_ids": sorted(incoming_ids),
                "cross_job": target_job_id != str(job_id),
                "linkage_kind": "archive_change_request",
                "change_request_id": result["change_request_id"],
                "prepared_structure_path": result.get("prepared_structure_path") or "",
            }

        assignment_reservation = _reserve_global_family_ids(
            target_event_id,
            selected_family_ids,
        )
        assignment_committed = False
        try:
            assigned = assign_free_families_to_existing_no_event(
                current_database_file(),
                job_id,
                target_event_id,
                segments,
                family_ids=selected_family_ids or None,
            )
            assignment_committed = True
            if str(assigned.get("target_status") or "") == "applied":
                _promote_global_family_ids_owned(
                    target_event_id,
                    assigned.get("family_ids") or selected_family_ids,
                )
            return assigned
        except Exception:
            if not assignment_committed:
                _release_new_global_reservations(assignment_reservation)
            raise
    except (
        ValueError,
        EventPreviewError,
        EventChangeRequestError,
        LibraryRegistryError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/legacy-multi-backup/{legacy_event_id}/plan", tags=["Ereignisse"])
def api_legacy_multi_backup_plan(legacy_event_id: str) -> dict[str, Any]:
    from app.legacy_multi_backup import (
        LegacyMultiBackupError,
        build_legacy_reconcile_plan,
    )
    try:
        return build_legacy_reconcile_plan(
            current_database_file(),
            current_workspace_root(),
            legacy_event_id,
        )
    except LegacyMultiBackupError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/legacy-multi-backup/{legacy_event_id}/apply", tags=["Ereignisse"])
def api_legacy_multi_backup_apply(
    legacy_event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from app.legacy_multi_backup import (
        LegacyMultiBackupError,
        apply_legacy_reconcile,
    )
    try:
        return apply_legacy_reconcile(
            current_database_file(),
            current_workspace_root(),
            legacy_event_id,
            expected_plan_token=str(payload.get("plan_token") or ""),
            confirmation_phrase=str(payload.get("confirmation_phrase") or ""),
        )
    except (LegacyMultiBackupError, OSError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/event-structure-changes/{change_id}", tags=["Ereignisse"])
def api_event_structure_change(change_id: str) -> dict[str, Any]:
    try:
        return get_structure_change(current_database_file(), change_id)
    except EventStructureChangeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/confirm-applied", tags=["Ereignisse"])
def api_confirm_applied_structure_change(change_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return confirm_applied_structure_change(
            current_database_file(),
            current_workspace_root(),
            change_id,
            input_path=str(payload.get("input_path") or ""),
            input_paths=payload.get("input_paths") if isinstance(payload.get("input_paths"), dict) else None,
            app_version=RELEASE_VERSION,
        )
    except EventStructureChangeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/undo", tags=["Ereignisse"])
def api_undo_manual_event_change(change_id: str) -> dict[str, Any]:
    from app.manual_event_undo import undo_manual_applied_change
    try:
        return undo_manual_applied_change(
            current_database_file(), current_workspace_root(), change_id
        )
    except (EventStructureChangeError, OSError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/restore-folders", tags=["Ereignisse"])
def api_restore_empty_event_folders(change_id: str) -> dict[str, Any]:
    """Safe Undo of missing EMPTY folders in an Applied event."""
    from app.manual_structure_undo import undo_empty_folder_change
    try:
        return undo_empty_folder_change(
            current_database_file(), current_library_context().work_root, change_id
        )
    except (EventStructureChangeError, OSError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/restore-applied", tags=["Ereignisse"])
def api_restore_applied_structure(change_id: str) -> dict[str, Any]:
    """Restore verified camera originals and even empty former subevent folders.

    Unlike archive workflows, the shared workspace is writable. This action
    requires a complete, unchanged content-addressed physical snapshot.
    """
    from app.manual_subevent_restoration import restore_applied_subevents
    try:
        return restore_applied_subevents(
            current_database_file(), current_workspace_root(), change_id
        )
    except (EventStructureChangeError, OSError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/prepare-archive", tags=["Ereignisse"])
def api_prepare_archived_structure_change(change_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return prepare_archived_structure_change(
            current_database_file(),
            current_workspace_root(),
            change_id,
            input_path=str(payload.get("input_path") or ""),
            input_paths=payload.get("input_paths") if isinstance(payload.get("input_paths"), dict) else None,
            app_version=RELEASE_VERSION,
            work_root=current_library_context().work_root,
        )
    except EventStructureChangeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/event-structure-changes/{change_id}/verify-archive", tags=["Ereignisse"])
def api_verify_archived_structure_change(change_id: str) -> dict[str, Any]:
    try:
        return verify_archived_structure_change(
            current_database_file(),
            current_archive_root(),
            current_workspace_root(),
            change_id,
            work_root=current_library_context().work_root,
        )
    except EventStructureChangeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/tasks", tags=["Aufgaben"])
def api_global_tasks() -> dict[str, Any]:
    tasks = list_global_tasks(current_database_file())
    return {"tasks": tasks, "count": sum(int(t.get("count", 1)) for t in tasks)}


@app.get(
    "/api/external-change-notices/state",
    tags=["Aufgaben"],
)
def api_external_change_state() -> dict[str, Any]:
    return list_external_change_state(
        current_database_file()
    )


@app.post(
    "/api/external-change-notices/acknowledge",
    tags=["Aufgaben"],
)
def api_acknowledge_external_changes(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return acknowledge_external_notices(
        current_database_file(),
        [
            str(value)
            for value in (payload.get("notice_ids") or [])
            if str(value)
        ],
    )


@app.post(
    "/api/external-change-notices/repair-all",
    tags=["Aufgaben"],
)
def api_repair_all_external_changes() -> dict[str, Any]:
    try:
        result = repair_external_conflicts(
            current_database_file(),
            central_root=storage_paths(
                WORKSPACE_PATH
            )["backup_root"],
            library_work_root=current_library_context().work_root,
        )
        refresh_live_event_inventories(
            current_database_file(),
            current_workspace_root(),
            current_archive_root(),
        )
        reconcile_global_central_stock_state(
            force=True
        )
        detect_all_event_structure_changes(
            current_database_file(), current_workspace_root()
        )
        result["state"] = list_external_change_state(
            current_database_file()
        )
        return result
    except ExternalChangeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@app.post(
    "/api/external-change-notices/{notice_id}/repair",
    tags=["Aufgaben"],
)
def api_repair_external_change(
    notice_id: str,
) -> dict[str, Any]:
    try:
        result = repair_external_notice(
            current_database_file(),
            notice_id,
            central_root=storage_paths(
                WORKSPACE_PATH
            )["backup_root"],
            library_work_root=current_library_context().work_root,
        )
        refresh_live_event_inventories(
            current_database_file(),
            current_workspace_root(),
            current_archive_root(),
        )
        reconcile_global_central_stock_state(
            force=True
        )
        detect_all_event_structure_changes(
            current_database_file(), current_workspace_root()
        )
        return result
    except ExternalChangeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@app.post(
    "/api/external-change-notices/{notice_id}/dismiss",
    tags=["Aufgaben"],
)
def api_dismiss_external_change(
    notice_id: str,
) -> dict[str, Any]:
    try:
        return dismiss_external_notice(
            current_database_file(),
            notice_id,
        )
    except ExternalChangeError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.get("/api/jobs/{job_id}/event-mutations/active", tags=["Ereignisse"])
def api_active_event_mutation(job_id: str) -> dict[str, Any]:
    from app.event_mutation import get_active_mutation
    from app.database import database_connection
    with database_connection(current_database_file()) as connection:
        row = get_active_mutation(connection, job_id)
    if row is None:
        return {"active": False, "mutation": None}
    safe = {k: row.get(k) for k in (
        "id", "job_id", "anchor_event_id", "mutation_kind", "status",
        "affected_event_ids_json", "created_at", "updated_at"
    )}
    return {"active": True, "mutation": safe}


@app.post("/api/jobs/{job_id}/event-mutations/{mutation_id}/cancel", tags=["Ereignisse"], status_code=202)
def api_cancel_event_mutation(job_id: str, mutation_id: str) -> dict[str, Any]:
    """Bestätigt die Annahme; Ausführung ist unabhängig vom Browser."""
    try:
        result = cancel_queue.enqueue(current_database_file(), job_id, mutation_id)
        CANCEL_WORKER_WAKE.set()
        return result
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/background-activity", tags=["Aufträge"])
def api_background_activity() -> dict[str, Any]:
    """Kompakter, rein lesender Status für die Desktop-Hinweise."""
    return current_activity(current_database_file(), DATABASE_FILE)


@app.get("/api/background-cancellations", tags=["Ereignisse"])
def api_background_cancellations() -> dict[str, Any]:
    return {"operations": cancel_queue.list_visible(current_database_file())}


@app.get("/api/background-cancellations/{operation_id}", tags=["Ereignisse"])
def api_background_cancellation_status(operation_id: str) -> dict[str, Any]:
    result = cancel_queue.get(current_database_file(), operation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Verwerfauftrag nicht gefunden.")
    return result


@app.get("/api/workspace/summary", tags=["Arbeitsbereich"])
def api_global_workspace_summary(
    jobs: str = "",
    physical_refresh: bool = True,
) -> dict[str, Any]:
    """Canonical library workspace projection; independent of the display cache.

    The first inspection per process remains physical. A user-requested
    physical_refresh=True forces verification; ordinary view reads reuse
    a DB-stamp-scoped snapshot. Any destructive action checks physical truth
    separately and must not trust this display snapshot.
    """
    selected = [
        part.strip()
        for part in str(jobs or "").split(",")
        if part.strip()
    ]
    for job_id in selected:
        if get_job(current_database_file(), job_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Mindestens eine Sicherung wurde nicht gefunden.",
            )

    db_path = current_database_file()
    must_check = physical_refresh or view_cache.needs_first_physical_check(db_path)
    if must_check:
        refresh_live_event_inventories(
            db_path,
            current_workspace_root(),
            current_archive_root(),
        )
        reconcile_global_central_stock_state(
            force=True
        )
        detect_all_event_structure_changes(
            current_database_file(), current_workspace_root()
        )
        backfill_library_claims(
            REGISTRY_DATABASE_FILE,
            database_path=current_database_file(),
            library_id=current_library_context().library_id,
        )

        view_cache.mark_physical_checked(db_path)
        view_cache.invalidate(db_path)

    cache_key = tuple(sorted(selected))
    if not must_check:
        cached = view_cache.get_snapshot(db_path, "workspace", cache_key)
        if cached is not None:
            return cached

    excluded_by_job = {
        job_id: blocked_family_ids(
            REGISTRY_DATABASE_FILE,
            database_path=current_database_file(),
            library_id=current_library_context().library_id,
            job_id=job_id,
        )
        for job_id in selected
    }
    payload = build_global_workspace_summary(
        current_database_file(),
        selected,
        workspace_path=current_workspace_root(),
        excluded_family_ids_by_job=excluded_by_job,
    )

    suggestions: list[dict[str, Any]] = []
    for job_id in selected:
        job = get_job(current_database_file(), job_id) or {}
        label = str(job.get("source_volume_label") or job_id)
        for suggestion in list_event_suggestions(
            current_database_file(),
            job_id,
        ):
            suggestions.append({
                **suggestion,
                "source_job_id": job_id,
                "source_label": label,
            })
    payload["event_suggestions"] = suggestions
    view_cache.put_snapshot(db_path, "workspace", payload, cache_key)
    return payload

@app.get(
    "/api/jobs/{job_id}/workspace-summary",
    tags=["Arbeitsbereich"],
)
def api_workspace_summary(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    live_inventory = refresh_live_event_inventories(
        current_database_file(),
        current_workspace_root(),
        current_archive_root(),
        job_id=job_id,
    )

    blocked = blocked_family_ids(
        REGISTRY_DATABASE_FILE,
        database_path=current_database_file(),
        library_id=current_library_context().library_id,
        job_id=job_id,
    )
    day_groups = list_job_day_groups(
        current_database_file(),
        job_id,
        excluded_family_ids=blocked,
    )

    events = list_job_events(
        current_database_file(),
        job_id,
    )

    planning_overview = list_job_planning_overview(
        current_database_file(),
        job_id,
        workspace_path=current_workspace_root(),
        excluded_family_ids=blocked,
    )

    archive_reviews = list_archive_change_reviews(
        current_database_file(),
        job_id,
    )

    dated_groups = [
        group
        for group in day_groups
        if group.get("has_date")
    ]
    without_date = next(
        (
            group
            for group in day_groups
            if not group.get("has_date")
        ),
        None,
    )

    return {
        "job": job,
        "live_inventory": live_inventory,
        "day_groups": day_groups,
        "event_count": len(events),
        "events": events,
        "time_segments": list_job_time_segments(
            current_database_file(),
            job_id,
        ),
        "planning_overview": planning_overview,
        "released_archive_groups": list_global_released_archive_groups(
            current_database_file(),
            excluded_family_ids=blocked,
            workspace_path=current_workspace_root(),
        ),
        "archive_change_review_count": len(archive_reviews),
        "archive_change_reviews": archive_reviews,
        "statistics": {
            "day_count": len(dated_groups),
            "file_count": sum(
                int(group.get("file_count", 0))
                for group in day_groups
            ),
            "family_count": sum(
                int(group.get("family_count", 0))
                for group in day_groups
            ),
            "total_size_bytes": sum(
                int(group.get("total_size_bytes", 0))
                for group in day_groups
            ),
            "review_required_count": sum(
                int(group.get("review_required_count", 0))
                for group in day_groups
            ),
            "without_date_file_count": (
                int(without_date.get("file_count", 0))
                if without_date
                else 0
            ),
        },
    }

def _metadata_library_contexts() -> list[LibraryContext]:
    contexts = list_active_library_contexts(REGISTRY_DATABASE_FILE)
    # Metadatenkorrektur ist bibliotheksübergreifend sichtbar. Auch eine nach
    # Prozessstart aktivierte/ältere Bibliothek muss deshalb vor dem Lesen der
    # Korrekturtabelle sicher auf dem aktuellen Schema stehen.
    for context in contexts:
        ensure_library_database_schema(context)
    return contexts


def _metadata_task_location(
    correction_id: str,
) -> tuple[LibraryContext, dict[str, Any]]:
    for context in _metadata_library_contexts():
        try:
            task = get_metadata_correction(context.database_path, correction_id)
        except MetadataCorrectionError:
            continue
        return context, task
    raise MetadataCorrectionError("Metadatenauftrag wurde nicht gefunden.")


def _sync_completed_library_metadata_correction(
    context: LibraryContext,
    task: dict[str, Any],
) -> dict[str, Any]:
    if (
        str(task.get("area") or "") != "library"
        or str(task.get("status") or "") != "completed"
    ):
        return task

    detected = dict(task.get("detected") or {})
    job_id = str(detected.get("job_id") or "")
    family_key = str(detected.get("family_key") or "")
    if not job_id or not family_key:
        return task

    databases = [
        Path(str(row["database_path"]))
        for row in list_libraries(
            REGISTRY_DATABASE_FILE,
            active_only=False,
            registered_only=True,
        )
        if str(row.get("database_path") or "").strip()
    ]
    propagation = propagate_corrected_family(
        context.database_path,
        databases,
        job_id=job_id,
        family_key=family_key,
    )
    synchronize_global_central_stock()
    task["projection_sync"] = propagation
    return task


@app.get("/api/metadata-correction/areas", tags=["Metadatenkorrektur"])
def api_metadata_correction_areas() -> dict[str, Any]:
    current = current_library_context()
    general = metadata_area_paths(
        area="general",
        workspace_root=current.workspace_root,
        library_id=current.library_id,
        create=True,
    )
    multiple = metadata_area_paths(
        area="multiple",
        workspace_root=current.workspace_root,
        library_id=current.library_id,
        create=True,
    )
    library_paths = metadata_area_paths(
        area="library",
        workspace_root=current.workspace_root,
        library_id=current.library_id,
        create=True,
    )
    return {
        "areas": {
            "library": {
                "available": True,
                "grouped_by_library": False,
                "source_root": str(library_paths["input_root"]),
                "destination_root": str(library_paths["output_root"]),
            },
            "general": {
                "available": True,
                "root": str(general["root"]),
                "input_root": str(general["input_root"]),
                "output_root": str(general["output_root"]),
            },
            "multiple": {
                "available": True,
                "root": str(multiple["root"]),
                "input_root": str(multiple["input_root"]),
                "output_root": str(multiple["output_root"]),
            },
        }
    }


@app.get("/api/metadata-correction/scan", tags=["Metadatenkorrektur"])
def api_metadata_correction_scan(area: str = "library") -> dict[str, Any]:
    kind = str(area or "library").strip().lower()
    try:
        if kind in {"general", "multiple"}:
            context = current_library_context()
            return scan_metadata_area(
                area=kind,
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                database_path=context.database_path,
                library_name=context.display_name,
            )
        if kind != "library":
            raise MetadataCorrectionError("Unbekannter Metadatenbereich.")

        groups: list[dict[str, Any]] = []
        flat: list[dict[str, Any]] = []
        for context in _metadata_library_contexts():
            job_ids = set(
                list_library_import_job_ids(
                    REGISTRY_DATABASE_FILE,
                    context.library_id,
                )
            )
            group = scan_metadata_area(
                area="library",
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                database_path=context.database_path,
                library_name=context.display_name,
                allowed_job_ids=job_ids,
            )
            groups.append(group)
            flat.extend(group.get("files") or [])

        return {
            "area": "library",
            # groups remains as a compatibility field for older clients, but
            # 0.33.5 presents the shared Ohne_Datum stock as one list.
            "groups": groups,
            "files": flat,
            "summary": {
                "library_count": len(groups),
                "family_count": len(flat),
                "file_count": sum(
                    int(group.get("summary", {}).get("file_count") or 0)
                    for group in groups
                ),
                "needs_attention": sum(
                    int(group.get("summary", {}).get("needs_attention") or 0)
                    for group in groups
                ),
                "ready_to_reintegrate": sum(
                    int(group.get("summary", {}).get("ready_to_reintegrate") or 0)
                    for group in groups
                ),
            },
        }
    except (MetadataCorrectionError, MetadataError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/metadata-correction/multiple/preview", tags=["Metadatenkorrektur"])
def api_preview_multiple_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    context = current_library_context()
    try:
        selected_raw = payload.get("selected_relative_paths")
        selected_relative_paths = (
            [str(value) for value in selected_raw if str(value or "").strip()]
            if isinstance(selected_raw, list)
            else None
        )
        preview = preview_multiple_metadata_correction(
            workspace_root=context.workspace_root,
            library_id=context.library_id,
            reference_relative_path=str(
                payload.get("reference_relative_path") or ""
            ),
            proposed_datetime=payload.get("proposed_datetime"),
            selected_relative_paths=selected_relative_paths,
        )
        return {"preview": preview}
    except (MetadataCorrectionError, MetadataError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/metadata-correction/multiple/apply", tags=["Metadatenkorrektur"])
def api_apply_multiple_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    context = current_library_context()
    mode = str(payload.get("mode") or "apply").strip().lower()
    if mode not in {"apply", "apply_and_import"}:
        raise HTTPException(status_code=422, detail="Unbekannter Mehrfachkorrektur-Modus.")

    try:
        selected_raw = payload.get("selected_relative_paths")
        selected_relative_paths = (
            [str(value) for value in selected_raw if str(value or "").strip()]
            if isinstance(selected_raw, list)
            else None
        )
        if mode == "apply_and_import" and selected_relative_paths:
            selection_preview = preview_multiple_metadata_correction(
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                reference_relative_path=str(
                    payload.get("reference_relative_path") or ""
                ),
                proposed_datetime=payload.get("proposed_datetime"),
                selected_relative_paths=selected_relative_paths,
            )
            if bool(selection_preview.get("selection_is_subset")):
                raise MetadataCorrectionError(
                    "Eine Teilmenge kann korrigiert, aber nicht direkt als kompletter "
                    "Mehrfachkorrektur-Ordner in den Tagesbestand übernommen werden."
                )

        result = apply_multiple_metadata_correction(
            workspace_root=context.workspace_root,
            library_id=context.library_id,
            reference_relative_path=str(
                payload.get("reference_relative_path") or ""
            ),
            proposed_datetime=payload.get("proposed_datetime"),
            expected_preview_fingerprint=str(
                payload.get("preview_fingerprint") or ""
            ),
            selected_relative_paths=selected_relative_paths,
        )

        response: dict[str, Any] = {
            "applied": True,
            "result": result,
        }
        if mode == "apply_and_import":
            blocker = _folder_import_runtime_blocker()
            if blocker:
                raise MetadataCorrectionError(blocker)

            source_paths = metadata_area_paths(
                area="multiple",
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                create=True,
            )
            source = source_paths["root"]
            signature = quick_source_signature(source)
            now = datetime.now().astimezone()
            job_id = now.strftime("MULTI_IMPORT_%Y%m%d_%H%M%S_%f")
            job = create_job(
                DATABASE_FILE,
                job_id=job_id,
                kind="sd_import",
                trigger_type="manual",
                source_path=str(source),
                working_path=str(workspace_backup_root(WORKSPACE_PATH)),
                operation="metadata_multiple_import",
                source_volume_label="Mehrfachkorrektur",
                source_signature=signature,
                source_device_id=None,
            )
            response["import_queued"] = True
            response["job"] = job
        return response
    except (
        MetadataCorrectionError,
        MetadataError,
        GlobalStockError,
        LibraryRegistryError,
        ValueError,
        OSError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/metadata-correction/correct-batch", tags=["Metadatenkorrektur"])
def api_correct_metadata_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one metadata source type to many files without rescanning per item."""
    area = str(payload.get("area") or "").strip().lower()
    source_type = str(payload.get("source_type") or "").strip()
    raw_items = payload.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    if area not in {"library", "general"}:
        raise HTTPException(status_code=422, detail="Mehrfachkorrektur ist für diesen Bereich nicht verfügbar.")
    if not source_type or not items:
        raise HTTPException(status_code=422, detail="Metadaten-Quelltyp oder Auswahl fehlt.")

    def safe_source(base: Path, relative_value: Any) -> Path:
        relative = Path(str(relative_value or "").replace("\\", "/").strip("/"))
        if (
            not relative.parts
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise MetadataCorrectionError("Unsicherer Metadatenpfad.")
        root = Path(base).resolve(strict=False)
        source = (root / relative).resolve(strict=False)
        try:
            source.relative_to(root)
        except ValueError as error:
            raise MetadataCorrectionError("Metadatenpfad verlässt den verwalteten Bereich.") from error
        if not source.is_file() or source.is_symlink():
            raise MetadataCorrectionError("Ausgewählte Metadatendatei fehlt: " + relative.as_posix())
        return source

    def source_candidate(row: dict[str, Any]) -> dict[str, Any]:
        candidates = sorted(
            (
                dict(candidate)
                for candidate in (row.get("metadata_candidates") or [])
                if bool(candidate.get("usable"))
                and str(candidate.get("normalized_datetime") or "").strip()
            ),
            key=lambda candidate: (
                int(candidate.get("priority") or 999),
                str(candidate.get("tag_name") or ""),
            ),
        )
        for candidate in candidates:
            logical = str(candidate.get("source_type") or "").strip()
            if not logical:
                logical = str(candidate.get("tag_name") or "").rsplit(":", 1)[-1]
            if logical == source_type:
                return candidate
        raise MetadataCorrectionError(
            f"Mindestens eine ausgewählte Datei besitzt den Quelltyp „{source_type}“ nicht mehr."
        )

    try:
        prepared: list[dict[str, Any]] = []
        context_cache: dict[str, tuple[LibraryContext, set[str], dict[int, dict[str, Any]], Path]] = {}

        if area == "library":
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                library_id = str(raw.get("library_id") or "").strip()
                family_id = int(raw.get("family_id") or 0)
                if not library_id or not family_id:
                    raise MetadataCorrectionError("Bibliothek oder Familie fehlt in der Mehrfachauswahl.")
                cached = context_cache.get(library_id)
                if cached is None:
                    context = resolve_library_context(REGISTRY_DATABASE_FILE, library_id)
                    ensure_library_database_schema(context)
                    job_ids = set(list_library_import_job_ids(REGISTRY_DATABASE_FILE, context.library_id))
                    scan = scan_metadata_area(
                        area="library",
                        workspace_root=context.workspace_root,
                        library_id=context.library_id,
                        database_path=context.database_path,
                        library_name=context.display_name,
                        allowed_job_ids=job_ids,
                    )
                    by_family = {
                        int(row["family_id"]): dict(row)
                        for row in (scan.get("files") or [])
                        if row.get("family_id") is not None
                    }
                    root = metadata_area_paths(
                        area="library",
                        workspace_root=context.workspace_root,
                        library_id=context.library_id,
                        create=True,
                    )["output_root"].resolve(strict=False)
                    cached = (context, job_ids, by_family, root)
                    context_cache[library_id] = cached
                context, job_ids, by_family, root = cached
                row = by_family.get(family_id)
                if row is None:
                    raise MetadataCorrectionError("Eine ausgewählte Ohne-Datum-Familie wurde nicht gefunden.")
                candidate = source_candidate(row)
                source = safe_source(root, row.get("relative_path"))
                prepared.append({
                    "context": context,
                    "job_ids": job_ids,
                    "row": row,
                    "source": source,
                    "candidate": candidate,
                    "family_id": family_id,
                })
        else:
            context = current_library_context()
            ensure_library_database_schema(context)
            scan = scan_metadata_area(
                area="general",
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                database_path=context.database_path,
                library_name=context.display_name,
            )
            by_relative = {
                str(row.get("relative_path") or ""): dict(row)
                for row in (scan.get("files") or [])
            }
            root = metadata_area_paths(
                area="general",
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                create=True,
            )["input_root"].resolve(strict=False)
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                relative = str(raw.get("relative_path") or "").replace("\\", "/").strip("/")
                row = by_relative.get(relative)
                if row is None:
                    raise MetadataCorrectionError("Eine ausgewählte Allgemein-Datei wurde nicht gefunden.")
                candidate = source_candidate(row)
                source = safe_source(root, relative)
                prepared.append({
                    "context": context,
                    "job_ids": None,
                    "row": row,
                    "source": source,
                    "candidate": candidate,
                    "family_id": None,
                })

        if len(prepared) != len(items):
            raise MetadataCorrectionError("Die Mehrfachauswahl enthält ungültige Einträge.")

        completed: list[dict[str, Any]] = []
        touched_families: list[tuple[LibraryContext, str, str]] = []
        for item in prepared:
            context = item["context"]
            row = item["row"]
            candidate = item["candidate"]
            task = execute_metadata_correction(
                context.database_path,
                area=area,
                relative_path=str(row.get("relative_path") or ""),
                family_id=item["family_id"],
                proposed_datetime=str(candidate["normalized_datetime"])[:19],
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                library_name=context.display_name,
                allowed_job_ids=item["job_ids"],
                proposal_source_tag=str(candidate.get("tag_name") or ""),
                _prevalidated_row=row,
                _prevalidated_source=item["source"],
            )
            completed.append(task)
            if area == "library":
                detected = dict(task.get("detected") or {})
                job_id = str(detected.get("job_id") or "")
                family_key = str(detected.get("family_key") or "")
                if job_id and family_key:
                    touched_families.append((context, job_id, family_key))

        if touched_families:
            databases = [
                Path(str(row["database_path"]))
                for row in list_libraries(
                    REGISTRY_DATABASE_FILE,
                    active_only=False,
                    registered_only=True,
                )
                if str(row.get("database_path") or "").strip()
            ]
            for context, job_id, family_key in touched_families:
                propagate_corrected_family(
                    context.database_path,
                    databases,
                    job_id=job_id,
                    family_key=family_key,
                )
            synchronize_global_central_stock()

        return {
            "tasks": completed,
            "count": len(completed),
            "source_type": source_type,
        }
    except (
        MetadataCorrectionError,
        MetadataError,
        GlobalStockError,
        LibraryRegistryError,
        ValueError,
        OSError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/metadata-correction/correct", tags=["Metadatenkorrektur"])
def api_correct_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Write and verify one explicitly confirmed correction in one request."""
    area = str(payload.get("area") or "library").strip().lower()
    try:
        if area == "library":
            library_id = str(payload.get("library_id") or "").strip()
            if not library_id:
                raise MetadataCorrectionError(
                    "Bibliothek für die Ohne-Datum-Familie fehlt."
                )
            context = resolve_library_context(REGISTRY_DATABASE_FILE, library_id)
            ensure_library_database_schema(context)
            job_ids = set(
                list_library_import_job_ids(
                    REGISTRY_DATABASE_FILE,
                    context.library_id,
                )
            )
            task = execute_metadata_correction(
                context.database_path,
                area="library",
                relative_path=str(payload.get("relative_path") or ""),
                family_id=int(payload.get("family_id") or 0),
                proposed_datetime=payload.get("proposed_datetime"),
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                library_name=context.display_name,
                allowed_job_ids=job_ids,
                proposal_source_tag=str(payload.get("proposal_source_tag") or "") or None,
            )
        elif area == "general":
            context = current_library_context()
            ensure_library_database_schema(context)
            task = execute_metadata_correction(
                context.database_path,
                area="general",
                relative_path=str(payload.get("relative_path") or ""),
                proposed_datetime=payload.get("proposed_datetime"),
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                library_name=context.display_name,
                proposal_source_tag=str(payload.get("proposal_source_tag") or "") or None,
            )
        else:
            raise MetadataCorrectionError(
                "Mehrfachkorrektur ist noch nicht aktiviert."
            )

        task = _sync_completed_library_metadata_correction(context, task)
        return {"task": task}
    except (
        MetadataCorrectionError,
        MetadataError,
        GlobalStockError,
        LibraryRegistryError,
        ValueError,
        OSError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/metadata-correction/general/reintegrate", tags=["Metadatenkorrektur"], status_code=202)
def api_reintegrate_general_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Queue selected corrected General files for the verified day-stock import path."""
    raw_items = payload.get("items")
    values = raw_items if isinstance(raw_items, list) else [payload]
    relatives: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        value = str(raw.get("relative_path") or "").replace("\\", "/").strip("/")
        path = Path(value)
        if (
            not value
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or value in seen
        ):
            continue
        seen.add(value)
        relatives.append(path.as_posix())
    if not relatives:
        raise HTTPException(status_code=422, detail="Keine Allgemein-Datei zum Einsortieren ausgewählt.")

    context = current_library_context()
    try:
        scan = scan_metadata_area(
            area="general",
            workspace_root=context.workspace_root,
            library_id=context.library_id,
            database_path=context.database_path,
            library_name=context.display_name,
        )
        by_relative = {
            str(row.get("relative_path") or ""): dict(row)
            for row in (scan.get("files") or [])
        }
        area_paths = metadata_area_paths(
            area="general",
            workspace_root=context.workspace_root,
            library_id=context.library_id,
            create=True,
        )
        general_root = area_paths["root"].resolve(strict=False)
        selected: list[tuple[str, Path, dict[str, Any]]] = []
        for relative in relatives:
            row = by_relative.get(relative)
            if row is None:
                raise MetadataCorrectionError(
                    "Die ausgewählte Allgemein-Datei wurde nicht gefunden: " + relative
                )
            if (
                not str(row.get("selected_capture_time") or "").strip()
                or str(row.get("capture_time_confidence") or "")
                not in {"high", "medium"}
            ):
                raise MetadataCorrectionError(
                    "Vor der Übernahme in den Tagesbestand muss jede ausgewählte Datei eine belastbare Aufnahmezeit besitzen."
                )
            source = (general_root / Path(relative)).resolve(strict=False)
            source.relative_to(general_root)
            if not source.is_file() or source.is_symlink():
                raise MetadataCorrectionError("Allgemein-Datei fehlt: " + relative)
            selected.append((relative, source, row))

        # A known camera original is not imported as a new source merely
        # because its metadata bytes were corrected in Allgemein.
        known_original_sha = {
            str(row.get("sha256") or "")
            for row in list_imported_media_origins(DATABASE_FILE)
            if str(row.get("sha256") or "")
        }
        # Eine bereits bekannte Aufnahme kann selbst schon einmal korrigiert
        # worden sein. Dann unterscheiden sich sha256_original und der
        # aktuelle physische Hash. Beide Identitäten verhindern, dass
        # "Allgemein" daraus künstlich einen neuen Import erzeugt.
        with database_connection(DATABASE_FILE) as main_connection:
            known_current_sha = {
                str(row["sha256"])
                for row in main_connection.execute(
                    """SELECT DISTINCT COALESCE(sha256_current,sha256_original) AS sha256
                       FROM files
                       WHERE COALESCE(TRIM(COALESCE(sha256_current,sha256_original)),'')<>''"""
                ).fetchall()
                if str(row["sha256"] or "")
            }
        known_camera_sha = known_original_sha | known_current_sha

        with database_connection(context.database_path) as connection:
            for relative, source, _row in selected:
                current_sha = sha256_file(source)
                correction = connection.execute(
                    """SELECT source_sha256
                       FROM metadata_corrections
                       WHERE area='general'
                         AND source_relative_path=?
                         AND status='completed'
                       ORDER BY COALESCE(completed_at,created_at) DESC
                       LIMIT 1""",
                    (relative,),
                ).fetchone()
                original_sha = str(correction["source_sha256"] or "") if correction else ""
                if current_sha in known_camera_sha or (
                    original_sha and original_sha in known_camera_sha
                ):
                    raise MetadataCorrectionError(
                        "Diese Datei gehört bereits zu einem bekannten Kameraimport. "
                        "Es wird keine neue Sicherung/Provenienz angelegt; bitte die bekannte Aufnahme im Bibliotheksbestand korrigieren."
                    )

        metadata_root = storage_paths(context.workspace_root)["metadata_root"].resolve(strict=False)
        stage_parent = (metadata_root / ".general-import").resolve(strict=False)
        stage_parent.mkdir(parents=True, exist_ok=True)
        job_id = datetime.now().astimezone().strftime("GENERAL_IMPORT_%Y%m%d_%H%M%S_%f")
        stage = (stage_parent / job_id).resolve(strict=False)
        stage.mkdir(parents=True, exist_ok=False)
        try:
            for relative, source, _row in selected:
                target = (stage / Path(relative)).resolve(strict=False)
                target.relative_to(stage)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if (
                    int(target.stat().st_size) != int(source.stat().st_size)
                    or sha256_file(target) != sha256_file(source)
                ):
                    raise MetadataCorrectionError(
                        "Staging-Kopie konnte nicht verifiziert werden: " + relative
                    )
            signature = quick_source_signature(stage)
            job = create_job(
                DATABASE_FILE,
                job_id=job_id,
                kind="sd_import",
                trigger_type="manual",
                source_path=str(stage),
                working_path=str(workspace_backup_root(WORKSPACE_PATH)),
                operation="metadata_general_import",
                source_volume_label="Metadatenkorrektur · Allgemein",
                source_signature=signature,
                source_device_id=None,
            )
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

        return {
            "queued": True,
            "job": job,
            "file_count": len(selected),
        }
    except (
        MetadataCorrectionError,
        MetadataError,
        LibraryRegistryError,
        ValueError,
        OSError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/metadata-correction/reintegrate", tags=["Metadatenkorrektur"])
def api_reintegrate_metadata_families(payload: dict[str, Any]) -> dict[str, Any]:
    """Explicitly move corrected Ohne_Datum families into canonical day stock."""
    raw_items = payload.get("items")
    if isinstance(raw_items, list):
        items = raw_items
    else:
        items = [payload]

    normalized: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        library_id = str(raw.get("library_id") or "").strip()
        family_id = int(raw.get("family_id") or 0)
        key = (library_id, family_id)
        if not library_id or not family_id or key in seen:
            continue
        seen.add(key)
        normalized.append(key)

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="Keine korrigierte Dateifamilie zum Einsortieren ausgewählt.",
        )

    try:
        results: list[dict[str, Any]] = []
        touched: list[tuple[LibraryContext, dict[str, Any]]] = []
        for library_id, family_id in normalized:
            context = resolve_library_context(REGISTRY_DATABASE_FILE, library_id)
            ensure_library_database_schema(context)
            result = reintegrate_library_metadata_family(
                context.database_path,
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                family_id=family_id,
            )
            results.append(result)
            touched.append((context, result))

        databases = [
            Path(str(row["database_path"]))
            for row in list_libraries(
                REGISTRY_DATABASE_FILE,
                active_only=False,
                registered_only=True,
            )
            if str(row.get("database_path") or "").strip()
        ]
        for context, result in touched:
            propagate_corrected_family(
                context.database_path,
                databases,
                job_id=str(result["job_id"]),
                family_key=str(result["family_key"]),
            )
        synchronize_global_central_stock()
        return {
            "results": results,
            "family_count": len(results),
            "file_count": sum(int(row.get("file_count") or 0) for row in results),
        }
    except (
        MetadataCorrectionError,
        GlobalStockError,
        LibraryRegistryError,
        ValueError,
        OSError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/metadata-correction/tasks", tags=["Metadatenkorrektur"])
def api_metadata_correction_tasks(include_completed: bool = False) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for context in _metadata_library_contexts():
        for task in list_metadata_corrections(
            context.database_path,
            include_completed=include_completed,
        ):
            task_id = str(task.get("id") or "")
            if not task_id or task_id in seen:
                continue
            seen.add(task_id)
            item = dict(task)
            item["library_id"] = context.library_id
            item["library_name"] = context.display_name
            tasks.append(item)
    tasks.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/metadata-correction/tasks", tags=["Metadatenkorrektur"], status_code=201)
def api_prepare_metadata_correction(payload: dict[str, Any]) -> dict[str, Any]:
    area = str(payload.get("area") or "library").strip().lower()
    try:
        if area == "library":
            library_id = str(payload.get("library_id") or "").strip()
            if not library_id:
                raise MetadataCorrectionError("Bibliothek für die Ohne-Datum-Familie fehlt.")
            context = resolve_library_context(REGISTRY_DATABASE_FILE, library_id)
            job_ids = set(
                list_library_import_job_ids(
                    REGISTRY_DATABASE_FILE,
                    context.library_id,
                )
            )
            task = create_metadata_correction(
                context.database_path,
                area="library",
                relative_path=str(payload.get("relative_path") or ""),
                family_id=int(payload.get("family_id") or 0),
                proposed_datetime=payload.get("proposed_datetime"),
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                library_name=context.display_name,
                allowed_job_ids=job_ids,
            )
        elif area == "general":
            context = current_library_context()
            task = create_metadata_correction(
                context.database_path,
                area="general",
                relative_path=str(payload.get("relative_path") or ""),
                proposed_datetime=payload.get("proposed_datetime"),
                workspace_root=context.workspace_root,
                library_id=context.library_id,
                library_name=context.display_name,
            )
        else:
            raise MetadataCorrectionError(
                "Mehrfachkorrektur ist noch nicht aktiviert."
            )
    except (MetadataCorrectionError, MetadataError, LibraryRegistryError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"task": task}


@app.post("/api/metadata-correction/tasks/{correction_id}/apply", tags=["Metadatenkorrektur"])
def api_apply_metadata_correction(correction_id: str) -> dict[str, Any]:
    try:
        context, before = _metadata_task_location(correction_id)
        task = apply_metadata_correction(
            context.database_path,
            correction_id,
            workspace_root=context.workspace_root,
            library_id=context.library_id,
        )
        task = _sync_completed_library_metadata_correction(context, task)
        return {"task": task}
    except (MetadataCorrectionError, GlobalStockError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/metadata-correction/tasks/{correction_id}/cancel", tags=["Metadatenkorrektur"])
def api_cancel_metadata_correction(correction_id: str) -> dict[str, Any]:
    try:
        context, _task = _metadata_task_location(correction_id)
        task = cancel_metadata_correction(
            context.database_path,
            correction_id,
        )
    except MetadataCorrectionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"task": task}


@app.get(
    "/api/jobs/{job_id}/files",
    tags=["Metadaten"],
)
def api_job_files(
    job_id: str,
    review_only: bool = False,
) -> dict[str, Any]:
    job = get_job(
        current_database_file(),
        job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Auftrag wurde nicht gefunden.",
        )

    files = list_job_files(
        current_database_file(),
        job_id,
    )

    if review_only:
        files = [
            record
            for record in files
            if record.get(
                "review_status"
            ) == "required"
        ]

    return {
        "job_id": job_id,
        "review_only": review_only,
        "count": len(files),
        "files": files,
    }


@app.get(
    "/api/files/{file_id}/metadata",
    tags=["Metadaten"],
)
def api_file_metadata(
    file_id: int,
) -> dict[str, Any]:
    candidates = list_file_metadata_candidates(
        current_database_file(),
        file_id,
    )

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=(
                "Datei oder Metadatenkandidaten "
                "wurden nicht gefunden."
            ),
        )

    return {
        "file_id": file_id,
        "count": len(candidates),
        "candidates": candidates,
    }


@app.post(
    "/api/jobs/metadata-test",
    tags=["Metadaten"],
    status_code=202,
)
def api_run_metadata_test() -> JSONResponse:
    now = datetime.now().astimezone()

    job_id = now.strftime(
        "METADATA_TEST_%Y%m%d_%H%M%S_%f"
    )

    source = (
        current_workspace_root()
        / "_test"
        / "METADATA_FIXTURES_001"
    )

    if not source.is_dir():
        raise HTTPException(
            status_code=500,
            detail=(
                "Kontrollierter Metadaten-Testbestand "
                "wurde nicht gefunden."
            ),
        )

    try:
        job = create_job(
            current_database_file(),
            job_id=job_id,
            kind="simulation",
            trigger_type="manual",
            source_path=str(source),
            working_path=None,
            operation="metadata_fixture_analysis",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "message": (
                "Metadaten-Testauftrag wurde "
                "in die Warteschlange aufgenommen."
            ),
            "job": job,
        },
    )


@app.post(
    "/api/jobs/simulated",
    tags=["Aufträge"],
    status_code=202,
)
def api_run_simulated_job() -> JSONResponse:
    now = datetime.now().astimezone()

    job_id = now.strftime(
        "WEB_SIM_%Y%m%d_%H%M%S_%f"
    )

    template = (
        current_workspace_root()
        / "_test"
        / "SD_SIM_001"
        / "simulierte-sd"
    )

    working_path = (
        current_workspace_root()
        / WORK_DIRECTORY_NAME
    )

    try:
        job = create_job(
            current_database_file(),
            job_id=job_id,
            kind="simulation",
            trigger_type="manual",
            source_path=str(template),
            working_path=str(working_path),
            operation="sd_lifecycle_simulation",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "message": (
                "Simulationsauftrag wurde "
                "in die Warteschlange aufgenommen."
            ),
            "job": job,
        },
    )


@app.get(
    "/assets/bibliothekar-logo-v2.svg",
    include_in_schema=False,
)
def bibliothekar_brand_logo() -> FileResponse:
    """Derselbe freigestellte SVG-Schriftzug für alle Bibliothekar-Seiten."""
    return FileResponse(
        Path(__file__).with_name("bibliothekar-logo-v2.svg"),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@app.get(
    "/manifest.webmanifest",
    include_in_schema=False,
)
def web_app_manifest(request: Request) -> JSONResponse:
    """Web-App-Manifest mit iPhone-spezifischer Hochformatsperre.

    iPad/Tablet bleibt absichtlich frei, damit dessen eigenes Layout später
    unabhängig gestaltet werden kann. Die normale Browser-Website wird durch
    das Manifest nicht in ihrer Ausrichtung eingeschränkt.
    """
    user_agent = request.headers.get("user-agent", "").lower()
    is_iphone = "iphone" in user_agent or "ipod" in user_agent
    return JSONResponse(
        content={
            "id": "/",
            "name": "Bibliothekar",
            "short_name": "Bibliothekar",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary" if is_iphone else "any",
            "theme_color": "#15222c",
            "background_color": "#15222c",
        },
        media_type="application/manifest+json",
        headers={
            "Cache-Control": "no-cache",
            "Vary": "User-Agent",
        },
    )


@app.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def index() -> str:
    return apply_shell("""
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <meta
    name="theme-color"
    content="#0d0f12"
  >
  <title>Import und Prüfung</title>

  <style>
    :root {
      color-scheme: dark;
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;

      --background: #0d0f12;
      --surface: #171a1f;
      --surface-soft: #1d2127;
      --border: #2b3038;
      --text: #f2f3f5;
      --muted: #9ba3ae;
      --accent: #e8e8e8;
      --accent-text: #101114;
      --success: #63d28d;
      --warning: #f1bf5b;
      --danger: #ef767a;
      --running: #72a7ff;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background:
        radial-gradient(
          circle at top right,
          rgba(255, 255, 255, 0.06),
          transparent 32rem
        ),
        var(--background);
      color: var(--text);
      min-height: 100vh;
    }

    main {
      width: min(1080px, 100%);
      margin: 0 auto;
      padding:
        max(1.2rem, env(safe-area-inset-top))
        max(1rem, env(safe-area-inset-right))
        max(3rem, env(safe-area-inset-bottom))
        max(1rem, env(safe-area-inset-left));
    }

    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.4rem;
    }

    h1 {
      margin: 0;
      font-size: clamp(1.8rem, 5vw, 3rem);
      line-height: 1;
      letter-spacing: -0.045em;
    }

    .subtitle {
      margin: 0.65rem 0 0;
      color: var(--muted);
      line-height: 1.45;
    }

    .version {
      flex: 0 0 auto;
      padding: 0.45rem 0.7rem;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      font-size: 0.82rem;
    }

    .grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.85rem;
      margin-bottom: 1.2rem;
    }

    .card {
      border: 1px solid var(--border);
      border-radius: 18px;
      background:
        linear-gradient(
          145deg,
          rgba(255, 255, 255, 0.025),
          transparent
        ),
        var(--surface);
      padding: 1.1rem;
      box-shadow:
        0 14px 40px rgba(0, 0, 0, 0.18);
    }

    .status-label {
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .status-value {
      margin-top: 0.45rem;
      font-size: 1.15rem;
      font-weight: 700;
    }

    .status-detail {
      margin-top: 0.35rem;
      color: var(--muted);
      font-size: 0.86rem;
    }

    .main-navigation,
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
    }

    .main-navigation { margin:0; }
    .global-header { position:sticky; top:0; z-index:60; display:flex; align-items:flex-start; justify-content:space-between; gap:18px; padding:12px 0; background:rgba(9,11,13,.96); backdrop-filter:blur(16px); }
    .global-header > div:first-child { min-width:240px; }
    .top-button { width:42px; min-width:42px; padding:0; font-size:1.2rem; }

    .main-navigation button[aria-current="page"] { border:2px solid #f2f3f5; background:var(--surface-soft); opacity:1; color:var(--text); }

    .toolbar {
      margin: 1.3rem 0;
    }

    .import-panel {
      margin-top: 1.2rem;
    }

    .import-panel h2 {
      margin: 0;
      font-size: 1.2rem;
    }

    .bk-import-head {
      display:flex;
      align-items:center;
      flex-wrap:wrap;
      gap:0.55rem;
    }

    .bk-copy-warning {
      color:var(--warning);
      font-size:0.82rem;
      line-height:1.35;
    }

    .bk-job-actions {
      display:flex;
      flex-wrap:wrap;
      gap:0.55rem;
      margin-top:0.8rem;
    }

    .bk-job-actions button {
      min-height:38px;
      padding:0.45rem 0.75rem;
    }

    .import-controls {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.75rem;
      margin-top: 0.95rem;
    }

    select {
      width: 100%;
      min-height: 48px;
      border: 1px solid var(--border);
      border-radius: 13px;
      padding: 0.75rem 0.9rem;
      background: var(--surface-soft);
      color: var(--text);
      font: inherit;
    }

    .source-detail {
      margin-top: 0.65rem;
      color: var(--muted);
      font-size: 0.86rem;
      line-height: 1.4;
    }

    .diagnostics {
      margin-top: 1.2rem;
      border: 1px solid var(--border);
      border-radius: 15px;
      padding: 0.85rem 1rem;
      background: rgba(255, 255, 255, 0.018);
    }

    .diagnostics summary {
      color: var(--muted);
      font-weight: 700;
    }

    .diagnostics-content {
      padding-top: 0.8rem;
    }

    button {
      appearance: none;
      border: 0;
      border-radius: 13px;
      min-height: 48px;
      padding: 0.8rem 1.05rem;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
      transition:
        transform 120ms ease,
        opacity 120ms ease;
    }

    button:active {
      transform: scale(0.98);
    }

    button:disabled { cursor:not-allowed; opacity:0.55; }
    .mount-state { display:flex; flex-direction:column; align-items:flex-start; justify-content:center; min-width:0; min-height:48px; cursor:default; overflow:hidden; overflow-wrap:anywhere; }
    .mount-state strong { display:block; }
    .mount-state span { display:block; margin-top:4px; font-size:.88rem; color:var(--muted); }
    .mount-state details { width:100%; margin-top:7px; color:var(--muted); font-size:.82rem; }
    .mount-state code { display:block; max-width:100%; margin-top:6px; white-space:normal; overflow-wrap:anywhere; color:var(--muted); }
    .mount-state.verified { border-color:var(--success); color:var(--success); }
    .sd-actions { grid-template-columns:minmax(220px,1fr) auto auto auto; }
    @media (max-width:900px) { .sd-actions { grid-template-columns:1fr 1fr; } .sd-actions .mount-state { grid-column:1/-1; } }

    .primary {
      background: var(--accent);
      color: var(--accent-text);
    }

    .secondary {
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
    }

    .notice {
      min-height: 1.3rem;
      color: var(--muted);
      font-size: 0.9rem;
    }

    section h2 {
      margin: 1.8rem 0 0.9rem;
      font-size: 1.25rem;
    }

    .jobs {
      display: grid;
      gap: 0.85rem;
    }

    .job {
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--surface);
      padding: 1rem;
    }

    .job-header {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
    }

    .job-title {
      min-width: 0;
    }

    .job-name {
      font-weight: 750;
      overflow-wrap: anywhere;
    }

    .job-description,
    .section-description {
      color: var(--muted);
      line-height: 1.45;
    }

    .job-description {
      margin-top: 0.3rem;
      font-size: 0.88rem;
    }

    .job-time {
      margin-top: 0.38rem;
      color: var(--muted);
      font-size: 0.82rem;
    }

    .badge {
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 0.38rem 0.65rem;
      font-size: 0.78rem;
      font-weight: 750;
      background: var(--surface-soft);
      color: var(--muted);
    }

    .badge.completed {
      color: var(--success);
    }

    .badge.failed {
      color: var(--danger);
    }

    .badge.interrupted {
      color: var(--warning);
    }

    .badge.active {
      color: var(--running);
    }

    .message {
      margin-top: 0.85rem;
      color: var(--text);
      line-height: 1.4;
    }

    .progress-stack {
      display: grid;
      gap: 0.38rem;
      margin-top: 0.78rem;
    }

    .progress-stack.completed-only {
      gap: 0;
    }

    .progress-row {
      display: grid;
      gap: 0.18rem;
    }

    .progress-caption {
      display: flex;
      gap: 1rem;
      color: var(--muted);
      font-size: 0.76rem;
      line-height: 1.1;
    }

    .progress-stack.completed-only .progress-caption {
      color: var(--success);
      font-weight: 700;
    }

    .progress {
      height: 9px;
      margin-top: 0;
      overflow: hidden;
      border-radius: 999px;
      background: #0d0f12;
      border: 1px solid #252931;
    }

    .progress > div {
      height: 100%;
      width: 0;
      border-radius: inherit;
      background: var(--running);
      transition: width 300ms ease;
    }

    .progress > div.completed {
      background: var(--success);
    }

    .job-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem 1rem;
      margin-top: 0.8rem;
      color: var(--muted);
      font-size: 0.82rem;
    }

    details {
      margin-top: 0.85rem;
      border-top: 1px solid var(--border);
      padding-top: 0.75rem;
    }

    summary {
      color: var(--muted);
      cursor: pointer;
      user-select: none;
    }

    pre {
      max-height: 28rem;
      overflow: auto;
      margin: 0.75rem 0 0;
      padding: 0.85rem;
      border-radius: 12px;
      background: #0a0c0f;
      color: #cfd4db;
      font-size: 0.75rem;
      line-height: 1.45;
      white-space: pre-wrap;
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
      padding: 2rem 1rem;
      border: 1px dashed var(--border);
      border-radius: 18px;
      color: var(--muted);
      text-align: center;
    }

    .error-text {
      color: var(--danger);
    }

    @media (max-width: 580px) {
      header {
        display: block;
      }

      .version {
        display: inline-block;
        margin-top: 0.85rem;
      }

      .toolbar button {
        flex: 1 1 auto;
      }

      .import-controls {
        grid-template-columns: 1fr;
      }

      .job-header {
        display: block;
      }

      .badge {
        display: inline-block;
        margin-top: 0.65rem;
      }
    }
  
    html, body { background: #090b0d !important; min-height:100%; }
    body::before { content:""; position:fixed; inset:-120px 0; background:#090b0d; z-index:-1000; pointer-events:none; }
    #refresh-button { display: none !important; }
    .page-intro { position:static; margin-bottom:12px; }
    .page-title-row { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
    .global-navigation-bar { position:sticky; top:0; z-index:60; display:flex; align-items:center; gap:10px; margin:0 0 18px; padding:10px 0; background:rgba(9,11,13,.96); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); }
    .global-navigation-bar .main-navigation { flex:1 1 auto; flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; }
    .global-navigation-bar .main-navigation::-webkit-scrollbar { display:none; }
    .global-navigation-bar .main-navigation button { flex:0 0 auto; white-space:nowrap; }
    @media (max-width:580px) {
      .page-title-row { display:block; }
      .global-navigation-bar { margin-left:-2px; margin-right:-2px; }
    }
  
    .global-task-fab { position:fixed; right:18px; bottom:18px; z-index:1200; width:50px; height:50px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:22px; box-shadow:0 8px 28px rgba(0,0,0,.35); background:#20252b; border:1px solid #4a5663; }
    .global-task-fab.visible { display:flex; }
    .global-task-badge.hidden { display:none !important; }
    .global-task-badge { position:absolute; right:-4px; top:-6px; min-width:22px; height:22px; padding:0 5px; border-radius:12px; background:#e04f5f; color:white; border:2px solid #090b0d; font-size:12px; font-weight:800; display:flex; align-items:center; justify-content:center; }
    .global-task-panel { position:fixed; right:18px; bottom:78px; z-index:1199; width:min(390px,calc(100vw - 36px)); max-height:60vh; overflow:auto; padding:14px; border-radius:14px; border:1px solid #3b424a; background:#181c20; box-shadow:0 14px 44px rgba(0,0,0,.5); display:none; }
    .global-task-panel.open { display:block; }
    .global-task-item { display:block; padding:10px; margin-top:8px; border-radius:10px; border:1px solid #333a42; background:#20252b; color:inherit; text-decoration:none; }

    /* 0.40.1: lange Duplikatpfade bleiben auf schmalen Displays im Kartenrahmen. */
    .duplicate-file-list,
    .duplicate-file-list li {
      min-width:0;
      max-width:100%;
    }
    .duplicate-file-list code,
    .duplicate-file-list .muted {
      max-width:100%;
      white-space:normal;
      overflow-wrap:anywhere;
      word-break:break-word;
    }
    .duplicate-file-list code {
      display:inline;
    }

/* 0.45.3 – flache Importkarten, Details erst auf Wunsch. */
.bk-history-row { border:1px solid var(--border); background:var(--surface-soft); border-radius:13px; overflow:hidden; margin:0 0 9px; }
.bk-history-strip { display:flex; align-items:center; gap:10px; min-height:64px; padding:8px 10px; }
.bk-history-open { display:flex; gap:12px; flex:1 1 auto; min-width:0; padding:0; border:0; background:transparent; color:inherit; text-align:left; align-items:center; cursor:pointer; }
.bk-history-open:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.bk-history-open .bk-job-thumb { flex:0 0 48px; width:48px; height:48px; margin:0; display:grid; place-items:center; overflow:hidden; border-radius:9px; }
.bk-history-open .bk-job-thumb img { width:100%; height:100%; object-fit:cover; }
.bk-history-text { display:grid; gap:4px; min-width:0; }
.bk-history-text strong { font-size:.97rem; overflow-wrap:anywhere; }
.bk-history-text small { color:var(--muted); font-size:.8rem; }
.bk-history-spinner { flex:0 0 15px; width:15px;height:15px;border:2px solid var(--muted);border-top-color:var(--accent);border-radius:50%;animation:bk-history-spin .8s linear infinite; }
@keyframes bk-history-spin { to{transform:rotate(360deg)} }
.bk-history-actions { display:flex; flex:0 0 auto; gap:7px; align-items:center; }
.bk-history-actions .bk-job-actions { margin:0; }
.bk-history-actions button { padding:6px 9px; min-height:34px; font-size:.77rem; }
.bk-history-details[hidden] { display:none !important; }
.bk-history-details { padding:3px 10px 12px; border-top:1px solid var(--border); }
.bk-history-details .job { margin:8px 0 0; }
.bk-history-more { display:flex;justify-content:center; margin:13px 0; }
.bk-history-hidden-section { border-top:1px solid var(--border); margin-top:17px; padding-top:12px; }
#hidden-history-toggle { display:flex; width:100%; justify-content:space-between; background:transparent; border:0; color:inherit; padding:9px 2px; font-weight:700; text-align:left; cursor:pointer; }
@media(max-width:700px){ .bk-history-strip {gap:6px;padding:7px;} .bk-history-open {gap:7px;} .bk-history-open .bk-job-thumb {flex-basis:37px;width:37px;height:37px;} .bk-history-actions {flex-direction:column;align-items:stretch;gap:4px;} .bk-history-actions button{min-height:30px;font-size:.69rem;padding:4px 6px;} .bk-history-text strong{font-size:.84rem;} .bk-history-text small{font-size:.7rem;} }
@media(prefers-reduced-motion:reduce){.bk-history-spinner{animation:none;}}
</style>
</head>

<body>
  <main>
    <header class="page-intro">
      <div class="page-title-row">
        <div>
          <h1>Import &amp; Prüfung</h1>
          <p class="subtitle">
            SD-Importe, Systemstatus und Prüfvorgänge an einem Ort
          </p>
        </div>

        <div
          class="version"
          id="version"
        >
          Version wird geladen
        </div>
      </div>
    </header>

    <div class="global-navigation-bar">
      <nav
        class="main-navigation"
        aria-label="Hauptbereiche"
      >
        <button class="secondary" type="button" aria-current="page">Import &amp; Prüfung</button>
        <button class="secondary" type="button" onclick="location.href='/workspace'">Sortieren</button>
        <button class="secondary" type="button" onclick="location.href='/events'">Ereignisse</button>
        <button class="secondary" type="button" onclick="location.href='/transfer'">Archiv</button>
      </nav>
      <button class="top-button" type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})" aria-label="Nach oben">↑</button>
    </div>

    <div class="grid bk-status-grid">
      <article class="card bk-status-card">
        <div class="bk-status-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="12" rx="1.5"/><path d="M8 21h8M12 17v4"/></svg>
        </div>
        <div>
          <div class="status-label">Anwendung</div>
          <div class="status-value" id="application-status">Wird geprüft …</div>
          <div class="status-detail" id="application-detail"></div>
        </div>
      </article>

      <article class="card bk-status-card">
        <div class="bk-status-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="7.5" ry="3"/><path d="M4.5 5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V5M4.5 11v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6"/></svg>
        </div>
        <div>
          <div class="status-label">Datenbank</div>
          <div class="status-value" id="database-status">Wird geprüft …</div>
          <div class="status-detail" id="database-detail"></div>
        </div>
      </article>

      <article class="card bk-status-card">
        <div class="bk-status-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M4 7.5h16v10.5H4z"/><path d="M7 7.5V5h10v2.5M7 14h.01M11 14h.01"/></svg>
        </div>
        <div>
          <div class="status-label">Arbeitsbereich</div>
          <div class="status-value" id="workspace-status">Wird geprüft …</div>
          <div class="status-detail" id="workspace-detail"></div>
        </div>
      </article>
    </div>

    <section class="card import-panel">
      <div class="bk-import-head">
        <h2>Quelle sichern</h2>
        <button class="bk-help" type="button" aria-label="Hilfe zur Quellenwahl" data-help="Quelle auswählen und anschließend sicher einlesen. Wähle SD-Karte, externes Laufwerk oder einen Ordner. Achtung: Jede Sicherung wird als vollständige Kopie angelegt; dabei werden Daten in den Arbeitsbestand geschrieben und zusätzlicher Speicherplatz benötigt.">?</button>
        <span class="bk-copy-warning"><strong>Achtung:</strong> Sicherungen werden als Kopie angelegt und belegen zusätzlichen Speicherplatz.</span>
      </div>

      <div id="bk-source-picker" class="bk-source-picker" aria-label="Importquelle wählen">
        <button type="button" class="bk-source-option active" data-source-mode="sd">
          <span class="bk-source-option-icon"><svg viewBox="0 0 24 24"><path d="M7 3h8l3 3v15H7z"/><path d="M10 3v5h5V3M10 13h5M10 16h5"/></svg></span>
          <span><strong>SD-Karte</strong><small>Karte im Kartenleser</small></span>
        </button>
        <button type="button" class="bk-source-option" data-source-mode="drive">
          <span class="bk-source-option-icon"><svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M6 14h12M7 10h.01M10 10h.01"/></svg></span>
          <span><strong>Laufwerk</strong><small>USB-Festplatte oder Stick</small></span>
        </button>
        <button type="button" class="bk-source-option" data-source-mode="folder">
          <span class="bk-source-option-icon"><svg viewBox="0 0 24 24"><path d="M3 7h7l2 2h9v10H3z"/><path d="M3 7V5h7l2 2"/></svg></span>
          <span><strong>Ordner / Sicherung</strong><small>NAS-Ordner oder vorhandene Sicherung</small></span>
        </button>
      </div>

      <div class="source-device-card" id="sd-card-status" data-source-pane="sd">
        SD-Karte wird gesucht …
      </div>

      <div class="import-controls sd-actions" data-source-pane="sd">
        <div class="source-device-card mount-state" id="sd-mount-state" aria-live="polite">SD-Karte noch nicht eingebunden</div>
        <button class="bk-action-tile bk-action-mount" id="sd-mount-button" type="button" disabled>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M5 14v5h14v-5"/></svg>
          <span>SD-Karte einbinden</span>
        </button>
        <button class="bk-action-tile bk-action-save" id="sd-import-button" type="button" disabled>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8V3M8 15h8"/></svg>
          <span>SD-Karte sichern</span>
        </button>
        <button class="bk-action-tile bk-action-eject" id="sd-unmount-button" type="button" disabled>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 14l6-8 6 8z"/><path d="M6 18h12"/></svg>
          <span>SD-Karte auswerfen</span>
        </button>
      </div>

      <div class="source-detail" id="sd-source-detail" data-source-pane="sd"></div>

      <details class="other-source-panel">
        <summary>Andere Quelle verwenden</summary>
        <div class="other-source-content">
          <section class="bk-source-pane" data-source-pane="drive" hidden>
            <h3>Externes Laufwerk sichern</h3>
            <p class="section-description">
              USB-Festplatte oder USB-Stick ausschließlich lesend einbinden.
              Danach kannst du das komplette Laufwerk oder nur einen Ordner daraus sichern.
            </p>
            <div class="import-controls">
              <select id="device-select" aria-label="Externes Laufwerk">
                <option value="">Laufwerke werden geladen …</option>
              </select>
              <button class="secondary" id="device-mount-button" type="button" disabled>
                Laufwerk einbinden
              </button>
            </div>
            <div class="source-device-card mount-state" id="device-mount-state" aria-live="polite">
              Noch kein Laufwerk eingebunden
            </div>
            <div class="import-controls drive-actions">
              <button class="primary" id="device-import-button" type="button" disabled>
                Komplettes Laufwerk sichern
              </button>
              <button class="secondary" id="device-folder-button" type="button" disabled>
                Ordner auswählen
              </button>
              <button class="secondary" id="device-unmount-button" type="button" disabled>
                Laufwerk auswerfen
              </button>
            </div>

            <div class="folder-browser" id="drive-folder-browser" hidden>
              <h3>Ordner im Laufwerk auswählen</h3>
              <p class="section-description">
                Nur der ausgewählte Ordner und sein Inhalt werden importiert.
              </p>
              <div class="folder-path" id="drive-folder-path">/</div>
              <div class="folder-list" id="drive-folder-list"></div>
              <div class="import-controls">
                <button class="secondary" id="drive-folder-up-button" type="button">
                  Eine Ebene höher
                </button>
                <button class="primary" id="drive-folder-import-button" type="button">
                  Diesen Ordner importieren
                </button>
              </div>
            </div>
          </section>

          <section class="bk-source-pane" data-source-pane="folder" hidden>
            <h3>Sicherungsordner auswählen</h3>
            <p class="section-description">
              Wähle einen einzelnen Ordner auf dem NAS oder auf einem bereits
              eingebundenen Wechselmedium. Nur dieser Ordner wird importiert.
            </p>
            <div class="folder-browser">
              <select id="folder-root-select" aria-label="Quellenbereich">
                <option value="nas">NAS-Speicher</option>
                <option value="removable">Eingebundene Wechselmedien</option>
              </select>
              <div class="folder-path" id="folder-path">/</div>
              <div class="folder-list" id="folder-list"></div>
              <div class="source-detail" id="folder-source-detail" role="status" aria-live="polite"></div>
              <div class="import-controls">
                <button class="secondary" id="folder-up-button" type="button">Eine Ebene höher</button>
                <button class="primary" id="folder-import-button" type="button">Diesen Ordner importieren</button>
              </div>
            </div>

          </section>
        </div>
      </details>
    </section>

    <div class="bk-metadata-toolbar">
      <button
        class="secondary"
        id="refresh-button"
        type="button"
      >
        Aktualisieren
      </button>

      <div
        class="notice"
        id="notice"
        role="status"
      ></div>
    </div>

    <section>
      <div class="bk-import-head">
        <h2>Import- und Prüfverlauf</h2>
        <button class="bk-help" type="button" aria-label="Hilfe zum Verlauf" data-help="Jeder Eintrag zeigt einen Importvorgang. Fortschritt und Status aktualisieren sich automatisch; technische Details bleiben ausklappbar.">?</button>
      </div>

      <div
        class="jobs"
        id="jobs"
      >
        <div class="empty bk-loading-status">
          Aufträge werden geladen …
        </div>
      </div>
    </section>
  </main>

  
  <button id="global-task-fab" class="global-task-fab" type="button" aria-label="Offene Aufgaben">☑<span id="global-task-badge" class="global-task-badge">0</span></button>
  <aside id="global-task-panel" class="global-task-panel" aria-live="polite"></aside>

<script>
    async function refreshGlobalTasks() {
      const button=document.getElementById("global-task-fab"), badge=document.getElementById("global-task-badge"), panel=document.getElementById("global-task-panel");
      if(!button||!badge||!panel)return;
      try { const response=await fetch("/api/tasks",{cache:"no-store"}); const data=await response.json(); const tasks=data.tasks||[]; const count=Number(data.count||0); button.classList.add("visible"); badge.textContent=String(count); badge.classList.toggle("hidden",count===0); panel.innerHTML=count?`<strong>Offene Aufgaben · ${count}</strong>`+tasks.map(task=>`<a class="global-task-item" href="${String(task.href||'/events').replaceAll('&','&amp;').replaceAll('\"','&quot;')}"><strong>${String(task.title||'Aufgabe')}</strong><br><span>${String(task.detail||'')}</span></a>`).join(""):`<strong>Keine offenen Aufgaben</strong><br><span>Alles erledigt.</span>`; } catch(_){}
    }
    document.getElementById("global-task-fab")?.addEventListener("click",()=>document.getElementById("global-task-panel")?.classList.toggle("open"));
    refreshGlobalTasks(); setInterval(refreshGlobalTasks,30000);

    const jobsElement =
      document.getElementById("jobs");

    let jobHistoryLimit = 5;
    let jobHistoryJobs = [];
    let jobHistoryTotal = 0;
    let hiddenHistoryTotal = 0;
    let hiddenHistoryLimit = 15;
    let hiddenHistoryJobs = [];
    let hiddenHistoryOpen = false;
    let importHistoryRequestId = 0;
    let hiddenHistoryRequestId = 0;
    const openHistoryIds = new Set();
    const seenHistoryStates = new Map();
    let lastImportHistoryPoll = 0;

    const noticeElement =
      document.getElementById("notice");

    const sdSourceDetail =
      document.getElementById("sd-source-detail");

    const sdCardStatus = document.getElementById("sd-card-status");
    const sdMountButton = document.getElementById("sd-mount-button");
    const sdImportButton = document.getElementById("sd-import-button");
    const sdUnmountButton = document.getElementById("sd-unmount-button");
    const sdMountState = document.getElementById("sd-mount-state");
    const deviceSelect = document.getElementById("device-select");
    const deviceMountButton = document.getElementById("device-mount-button");
    const deviceMountState = document.getElementById("device-mount-state");
    const deviceImportButton = document.getElementById("device-import-button");
    const deviceFolderButton = document.getElementById("device-folder-button");
    const deviceUnmountButton = document.getElementById("device-unmount-button");
    const driveFolderBrowser = document.getElementById("drive-folder-browser");
    const driveFolderPath = document.getElementById("drive-folder-path");
    const driveFolderList = document.getElementById("drive-folder-list");
    const driveFolderUpButton = document.getElementById("drive-folder-up-button");
    const driveFolderImportButton = document.getElementById("drive-folder-import-button");
    const folderRootSelect = document.getElementById("folder-root-select");
    const folderPath = document.getElementById("folder-path");
    const folderList = document.getElementById("folder-list");
    const folderSourceDetail = document.getElementById("folder-source-detail");
    const folderUpButton = document.getElementById("folder-up-button");
    const folderImportButton = document.getElementById("folder-import-button");

    const refreshButton =
      document.getElementById("refresh-button");

    const activeStates = new Set([
      "queued",
      "copying",
      "verifying",
      "backup_verified",
      "analyzing_metadata",
      "organizing"
    ]);

    const stageLabels = {
      starting: "Vorbereitung", source_manifest: "Quelle inventarisieren",
      copying: "Dateien kopieren", backup_verification: "Sicherung prüfen",
      snapshot_created: "Prüfbeleg erstellen",
      metadata_analysis: "Aufnahmen analysieren",
      organization_planning: "Sortierung planen",
      workspace_moving: "Dateien übernehmen",
      workspace_verification: "Übernahme prüfen",
      completed: "Abgeschlossen"
    };
    const cancelEscalationPrompted = new Set();
    const stateLabels = {
      queued: "Wartet",
      copying: "Kopiert",
      verifying: "Prüft",
      backup_verified: "Sicherung geprüft",
      analyzing_metadata: "Analysiert",
      organizing: "Sortiert",
      waiting_for_review: "Prüfung nötig",
      waiting_for_archive: "Bereit fürs Archiv",
      archive_verified: "Archiv geprüft",
      deletion_approved: "Löschen freigegeben",
      completed: "Abgeschlossen",
      failed: "Fehlgeschlagen",
      interrupted: "Unterbrochen"
    };

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function formatBytes(bytes) {
      if (
        bytes === null
        || bytes === undefined
        || Number.isNaN(Number(bytes))
      ) {
        return "—";
      }

      const value = Number(bytes);

      if (value === 0) {
        return "0 Byte";
      }

      const units = [
        "Byte",
        "KiB",
        "MiB",
        "GiB",
        "TiB"
      ];

      const index = Math.min(
        Math.floor(
          Math.log(value) / Math.log(1024)
        ),
        units.length - 1
      );

      return (
        (value / Math.pow(1024, index))
          .toLocaleString(
            (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
            {
              maximumFractionDigits: 1
            }
          )
        + " "
        + units[index]
      );
    }

    function formatDate(value) {
      if (!value) {
        return "—";
      }

      const date = new Date(value);

      if (Number.isNaN(date.getTime())) {
        return value;
      }

      return date.toLocaleString(
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
        {
          dateStyle: "medium",
          timeStyle: "medium"
        }
      );
    }

    function jobPresentation(job) {
      const operation = String(job?.operation || "");
      const identifier = String(job?.job_id || job?.id || "");

      if (
        operation === "metadata_fixture_analysis"
        || identifier.startsWith("METADATA_TEST_")
      ) {
        return {
          title: "Metadaten-Testbestand",
          description:
            "Künstlicher Testbestand für Aufnahmedaten, "
            + "Dateifamilien und Prüffälle."
        };
      }

      if (operation === "folder_import") {
        const trigger = String(job?.trigger_type || "");
        const sourceTitle =
          trigger === "approved_sd"
            ? "SD-Kartenimport"
            : trigger === "usb_key"
              ? "Laufwerksimport"
              : "Ordnerimport";
        return {
          title:
            sourceTitle + " · "
            + (job?.source_volume_label || "Quelle"),
          description:
            sourceTitle + " mit SHA-256, ExifTool, "
            + "Gerätenamen und Tagesgruppierung."
        };
      }

      if (
        job?.simulation
        || job?.kind === "simulation"
        || identifier.startsWith("WEB_SIM_")
      ) {
        return {
          title: "Simulierter SD-Import",
          description:
            "Testlauf des automatischen Ablaufs vom Kopieren "
            + "bis zum geprüften Arbeitsbereich."
        };
      }

      if (operation === "sd_import") {
        return {
          title:
            job?.source_volume_label
            || "SD-Kartenimport",
          description:
            "Echter Import mit Sicherung, SHA-256-Prüfung "
            + "und Überführung in den Arbeitsbereich."
        };
      }

      return {
        title: "Hintergrundauftrag",
        description:
          "Technischer Verarbeitungsvorgang der Kamera-Automatisierung."
      };
    }

    function progressPercent(job) {
      if (job.state === "completed") {
        return 100;
      }

      const current = Number(
        job.overall_progress_current
        ?? job.progress_current
        ?? 0
      );
      const total = Number(
        job.overall_progress_total
        ?? job.progress_total
        ?? 0
      );

      if (total <= 0) {
        return 0;
      }

      return Math.max(
        0,
        Math.min(
          100,
          Math.round(current / total * 100)
        )
      );
    }

    function stageProgressPercent(job) {
      if (job.state === "completed") {
        return 100;
      }
      const current = Number(job.stage_progress_current || 0);
      const total = Number(job.stage_progress_total || 0);
      if (total <= 0) {
        return 0;
      }
      return Math.max(
        0,
        Math.min(
          100,
          Math.round(current / total * 100)
        )
      );
    }

    function backendTimestampMs(value) {
      const raw = String(value || "").trim();
      if (!raw) {
        return NaN;
      }
      const normalized = raw.replace(
        /(\.\d{3})\d+(?=(?:Z|[+-]\d\d:\d\d)?$)/,
        "$1"
      );
      return Date.parse(normalized);
    }

    function estimatedRemainingText(job) {
      if (job.state === "completed") {
        return "fertig";
      }
      if (job.state === "interrupted" || job.state === "failed") {
        return "—";
      }

      const current = Number(
        job.overall_progress_current
        ?? job.progress_current
        ?? 0
      );
      const total = Number(
        job.overall_progress_total
        ?? job.progress_total
        ?? 0
      );
      if (total <= 0 || current <= 0 || current >= total) {
        return "wird berechnet …";
      }

      const started = backendTimestampMs(
        job.started_at || job.created_at || ""
      );
      if (!Number.isFinite(started)) {
        return "wird berechnet …";
      }
      const elapsed = Date.now() - started;
      if (elapsed < 2000) {
        return "wird berechnet …";
      }

      const ratio = Math.max(.001, Math.min(.999, current / total));
      const remainingMs = Math.max(0, elapsed * (1 - ratio) / ratio);
      if (remainingMs < 60000) {
        const seconds = Math.max(
          5,
          Math.round(remainingMs / 5000) * 5
        );
        return "ca. " + seconds + " Sek.";
      }

      const minutes = Math.max(1, Math.round(remainingMs / 60000));
      if (minutes < 60) {
        return "ca. " + minutes + " Min.";
      }
      const hours = Math.floor(minutes / 60);
      const rest = minutes % 60;
      return "ca. " + hours + " Std." + (rest ? " " + rest + " Min." : "");
    }

    function badgeClass(state) {
      if (state === "completed") {
        return "completed";
      }

      if (state === "failed") {
        return "failed";
      }

      if (state === "interrupted") {
        return "interrupted";
      }

      if (activeStates.has(state)) {
        return "active";
      }

      return "";
    }

    function bk0511ImportLabel(german, english) {
      return document.documentElement.dataset.bkLocale === "de" ? german : english;
    }

    function importUiText(value) {
      const source = String(value ?? "");
      const translated = window.BibliothekarI18n?.t?.(source) ?? source;
      if (document.documentElement.dataset.bkLocale === "de" || translated !== source) return translated;
      // An unknown German diagnostic is still available verbatim in raw JSON.
      // Never attempt to translate file paths, user names or machine values.
      return /\b(?:Fehler|fehlgeschlagen|konnte|wurden|wurde|nicht|Sicherung|abgebrochen)\b|[äöüß]/iu.test(source)
        ? "A technical message is available in the original import log."
        : source;
    }

    // The technical panel is presentation-only. Translate known import-state
    // Historical technical logs are raw evidence. Keep nested JSON, IDs,
    // machine codes, user-defined names and filesystem paths byte-for-byte.
    // Visible summaries are localized independently of this raw panel.
    function localizedTechnicalJob(job) {
      return job;
    }

    function renderJob(job, isHidden=false) {
      const state =
        job.stage === "cancelled"
        ? "Abgebrochen"
        : (
          stateLabels[job.state]
          || job.state
          || "Unbekannt"
        );

      const presentation =
        jobPresentation(job);

      const percent =
        progressPercent(job);
      const stagePercent =
        stageProgressPercent(job);
      const stageCode = String(job.stage_progress_stage || job.stage || "starting");
      const stageLabel = stageLabels[stageCode] || stateLabels[stageCode] || stageCode;
      const cancelAgeMs = job.cancel_requested_at
        ? Date.now() - backendTimestampMs(job.cancel_requested_at) : 0;
      const mayForceCancel = Boolean(
        job.cancel_requested && !job.cancel_forced && cancelAgeMs >= 15000
      );
      const remaining =
        estimatedRemainingText(job);

      const result =
        job.result || {};

      const source =
        result.source || {};

      const organization =
        result.organization || {};

      const fileCount =
        job.file_count
        ?? organization.file_count
        ?? source.file_count
        ?? null;

      const sizeBytes =
        job.total_size_bytes
        ?? source.size_bytes
        ?? null;

      const error =
        job.error_message
        ? `
          <div class="message error-text">
            ${escapeHtml(importUiText(job.error_message))}
          </div>
        `
        : "";

      const jobId = String(job.job_id || job.id || "");

      const duplicateFiles = Array.isArray(source.duplicate_files)
        ? source.duplicate_files
        : [];
      const duplicateCount = Number(
        source.duplicate_file_count
        ?? source.already_imported_file_count
        ?? 0
      );
      const duplicateNotice = duplicateCount > 0
        ? `
          <details class="message" data-job-detail-key="${escapeHtml(jobId)}:duplicates" style="border:1px solid var(--border);border-radius:10px;padding:9px 11px">
            <summary><strong>${duplicateCount} ${duplicateCount === 1 ? "Duplikat" : "Duplikate"} übersprungen</strong></summary>
            <p class="muted" style="margin:8px 0">Nur Dateien mit identischer Größe und identischem SHA-256 werden automatisch übersprungen.</p>
            <ul class="duplicate-file-list" style="margin:0;padding-left:20px">
              ${duplicateFiles.map(file => `
                <li style="margin:6px 0">
                  <code>${escapeHtml(file.relative_path || "")}</code>
                  ${file.existing_source_label || file.existing_job_id
                    ? `<br><span class="muted">Bereits vorhanden in ${escapeHtml(file.existing_source_label || file.existing_job_id)}${file.existing_relative_path ? " · " + escapeHtml(file.existing_relative_path) : ""}</span>`
                    : ""}
                </li>`
              ).join("") || `<li class="muted">Detaildaten stehen im technischen Importprotokoll.</li>`}
            </ul>
          </details>
        `
        : "";

      const thumbnail = job.operation === "folder_import"
        ? `<div class="bk-job-thumb"><img src="/api/jobs/${encodeURIComponent(jobId)}/thumbnail" alt="" loading="lazy" onerror="this.remove();this.parentElement.textContent='▣'"></div>`
        : `<div class="bk-job-thumb" aria-hidden="true">▣</div>`;

      const cancellable =
        job.operation === "folder_import"
        && (job.state === "queued" || activeStates.has(job.state));
      const removableInterrupted =
        job.operation === "folder_import"
        && job.kind === "sd_import"
        && (job.state === "interrupted" || job.state === "failed");
      const completedBackup =
        job.operation === "folder_import"
        && job.kind === "sd_import"
        && job.state === "completed";
      const backupActions = (cancellable || removableInterrupted || completedBackup)
        ? `
          <div class="bk-job-actions">
            ${cancellable
              ? `<button class="secondary" type="button" data-cancel-import="${escapeHtml(jobId)}"
                   ${job.cancel_requested ? "disabled" : ""}>${job.cancel_requested ? "Abbruch läuft …" : "Import abbrechen"}</button>
                 ${mayForceCancel ? `<button class="danger" type="button" data-force-import="${escapeHtml(jobId)}">Abbruch erzwingen</button>` : ""}`
              : ""}
            ${removableInterrupted
              ? `<button class="danger" type="button" data-discard-import="${escapeHtml(jobId)}">Import entfernen</button>`
              : ""}
            ${completedBackup
              ? `<button class="danger" type="button"
                    data-delete-backup="${escapeHtml(jobId)}"
                    ${job.backup_delete_allowed ? "" : "disabled"}
                    title="${escapeHtml(job.backup_delete_allowed ? "Sicherung vollständig löschen" : (job.backup_delete_reason || "Sicherung kann nicht gelöscht werden."))}">
                    Sicherung löschen
                 </button>`
              : ""}
          </div>
        `
        : "";

      const detailMarkup = `
        <article class="job bk-history-expanded">
          
          <div class="bk-history-detail-date">
            <span>Erstellt: ${escapeHtml(formatDate(job.created_at))}</span>
            ${activeStates.has(job.state) ? `<span class="bk-stage-badge bk-stage-badge-header">${escapeHtml(stageLabel)}</span>` : ""}
          </div>

          <div class="message">
            ${escapeHtml(
              importUiText(job.progress_message || "Kein Statustext vorhanden.")
            )}
          </div>

          ${error}
          ${duplicateNotice}

          <div class="progress-stack ${job.state === "completed" ? "completed-only" : ""}">
            ${job.state === "completed" ? "" : `
              <div class="progress-row">
                <div class="progress-caption">
                  <span>Aktuelle Phase</span>
                  <span class="bk-stage-value">${stagePercent} %</span>
                </div>
                <div class="progress stage-progress" role="progressbar"
                  aria-label="${escapeHtml(stageLabel)}" aria-valuenow="${stagePercent}" aria-valuemin="0" aria-valuemax="100">
                  <div style="width: ${stagePercent}%"></div>
                </div>
              </div>
            `}
            <div class="progress-row">
              <div class="progress-caption">
                <span>${job.state === "completed" ? "Abgeschlossen" : "Gesamt"}</span>
              </div>
              <div class="progress overall-progress">
                <div
                  class="${job.state === "completed" ? "completed" : ""}"
                  style="width: ${percent}%"
                ></div>
              </div>
            </div>
          </div>

          <div class="job-meta">
            <span>
              ${bk0511ImportLabel("Fortschritt gesamt:", "Overall progress:")}
              ${percent} %
            </span>

            <span>
              ${bk0511ImportLabel("Restzeit:", "Time remaining:")}
              ${escapeHtml(remaining)}
            </span>

            <span>
              ${bk0511ImportLabel("Dateien:", "Files:")}
              ${fileCount ?? "—"}
            </span>

            <span>
              ${bk0511ImportLabel("Größe:", "Size:")}
              ${formatBytes(sizeBytes)}
            </span>

            <span>
              ${bk0511ImportLabel("Stufe:", "Stage:")}
              ${escapeHtml(job.stage || "—")}
            </span>
          </div>

          <details data-job-detail-key="${escapeHtml(jobId)}:technical">
            <summary>
              Technische Details
            </summary>

            <pre>${escapeHtml(
              (document.documentElement.dataset.bkLocale === "de" ? "Technische ID: " : "Technical ID: ")
              + (job.job_id || job.id || "–")
              + (document.documentElement.dataset.bkLocale === "de" ? "\\nAuftragsart: " : "\\nJob type: ")
              + (job.operation || job.kind || "–")
              + "\\n\\n"
              + JSON.stringify(
                  localizedTechnicalJob(job),
                  null,
                  2
                )
            )}</pre>
          </details>
        </article>
      `;
      const isDone = job.state === "completed";
      const isActive = activeStates.has(job.state);
      const expanded = openHistoryIds.has(jobId);
      const progressLabel = isDone
        ? `${bk0511ImportLabel("Abgeschlossen","Completed")} · ${fileCount ?? "–"} ${bk0511ImportLabel("Dateien","files")}`
        : (isActive ? `${escapeHtml(state)} · ${percent}% · ${escapeHtml(remaining)}` : escapeHtml(state));
      const actionMarkup = isHidden
        ? `<button type="button" class="secondary" data-history-unhide="${escapeHtml(jobId)}">Wieder einblenden</button>`
        : (isDone
          ? `${completedBackup ? backupActions : ""}<button type="button" class="secondary" data-history-hide="${escapeHtml(jobId)}">Ausblenden</button>`
          : backupActions);
      return `
        <article class="bk-history-row" data-history-row="${escapeHtml(jobId)}">
          <div class="bk-history-strip">
            <button type="button" class="bk-history-open" data-history-toggle="${escapeHtml(jobId)}"
              aria-expanded="${expanded}" aria-label="Details ${escapeHtml(presentation.title)} ${expanded ? "einklappen" : "aufklappen"}">
              ${thumbnail}
              <span class="bk-history-text">
                <strong>${escapeHtml(presentation.title)}</strong>
                <small>${isDone ? bk0511ImportLabel("Abgeschlossen","Completed") : progressLabel}${isDone ? " · " + (fileCount ?? "–") + " " + bk0511ImportLabel("Dateien","files") : ""}</small>
              </span>
              ${isActive ? '<span class="bk-history-spinner" aria-hidden="true"></span>' : ""}
            </button>
          </div>
          <div class="bk-history-details" ${expanded ? "" : "hidden"}>${detailMarkup}</div>
          <div class="bk-history-actions" data-history-actions>${actionMarkup}</div>
        </article>`;
    }

    async function loadHealth() {
      const response = await fetch(
        "/api/health",
        {
          cache: "no-store"
        }
      );

      if (!response.ok) {
        throw new Error(
          "Systemstatus konnte nicht geladen werden."
        );
      }

      const health = await response.json();

      document.getElementById(
        "version"
      ).textContent =
        "Version " + health.version;

      const applicationStatus =
        document.getElementById(
          "application-status"
        );

      applicationStatus.textContent =
        health.status === "ok"
        ? "Bereit"
        : "Eingeschränkt";

      applicationStatus.style.color =
        health.status === "ok"
        ? "var(--success)"
        : "var(--warning)";

      document.getElementById(
        "application-detail"
      ).textContent =
        "Benutzer "
        + health.runtime.uid
        + ":"
        + health.runtime.gid;

      const database =
        health.database || {};

      document.getElementById(
        "database-status"
      ).textContent =
        database.initialized
        ? "Verbunden"
        : "Fehler";

      document.getElementById(
        "database-status"
      ).style.color =
        database.initialized
        ? "var(--success)"
        : "var(--danger)";

      const schemaVersions = (database.schema_versions || [])
        .map(value => Number(value))
        .filter(value => Number.isFinite(value))
        .sort((left, right) => left - right);
      const schemaSummary = schemaVersions.length > 1
        ? schemaVersions[0] + "–" + schemaVersions[schemaVersions.length - 1]
        : (schemaVersions.length ? String(schemaVersions[0]) : "–");

      document.getElementById(
        "database-detail"
      ).textContent =
        database.initialized
        ? ((document.documentElement.dataset.bkLocale === "de" ? "Schema " : "Schema version ") + schemaSummary)
        : (
          database.error
          || "Keine Verbindung"
        );

      const workspace =
        health.paths?.workspace || {};

      document.getElementById(
        "workspace-status"
      ).textContent =
        workspace.writable
        ? "Beschreibbar"
        : "Nicht beschreibbar";

      document.getElementById(
        "workspace-status"
      ).style.color =
        workspace.writable
        ? "var(--success)"
        : "var(--danger)";

      document.getElementById(
        "workspace-detail"
      ).textContent =
        formatBytes(
          workspace.available_bytes
        )
        + " frei";
    }

    let sourceDevices = [];
    let selectedSdDevice = null;
    let currentFolderRoot = "nas";
    let currentFolderPath = ".";
    let currentFolderParent = null;
    let driveFolderBoundary = null;
    let driveFolderPathValue = ".";
    let driveFolderParent = null;

    function deviceLabel(device) {
      const kind = device.kind === "sd_card" ? "SD-Karte" : "Externes Laufwerk";
      const name = device.label || device.model || device.device_path;
      return `${kind} · ${name} · ${formatBytes(device.size_bytes)} · ${String(device.filesystem || "").toUpperCase()}`;
    }

    function currentExternalDevice() {
      return sourceDevices.find(item => item.device_path === deviceSelect.value) || null;
    }

    function updateDriveControls() {
      const device = currentExternalDevice();
      const verifiedReadOnly = Boolean(device?.mounted && device?.read_only);
      deviceMountButton.disabled = !device || Boolean(device.mounted);
      deviceImportButton.disabled = !verifiedReadOnly;
      deviceFolderButton.disabled = !verifiedReadOnly;
      deviceUnmountButton.disabled = !device?.mounted;
      if (!device) {
        deviceMountState.textContent = "Kein externes Laufwerk erkannt.";
      } else if (verifiedReadOnly) {
        deviceMountState.innerHTML =
          `<strong>${bk0511ImportLabel("✓ Nur lesend eingebunden", "✓ Mounted read-only")}</strong><span>${escapeHtml(deviceLabel(device))}</span>`;
      } else if (device.mounted) {
        deviceMountState.textContent = "Laufwerk ist eingebunden, Nur-Lese-Status aber noch nicht bestätigt.";
      } else {
        deviceMountState.textContent = deviceLabel(device) + " · Bereit zum Einbinden";
      }
      if (!verifiedReadOnly) {
        driveFolderBrowser.hidden = true;
        driveFolderBoundary = null;
      }
    }

    async function loadSourceDevices() {
      try {
        const response = await fetch("/api/source-devices", {cache:"no-store"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Wechselmedien konnten nicht erkannt werden.");
        sourceDevices = data.devices || [];
      } catch (error) {
        sourceDevices = [];
        sdCardStatus.textContent = error.message;
        sdCardStatus.classList.add("error-text");
        deviceSelect.innerHTML = '<option value="">Quellen-Helfer nicht erreichbar</option>';
        return;
      }

      const sdCards = sourceDevices.filter(item => item.kind === "sd_card");
      selectedSdDevice = sdCards.length === 1 ? sdCards[0] : null;
      if (sdCards.length === 0) {
        sdCardStatus.textContent = "Keine SD-Karte im Kartenleser erkannt.";
        sdMountButton.disabled = true;
        sdImportButton.disabled = true;
      } else if (sdCards.length === 1) {
        const card = sdCards[0];
        sdCardStatus.textContent = deviceLabel(card) + (card.mounted ? " · Nur lesend eingebunden" : " · Bereit zum Einbinden");
        const verifiedReadOnly = Boolean(card.mounted && card.read_only);
        sdMountButton.disabled = card.mounted;
        sdMountButton.textContent = "SD-Karte einbinden";
        sdImportButton.disabled = !verifiedReadOnly;
        sdUnmountButton.disabled = !card.mounted;
        sdMountState.classList.toggle("verified", verifiedReadOnly);
        if (verifiedReadOnly) {
          const options = String(card.mount_options || "ro").split(",");
          const compact = ["ro", "nosuid", "nodev", "noexec"].filter(item => options.includes(item));
          sdMountState.innerHTML = `<strong>${bk0511ImportLabel("✓ Nur lesend eingebunden", "✓ Mounted read-only")}</strong><span>${escapeHtml(card.fstype || bk0511ImportLabel("Dateisystem","Filesystem"))} · ${escapeHtml(compact.join(", ") || "ro")}</span><details><summary>${bk0511ImportLabel("Technische Mount-Optionen","Technical mount options")}</summary><code>${escapeHtml(card.mount_options || "ro")}</code></details>`;
        } else {
          sdMountState.textContent = card.mounted ? "Einbindung erkannt, Nur-Lese-Status nicht bestätigt" : "SD-Karte noch nicht eingebunden";
        }
      } else {
        sdCardStatus.textContent = `${sdCards.length} SD-Karten erkannt. Bitte unter „Andere Quelle verwenden“ auswählen.`;
        sdMountButton.disabled = true;
        sdImportButton.disabled = true;
      }

      const external = sourceDevices.filter(item => item.kind !== "sd_card");
      const previousExternal = deviceSelect.value;
      deviceSelect.innerHTML = external.length
        ? external.map(item => `<option value="${escapeHtml(item.device_path)}">${escapeHtml(deviceLabel(item))}${item.mounted ? " · eingebunden" : ""}</option>`).join("")
        : '<option value="">Kein externes Laufwerk erkannt</option>';
      deviceSelect.disabled = external.length === 0;
      if (external.some(item => item.device_path === previousExternal)) {
        deviceSelect.value = previousExternal;
      }
      updateDriveControls();
      updateSdSourceDetail();
    }

    async function unmountDevice(devicePath) {
      const response = await fetch("/api/source-devices/unmount", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_path:devicePath})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Quelle konnte nicht ausgeworfen werden.");
      await loadSourceDevices();
      return data.device;
    }

    async function mountDevice(devicePath) {
      const response = await fetch("/api/source-devices/mount", {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({device_path:devicePath})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Quelle konnte nicht eingebunden werden.");
      await loadSourceDevices();
      return data.device;
    }

    let sdSummaryRequest = 0;
    async function updateSdSourceDetail() {
      const device = selectedSdDevice;
      const requestId = ++sdSummaryRequest;
      if (!device?.mounted || !device.read_only || !device.device_id) {
        sdSourceDetail.textContent = "";
        return;
      }
      sdSourceDetail.textContent = "Karteninhalt wird geprüft …";
      try {
        const params = new URLSearchParams({root_key:"removable", relative_path:device.device_id});
        const response = await fetch("/api/source-folder-summary?" + params, {cache:"no-store"});
        const source = await response.json();
        if (!response.ok) throw new Error(source.detail || "Karteninhalt konnte nicht geprüft werden.");
        if (requestId !== sdSummaryRequest) return;
        const changed = Number(source.changed_file_count || 0);
        const ignored = Number(source.ignored_file_count || 0);
        sdSourceDetail.textContent = `${source.file_count} Dateien insgesamt · `
          + `${source.media_file_count} Medien · `
          + `${formatBytes(source.total_size_bytes)} · `
          + `${Number(source.already_imported_file_count || 0)} bereits gesichert · `
          + `${Number(source.new_file_count || 0)} neu`
          + (changed ? ` · ${changed} verändert/zu prüfen` : "")
          + (ignored ? ` · ${ignored} Verwaltungsdateien ignoriert` : "")
          + (source.import_status === "no_changes" ? " · Keine neuen Dateien" : "");
        if (["no_changes", "already_imported", "import_running"].includes(source.import_status)) {
          sdImportButton.disabled = true;
        }
      } catch (error) {
        if (requestId === sdSummaryRequest)
          sdSourceDetail.textContent = "Karteninformationen nicht verfügbar: " + error.message;
      }
    }

    async function loadDriveFolderBrowser(relativePath=driveFolderBoundary) {
      const device = currentExternalDevice();
      if (!device?.mounted || !device?.read_only || !device.device_id) {
        throw new Error("Bitte das externe Laufwerk zuerst ausschließlich lesend einbinden.");
      }
      if (!driveFolderBoundary) driveFolderBoundary = device.device_id;
      const requested = String(relativePath || driveFolderBoundary);
      if (
        requested !== driveFolderBoundary
        && !requested.startsWith(driveFolderBoundary + "/")
      ) {
        throw new Error("Der Ordner liegt außerhalb des ausgewählten Laufwerks.");
      }
      const params = new URLSearchParams({
        root_key:"removable",
        relative_path:requested
      });
      const response = await fetch(`/api/source-folders?${params}`, {cache:"no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Ordner im Laufwerk konnten nicht geladen werden.");

      driveFolderPathValue = data.relative_path;
      const rawParent = data.parent_relative_path;
      driveFolderParent =
        driveFolderPathValue === driveFolderBoundary
          ? null
          : (
              rawParent
              && (
                rawParent === driveFolderBoundary
                || rawParent.startsWith(driveFolderBoundary + "/")
              )
                ? rawParent
                : null
            );

      const visiblePath =
        driveFolderPathValue === driveFolderBoundary
          ? "/"
          : "/" + driveFolderPathValue.slice(driveFolderBoundary.length + 1);
      driveFolderPath.textContent = visiblePath;
      driveFolderUpButton.disabled = driveFolderParent === null;
      driveFolderList.innerHTML = (data.directories || []).length
        ? data.directories
            .filter(item =>
              item.relative_path === driveFolderBoundary
              || item.relative_path.startsWith(driveFolderBoundary + "/")
            )
            .map(item =>
              `<button type="button" class="secondary folder-entry" data-drive-folder="${escapeHtml(item.relative_path)}">📁 ${escapeHtml(item.name)}</button>`
            ).join("")
        : '<div class="source-detail">Keine Unterordner</div>';
      driveFolderList.querySelectorAll("[data-drive-folder]").forEach(button => {
        button.addEventListener("click", () =>
          loadDriveFolderBrowser(button.dataset.driveFolder).catch(showError)
        );
      });
    }

    let folderBrowserRequest = 0;
    let folderSummaryRequest = 0;

    async function updateFolderSourceDetail(rootKey, relativePath) {
      const requestId = ++folderSummaryRequest;
      if (relativePath === ".") {
        folderSourceDetail.textContent = "Bitte einen Unterordner auswählen.";
        folderImportButton.disabled = true;
        return;
      }
      folderImportButton.disabled = false;
      folderSourceDetail.textContent = "Ausgewählten Ordner prüfen …";
      try {
        const params = new URLSearchParams({root_key:rootKey, relative_path:relativePath});
        const response = await fetch("/api/source-folder-summary?" + params, {cache:"no-store"});
        const source = await response.json();
        if (!response.ok) throw new Error(source.detail || "Ordner konnte nicht geprüft werden.");
        if (requestId !== folderSummaryRequest) return;
        folderSourceDetail.textContent = `${source.file_count} Dateien insgesamt · `
          + `${source.media_file_count} Medien · `
          + formatBytes(source.total_size_bytes);
      } catch (error) {
        if (requestId === folderSummaryRequest)
          folderSourceDetail.textContent = "Ordnerinformationen nicht verfügbar: " + error.message;
      }
    }

    async function loadFolderBrowser(rootKey=currentFolderRoot, relativePath=currentFolderPath) {
      const requestId = ++folderBrowserRequest;
      const params = new URLSearchParams({root_key:rootKey, relative_path:relativePath});
      const response = await fetch(`/api/source-folders?${params}`, {cache:"no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Ordner konnten nicht geladen werden.");
      if (requestId !== folderBrowserRequest) return;
      currentFolderRoot = data.root_key;
      currentFolderPath = data.relative_path;
      currentFolderParent = data.parent_relative_path;
      folderPath.textContent = `/${currentFolderPath === "." ? "" : currentFolderPath}`;
      folderUpButton.disabled = currentFolderParent === null;
      folderList.innerHTML = (data.directories || []).length
        ? data.directories.map(item => `<button type="button" class="secondary folder-entry" data-folder="${escapeHtml(item.relative_path)}">📁 ${escapeHtml(item.name)}</button>`).join("")
        : '<div class="source-detail">Keine Unterordner</div>';
      folderList.querySelectorAll("[data-folder]").forEach(button =>
        button.addEventListener("click", () =>
          loadFolderBrowser(currentFolderRoot, button.dataset.folder).catch(showError)));
      void updateFolderSourceDetail(currentFolderRoot, currentFolderPath);
    }

    function showError(error) {
      noticeElement.textContent = error.message;
      noticeElement.classList.add("error-text");
    }

    function openJobDetailKeys() {
      return new Set(
        [...jobsElement.querySelectorAll("details[data-job-detail-key][open]")]
          .map(node => String(node.dataset.jobDetailKey || ""))
          .filter(Boolean)
      );
    }

    function restoreOpenJobDetails(keys) {
      for (const node of jobsElement.querySelectorAll("details[data-job-detail-key]")) {
        node.open = keys.has(String(node.dataset.jobDetailKey || ""));
      }
    }

    function renderJobHistory(openDetails = new Set()) {
      const remaining = Math.max(0, jobHistoryTotal - jobHistoryJobs.length);
      jobsElement.innerHTML = (jobHistoryJobs.length
        ? jobHistoryJobs.map(job => renderJob(job)).join("")
        : '<div class="empty">Keine sichtbaren Importe vorhanden.</div>')
        + (remaining ? `<div class="bk-history-more"><button class="secondary" id="jobs-more-button" type="button">Mehr anzeigen (${remaining})</button></div>` : "")
        + `<div class="bk-history-hidden-section">
             <button type="button" id="hidden-history-toggle" aria-expanded="${hiddenHistoryOpen}">Ausgeblendet (${hiddenHistoryTotal})</button>
             <div id="hidden-history-list" ${hiddenHistoryOpen ? "" : "hidden"}></div>
           </div>`;
      restoreOpenJobDetails(openDetails);
      document.getElementById("jobs-more-button")?.addEventListener("click", async event => {
        event.currentTarget.disabled = true;
        jobHistoryLimit += 5;
        await loadJobs().catch(showError);
      });
      document.getElementById("hidden-history-toggle")?.addEventListener("click", () => {
        hiddenHistoryOpen = !hiddenHistoryOpen;
        const toggle = document.getElementById("hidden-history-toggle");
        const list = document.getElementById("hidden-history-list");
        if(toggle) toggle.setAttribute("aria-expanded", String(hiddenHistoryOpen));
        if(list) list.hidden = !hiddenHistoryOpen;
        if(hiddenHistoryOpen) {
          if(list && !hiddenHistoryJobs.length) list.innerHTML = '<div class="empty bk-loading-status">Ausgeblendete Importe werden geladen …</div>';
          void loadHiddenHistory().catch(showError);
        } else {
          hiddenHistoryRequestId++;
        }
      });
      bindHistoryButtons(jobsElement);
      if(hiddenHistoryOpen) renderHiddenHistory();
    }

    function bindHistoryButtons(host) {
      for(const button of host.querySelectorAll("[data-history-toggle]")){
        button.addEventListener("click", () => {
          const id = button.dataset.historyToggle;
          const row = button.closest("[data-history-row]");
          if (!row || !id) return;
          if(openHistoryIds.has(id)) openHistoryIds.delete(id);
          else openHistoryIds.add(id);
          const expanded = openHistoryIds.has(id);
          const detail = row.querySelector(".bk-history-details");
          if(detail) detail.hidden = !expanded;
          button.setAttribute("aria-expanded", String(expanded));
        });
      }
      for(const button of host.querySelectorAll("[data-history-hide], [data-history-unhide]")){
        button.addEventListener("click", async () => {
          const id = button.dataset.historyHide || button.dataset.historyUnhide;
          const hidden = Boolean(button.dataset.historyHide);
          button.disabled = true;
          try {
            const response = await fetch("/api/import-history/" + encodeURIComponent(id) + "/visibility", {
              method:"POST", headers:{"Content-Type":"application/json"},
              body:JSON.stringify({hidden})
            });
            const result = await response.json();
            if(!response.ok) throw new Error(result.detail || "Sichtbarkeit konnte nicht geändert werden.");
            // Sichtbarkeit unmittelbar nach dem bestätigten Schreibzugriff aktualisieren.
            if(hidden) {
              jobHistoryJobs = jobHistoryJobs.filter(job => String(job.id) !== String(id));
              jobHistoryTotal = Math.max(0, jobHistoryTotal - 1);
              hiddenHistoryTotal++;
            } else {
              hiddenHistoryJobs = hiddenHistoryJobs.filter(job => String(job.id) !== String(id));
              hiddenHistoryTotal = Math.max(0, hiddenHistoryTotal - 1);
            }
            renderJobHistory(openJobDetailKeys());
            await loadJobs();
            if(hiddenHistoryOpen) await loadHiddenHistory();
          }catch(error){showError(error);button.disabled = false;}
        });
      }
      for (const button of host.querySelectorAll("[data-cancel-import]")) {
        button.addEventListener("click", async () => {
          const jobId = String(button.dataset.cancelImport || "");
          if (!jobId) return;
          button.disabled = true;
          try {
            const response = await fetch(
              `/api/jobs/${encodeURIComponent(jobId)}/cancel`,
              {method:"POST"}
            );
            const data = await response.json();
            if (!response.ok) {
              throw new Error(data.detail || "Import konnte nicht abgebrochen werden.");
            }
            noticeElement.classList.remove("error-text");
            noticeElement.textContent = data.message || "Abbruch wurde angefordert.";
            await loadJobs();
          } catch (error) {
            showError(error);
            button.disabled = false;
          }
        });
      }

      for(const button of host.querySelectorAll("[data-force-import]")) {
        button.addEventListener("click", async () => {
          const jobId = String(button.dataset.forceImport || "");
          if(!jobId || !(await window.BibliothekarI18n.confirmAsync(
            "Importabbruch erzwingen? Der laufende Import wird an sicheren Unterbrechungspunkten beendet. "
            + "Es werden nur eindeutig diesem Import gehörende Dateien bereinigt; fremde Dateien bleiben unangetastet."
          ))) return;
          cancelEscalationPrompted.add(jobId);
          button.disabled = true;
          void requestForcedImportCancel(jobId).catch(showError);
        });
      }

      for (const button of host.querySelectorAll("[data-discard-import]")) {
        button.addEventListener("click", async () => {
          const jobId = String(button.dataset.discardImport || "");
          if (!jobId) return;
          const confirmed = await window.BibliothekarI18n.confirmAsync(
            "Der unterbrochene bzw. fehlgeschlagene Import wird entfernt. "
            + "Temporäre Importdaten und der Verlaufseintrag werden gelöscht; "
            + "die ursprüngliche Quelle bleibt unverändert. Fortfahren?"
          );
          if (!confirmed) return;
          button.disabled = true;
          try {
            const response = await fetch(
              `/api/jobs/${encodeURIComponent(jobId)}/discard`,
              {method:"DELETE"}
            );
            const data = await response.json();
            if (!response.ok) {
              throw new Error(data.detail || "Import konnte nicht entfernt werden.");
            }
            noticeElement.classList.remove("error-text");
            noticeElement.textContent = data.message || "Import wurde entfernt.";
            await loadJobs();
          } catch (error) {
            showError(error);
            button.disabled = false;
          }
        });
      }

      for (const button of host.querySelectorAll("[data-delete-backup]")) {
        button.addEventListener("click", async () => {
          const jobId = String(button.dataset.deleteBackup || "");
          if (!jobId) return;
          const confirmed = await window.BibliothekarI18n.confirmAsync(
            "Diese Sicherung wird vollständig aus dem Arbeitsbestand gelöscht. "
            + "Die zugehörigen Dateien werden unwiderruflich gelöscht. "
            + "Möchtest du wirklich fortfahren?"
          );
          if (!confirmed) return;
          button.disabled = true;
          try {
            const response = await fetch(
              `/api/backups/${encodeURIComponent(jobId)}`,
              {method:"DELETE"}
            );
            const data = await response.json();
            if (!response.ok) {
              throw new Error(data.detail || "Sicherung konnte nicht gelöscht werden.");
            }
            noticeElement.classList.remove("error-text");
            noticeElement.textContent =
              `Sicherung gelöscht: ${data.deleted_file_count || 0} Dateien.`;
            await loadJobs();
          } catch (error) {
            showError(error);
            await loadJobs().catch(() => null);
          }
        });
      }
    }

    async function loadHiddenCount() {
      const response = await fetch("/api/import-history?hidden=true&count_only=true", {cache:"no-store"});
      if(!response.ok) throw new Error("Zähler für ausgeblendete Importe konnte nicht geladen werden.");
      const data = await response.json();
      return Number(data.total || 0);
    }

    async function requestHistoryPages(hidden, count) {
      let offset = 0, total = 0, jobs = [];
      do {
        const limit = Math.min(50, count - offset);
        const response = await fetch("/api/import-history?hidden=" + String(hidden)
          + "&limit=" + limit + "&offset=" + offset, {cache:"no-store"});
        if(!response.ok)throw new Error("Importverlauf konnte nicht geladen werden.");
        const part = await response.json();
        total = Number(part.total || 0);
        jobs.push(...(part.jobs || []));
        if(!part.jobs?.length || jobs.length >= total) break;
        offset = jobs.length;
      } while (offset < count);
      return {jobs,total};
    }

    async function loadHiddenHistory() {
      const requestId = ++hiddenHistoryRequestId;
      const data = await requestHistoryPages(true, hiddenHistoryLimit);
      if(requestId !== hiddenHistoryRequestId || !hiddenHistoryOpen) return;
      hiddenHistoryJobs = data.jobs;
      hiddenHistoryTotal = data.total;
      const label = document.getElementById("hidden-history-toggle");
      if(label) label.textContent = 'Ausgeblendet (' + hiddenHistoryTotal + ')';
      renderHiddenHistory();
    }

    async function requestForcedImportCancel(jobId) {
      const response = await fetch(
        `/api/jobs/${encodeURIComponent(jobId)}/cancel?force=true`,
        {method:"POST"}
      );
      const data = await response.json();
      if(!response.ok) throw new Error(data.detail || "Eskalierter Abbruch fehlgeschlagen.");
      noticeElement.classList.remove("error-text");
      noticeElement.textContent = data.message || "Erzwungener Abbruch angefordert.";
      await loadJobs();
    }

    function renderHiddenHistory() {
      const host=document.getElementById("hidden-history-list");
      if(!host)return;
      const more = Math.max(0, hiddenHistoryTotal-hiddenHistoryJobs.length);
      host.innerHTML = hiddenHistoryJobs.map(job=>renderJob(job,true)).join("")
        + (more ? `<div class="bk-history-more"><button type="button" id="hidden-more">Mehr anzeigen (${more})</button></div>` : "");
      bindHistoryButtons(host);
      host.querySelector("#hidden-more")?.addEventListener("click", async event=>{
        event.currentTarget.disabled=true;hiddenHistoryLimit+=15;await loadHiddenHistory();
      });
    }

    async function loadJobs() {
      // Liste und Zähler nur gemeinsam aus der aktuellen SQLite-Ansicht darstellen.
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
      if(!document.hidden) {
        const stalled = jobHistoryJobs.find(job => {
          if(!job.cancel_requested || job.cancel_forced || !activeStates.has(job.state)) return false;
          const age = Date.now()-backendTimestampMs(job.cancel_requested_at);
          return age>=15000 && !cancelEscalationPrompted.has(String(job.id));
        });
        if(stalled){
          const key=String(stalled.id);
          cancelEscalationPrompted.add(key);
          // Beim ersten erfolglosen Abbruch einmalig nachfragen; Nein bleibt
          // möglich, der sichtbare Eskalationsknopf bleibt verfügbar.
          if(await window.BibliothekarI18n.confirmAsync("Der Import reagiert seit mindestens 15 Sekunden nicht auf den Abbruch. Abbruch erzwingen?")) {
            void requestForcedImportCancel(key).catch(showError);
          }
        }
      }
    }

    async function refreshAll() {
      refreshButton.disabled = true;
      refreshButton.classList.add("bk-busy");
      refreshButton.setAttribute("aria-busy", "true");
      noticeElement.classList.add("bk-loading-status");
      noticeElement.textContent = "Import & Prüfung wird aktualisiert …";

      try {
        await Promise.all([
          loadHealth(),
          loadJobs(),
          loadSourceDevices(),
          loadFolderBrowser().catch(() => null)
        ]);

        noticeElement.textContent =
          "Zuletzt aktualisiert: "
          + new Date().toLocaleTimeString(
            (document.documentElement.lang === "de" ? "de-DE" : "en-US")
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
      const device = selectedSdDevice;
      if (!device?.mounted || !device.read_only || !device.device_id) {
        showError(new Error("Bitte die SD-Karte zuerst ausschließlich lesend einbinden."));
        return;
      }
      await startFolderImportSelection(
        "removable", device.device_id, device.label || device.model || "SD-Karte", "sd_card"
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
      const leaf = currentFolderPath.split("/").filter(Boolean).at(-1) || "Sicherungsordner";
      await startFolderImportSelection(currentFolderRoot, currentFolderPath, leaf, "folder");
    });

    async function startFolderImportSelection(rootKey, relativePath, displayName="", sourceMode="folder") {
      if (!rootKey || !relativePath) {
        noticeElement.textContent = "Bitte zuerst eine Importquelle auswählen.";
        noticeElement.classList.add("error-text");
        return;
      }

      folderImportButton.disabled = true;
      sdImportButton.disabled = true;
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
        await loadSourceDevices();
        updateDriveControls();
        folderImportButton.disabled = currentFolderPath === ".";
        noticeElement.classList.remove("bk-loading-status");
      }
    }

    refreshButton.addEventListener(
      "click",
      () => refreshAll()
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
        manual_change_id = str(body.get("manual_structure_change_id") or "").strip()
        if manual_change_id:
            from app.event_structure_changes import validate_guided_structure_edit
            with database_connection(current_database_file()) as connection:
                validate_guided_structure_edit(
                    connection, event_id, manual_change_id, preview,
                    expected_root_kind="camera_archive",
                )
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
                guided_structure_change_id=manual_change_id or None,
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
        from app.event_structure_changes import EventStructureChangeError
        if isinstance(exc, EventStructureChangeError):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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


@app.post("/api/change-requests/{cr_id}/reversal/force-stop")
def api_force_stop_change_reversal(
    cr_id: str, body: dict[str, Any],
) -> JSONResponse:
    """Emergency lock, not a successful reversal or deletion."""
    from app.archive_recovery import force_stop_reversal
    try:
        result = force_stop_reversal(
            current_database_file(), current_archive_root(), current_workspace_root(),
            cr_id, phrase=str(body.get("confirmation") or ""),
            reason=str(body.get("reason") or ""),
        )
        return JSONResponse(content=result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/archive/recovery/{event_id}")
def api_archive_recovery_status(event_id: str) -> JSONResponse:
    from app.archive_recovery import read_recovery_incident
    incident = read_recovery_incident(current_database_file(), event_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Kein offener Wiederherstellungsfall.")
    return JSONResponse(content=incident)


@app.post("/api/archive/recovery/{event_id}/verify-and-unlock")
def api_archive_recovery_verify_and_unlock(event_id: str) -> JSONResponse:
    from app.archive_recovery import resolve_recovery_incident
    try:
        result = resolve_recovery_incident(
            current_database_file(), current_archive_root(), current_workspace_root(),
            event_id,
        )
        return JSONResponse(content=result)
    except ValueError as exc:
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


# BA-03: The last registered HTTP middleware executes first. In particular,
# authenticate BEFORE library-context resolution, onboarding or APIs.
@app.middleware("http")
async def owner_authentication_middleware(request: Request, call_next):
    from app.security import protect_request
    return await protect_request(request, call_next)
