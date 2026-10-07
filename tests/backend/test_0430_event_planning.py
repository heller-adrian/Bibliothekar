from __future__ import annotations

from pathlib import Path

import pytest

from app.canonical_membership import resolve_payload_membership
from app.database import create_job, database_connection, initialize_database
from app.event_naming import (
    render_event_folder_name,
    render_subevent_folder_name,
)
from app.event_structure import EventPreviewError, build_event_preview
from app.subevents import normalize_subevents
from app.ui_shell import BIBLIOTHEKAR_JS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def _family(family_id: int, capture: str) -> dict:
    return {
        "family_id": family_id,
        "job_id": "JOB",
        "family_key": f"F{family_id}",
        "original_stem": f"IMG_{family_id:04d}",
        "selected_capture_time": capture,
        "capture_time_confidence": "high",
        "has_date": True,
        "day_key": capture[:10],
        "file_count": 1,
        "total_size_bytes": 100,
        "review_required_count": 0,
    }


def test_0430_subevent_prefix_modes_and_cross_year_logic():
    common = {
        "event_name": "Stadtbesuch",
        "start_datetime": "2026-07-20T14:00:00",
        "end_datetime": "2026-07-21T18:30:59",
    }
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "date", "subevent_prefix_enabled": True},
    ) == "07-20 - Stadtbesuch"
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "date_range", "subevent_prefix_enabled": True},
    ) == "07-20–07-21 - Stadtbesuch"
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "time", "subevent_prefix_enabled": True},
    ) == "14-00–18-30 - Stadtbesuch"
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "year", "subevent_prefix_enabled": True},
    ) == "2026 - Stadtbesuch"
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "none", "subevent_prefix_enabled": True},
    ) == "Stadtbesuch"
    assert render_subevent_folder_name(
        **common,
        naming={"subevent_prefix_mode": "date_range", "subevent_prefix_enabled": False},
    ) == "Stadtbesuch"

    cross = render_subevent_folder_name(
        event_name="Silvester",
        start_datetime="2026-12-31T20:00:00",
        end_datetime="2027-01-01T02:00:59",
        parent_start_datetime="2026-12-31T00:00:00",
        parent_end_datetime="2027-01-02T23:59:59",
        naming={"subevent_prefix_mode": "date_range", "subevent_prefix_enabled": True},
    )
    assert cross == "2026-12-31–2027-01-01 - Silvester"

    parent = render_event_folder_name(
        event_name="Jahreswechsel",
        start_date="2026-12-31",
        end_date="2027-01-02",
        start_time="00:00",
        end_time="23:59",
        uses_time_range=True,
        naming={"date_mode": "range", "include_year": False, "include_time": False},
    )
    assert parent == "2026-12-31–2027-01-02 - Jahreswechsel"


def test_0430_photo_free_days_are_not_event_gaps():
    preview = build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Reise",
            "start_date": "2026-07-20",
            "end_date": "2026-07-22",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": True,
            "preserve_day_folders": True,
            "selected_family_ids": [1, 2],
            # This deliberately mirrors two clicked day cards with a
            # photo-free calendar day between them.
            "selected_intervals": [
                {
                    "start_datetime": "2026-07-20T00:00:00",
                    "end_datetime": "2026-07-20T23:59:59",
                },
                {
                    "start_datetime": "2026-07-22T00:00:00",
                    "end_datetime": "2026-07-22T23:59:59",
                },
            ],
            "subevents": [{
                "name": "Gesamtausflug",
                "start_datetime": "2026-07-20T00:00:00",
                "end_datetime": "2026-07-22T23:59:59",
            }],
            "folder_naming": {
                "subevent_prefix_mode": "date_range",
                "subevent_prefix_enabled": True,
            },
        },
        [
            _family(1, "2026-07-20T12:00:00"),
            _family(2, "2026-07-22T12:00:00"),
        ],
    )
    assert preview["selected_day_keys"] == ["2026-07-20", "2026-07-22"]
    assert preview["empty_subevent_days"] == []
    assert preview["subevents"][0]["folder_name"] == "07-20–07-22 - Gesamtausflug"


def test_0430_no_event_has_no_semantic_subevents():
    with pytest.raises(EventPreviewError, match="keine semantischen Unterereignisse"):
        build_event_preview(
            {
                "event_kind": "no_event",
                "event_name": "Ohne Ereignis",
                "no_event_segments": [{
                    "day_key": "2026-07-20",
                    "start_time": "00:00",
                    "end_time": "23:59",
                }],
                "subevents": [{
                    "name": "Nicht erlaubt",
                    "start_datetime": "2026-07-20T10:00:00",
                    "end_datetime": "2026-07-20T11:00:00",
                }],
            },
            [_family(1, "2026-07-20T10:30:00")],
        )


def test_0430_nested_subevents_are_rejected():
    with pytest.raises(ValueError, match="Unter-Unterereignisse"):
        normalize_subevents(
            [{
                "name": "A",
                "start_datetime": "2026-07-20T10:00:00",
                "end_datetime": "2026-07-20T11:00:00",
                "subevents": [{
                    "name": "B",
                    "start_datetime": "2026-07-20T10:15:00",
                    "end_datetime": "2026-07-20T10:30:00",
                }],
            }],
            "2026-07-20T00:00:00",
            "2026-07-20T23:59:59",
        )


def test_0430_membership_warns_only_for_hidden_active_backups(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)

    for job_id, label in [
        ("VISIBLE", "Sichtbar"),
        ("HIDDEN", "Ausgeblendet"),
    ]:
        create_job(
            database,
            job_id=job_id,
            kind="sd_import",
            trigger_type="manual",
            operation="folder_import",
            source_volume_label=label,
        )

    with database_connection(database) as connection:
        family_ids = {}
        for job_id, stem, capture in [
            ("VISIBLE", "A", "2026-07-20T10:00:00"),
            ("VISIBLE", "B", "2026-07-20T11:00:00"),
            ("HIDDEN", "C", "2026-07-20T12:00:00"),
        ]:
            family_id = int(connection.execute(
                """INSERT INTO file_families(
                       job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence
                   ) VALUES (?,?,?,'complete',?,'high')""",
                (job_id, stem, stem, capture),
            ).lastrowid)
            family_ids[stem] = family_id
            connection.execute(
                """INSERT INTO files(
                       job_id,family_id,original_relative_path,current_relative_path,
                       current_root_kind,original_filename,extension,media_type,
                       size_bytes,sha256_original,selected_capture_time,capture_time_confidence,
                       review_status,metadata_write_status,created_at,updated_at
                   ) VALUES (?,?,?,?,'shared_workspace',?,'.JPG','jpeg',100,?,?,
                             'high','not_required','not_requested','2026-07-20','2026-07-20')""",
                (
                    job_id,
                    family_id,
                    f"{stem}.JPG",
                    f"2026/07-20/{stem}.JPG",
                    f"{stem}.JPG",
                    (stem.lower()*64)[:64],
                    capture,
                ),
            )
        connection.commit()

        membership = resolve_payload_membership(
            connection,
            {
                "event_kind": "event",
                "start_date": "2026-07-20",
                "end_date": "2026-07-20",
                "start_time": "09:00",
                "end_time": "13:00",
                "uses_time_range": True,
                "selected_family_ids": [family_ids["A"]],
                "visible_active_job_ids": ["VISIBLE"],
            },
        )

    assert membership["additional_family_count"] == 2
    assert set(membership["additional_family_ids"]) == {
        family_ids["B"],
        family_ids["C"],
    }
    assert membership["hidden_additional_family_count"] == 1
    assert membership["hidden_additional_family_ids"] == [family_ids["C"]]
    assert [source["job_id"] for source in membership["hidden_sources"]] == ["HIDDEN"]


def test_0430_settings_and_event_dialog_expose_subevent_prefix_policy():
    shell = _shell_markup("workspace", "captures")
    assert "<span>Unterereignisse</span>" in shell
    assert 'id="bk-subevent-prefix-mode"' in shell
    assert '<option value="date">Datum</option>' in shell
    assert '<option value="date_range">Datumsbereich</option>' in shell
    assert '<option value="time">Uhrzeit</option>' in shell
    assert '<option value="year">Jahr</option>' in shell
    assert '<option value="none">Kein Präfix</option>' in shell
    assert 'id="bk-subevent-prefix-enabled"' in shell
    assert "Stadtbesuch" in BIBLIOTHEKAR_JS

    assert 'id="subevent-prefix-toggle"' in WORKSPACE_HTML
    assert ">Präfix: an<" in WORKSPACE_HTML
    assert "count>0" in WORKSPACE_HTML
    assert "subevent_prefix_enabled=dialogSubeventPrefixEnabled" in WORKSPACE_HTML
    assert "visible_active_job_ids" in WORKSPACE_HTML
    assert "Weitere Aufnahmen aus ausgeblendeten Sicherungen" in WORKSPACE_HTML


def test_0430_full_dates_are_directly_typable_with_optional_picker():
    assert 'id="event-start-date" type="text"' in WORKSPACE_HTML
    assert 'id="event-end-date" type="text"' in WORKSPACE_HTML
    assert 'data-date-picker-target="event-start-date"' in WORKSPACE_HTML
    assert 'data-date-picker-target="event-end-date"' in WORKSPACE_HTML
    assert 'placeholder="JJJJ-MM-TT"' in WORKSPACE_HTML

    assert 'id="edit-start-date" type="text"' in EVENTS_HTML
    assert 'id="edit-end-date" type="text"' in EVENTS_HTML
    assert 'data-edit-date-picker="edit-start-date"' in EVENTS_HTML
    assert 'data-edit-date-picker="edit-end-date"' in EVENTS_HTML


def test_0430_invalid_direct_date_is_rejected():
    with pytest.raises(EventPreviewError, match="Beginn ist ungültig"):
        build_event_preview(
            {
                "event_kind": "event",
                "event_name": "Ungültig",
                "start_date": "2026-02-31",
                "end_date": "2026-03-01",
                "start_time": "00:00",
                "end_time": "23:59",
                "uses_time_range": True,
            },
            [_family(1, "2026-03-01T12:00:00")],
        )
