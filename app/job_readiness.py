from __future__ import annotations

from typing import Any


SORTABLE_ACTIVE_STATES = {
    "backup_verified",
    "analyzing_metadata",
    "waiting_for_review",
    "organizing",
    "waiting_for_archive",
    "archive_verified",
    "deletion_approved",
}

SORTABLE_COMPLETED_STAGES = {
    "organized_verified",
    "event_sort_applied",
    "event_ssd_released",
}

SORTABLE_COMPLETED_OPERATIONS = {
    "folder_import",
    "sd_import",
    "metadata_fixture_analysis",
    "legacy_simulation",
}


def job_sort_readiness(job: dict[str, Any]) -> tuple[bool, str]:
    """Return one shared verdict for sort planning and sort application."""

    state = str(job.get("state") or "")
    stage = str(job.get("stage") or "")
    operation = str(job.get("operation") or "")

    if state in SORTABLE_ACTIVE_STATES:
        return True, ""

    if state == "completed":
        if (
            stage in SORTABLE_COMPLETED_STAGES
            and operation in SORTABLE_COMPLETED_OPERATIONS
        ):
            return True, ""

        return (
            False,
            "Der abgeschlossene Sicherungsauftrag besitzt keine "
            "sortierbare Abschlussstufe: " + (stage or "[ohne Stufe]"),
        )

    return (
        False,
        "Der Sicherungsauftrag befindet sich noch nicht in einem "
        "für die Sortierung freigegebenen Zustand: "
        + (state or "[ohne Zustand]"),
    )
