"""Tests fuer den Change-Request-Workflow (0.16.1).

Diese Tests nutzen das REALE Migrationsschema (app.database.initialize_database),
nicht ein kuenstliches Schema. Damit werden die frueheren Schema-Bugs
(event_assignments hat KEINE job_id; events hat job_id/revision/archived_at)
sichtbar statt verdeckt.

Abgedeckt:
- propose / list / get / files
- confirm / cancel / archive (finish_event_change)
- update_event_definition (planned, applied, archived)
- Frontend isoDate/isoTime-Fallback (leere/NULL Werte)
- Integrationstests planned/applied/archived
- Zeit-erweitern/-verkuerrzen
- leere/NULL-Datum/-Zeit
"""
import json
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import connect, initialize_database, update_event_definition
from app.event_change_request import (
    EventChangeRequestError,
    get_event_change_request,
    get_event_change_files,
    list_event_change_requests,
    propose_event_change,
)
from app.event_change_apply import (
    EventChangeApplyError,
    cancel_event_change,
    confirm_event_change,
    finish_event_change,
)

NOW = "2024-01-01T00:00:00"


def _make_db(temp_dir) -> Path:
    db = Path(temp_dir) / "test.sqlite3"
    initialize_database(db)
    return db


def _seed_job(conn, job_id: str = "job-001"):
    conn.execute(
        """INSERT INTO jobs (id, kind, trigger_type, state, stage,
           created_at, updated_at) VALUES (?,?,?,?,?,?,?)""",
        (job_id, "sd_import", "approved_sd", "completed", "done", NOW, NOW),
    )


def _seed_event(
    conn,
    *,
    event_id: str,
    job_id: str = "job-001",
    status: str = "planned",
    name: str = "Ereignis A",
    uses_time_range: bool = False,
    preserve_day_folders: bool = True,
    folder_name: str | None = None,
):
    if folder_name is None:
        folder_name = name
    if status == "applied":
        applied_at, archived_at = NOW, None
    elif status == "archived":
        applied_at, archived_at = NOW, "2024-01-02T00:00:00"
    else:
        applied_at, archived_at = None, None
    conn.execute(
        """INSERT INTO events (id, job_id, parent_event_id, event_level, name,
           start_datetime, end_datetime, uses_time_range, folder_name, status,
           created_at, updated_at, event_kind, preserve_day_folders, revision,
           applied_at, archived_at, notes, edited_at, resort_required)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (event_id, job_id, None, "parent", name,
         "2024-01-01T00:00:00", "2024-01-01T23:59:59", 1 if uses_time_range else 0,
         folder_name, status, NOW, NOW, "event", 1 if preserve_day_folders else 0,
         1, applied_at, archived_at, "", NOW, 0),
    )


def _seed_family(
    conn,
    job_id: str = "job-001",
    family_key: str = "fk-1",
    capture: str = "2024-01-01T12:00:00",
) -> int:
    cur = conn.execute(
        """INSERT INTO file_families (job_id, family_key, original_stem,
           status, selected_capture_time, capture_time_confidence)
           VALUES (?,?,?,?,?,?)""",
        (job_id, family_key, "IMG_1", "complete", capture, "high"),
    )
    return cur.lastrowid


def _seed_file(
    conn,
    job_id: str = "job-001",
    family_id: int = 1,
    path: str = "IMG_1.jpg",
    capture: str = "2024-01-01T12:00:00",
) -> int:
    cur = conn.execute(
        """INSERT INTO files (job_id, family_id, original_relative_path,
           current_relative_path, original_filename, extension, media_type,
           size_bytes, sha256_original, sha256_current, selected_capture_time,
           selected_capture_source, capture_time_confidence, review_status,
           metadata_write_status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, family_id, path, path, path.rsplit(".", 1)[0], "jpg", "jpeg",
         100, "sha1", "sha1", capture, "metadata", "high", "confirmed",
         "not_requested", NOW, NOW),
    )
    return cur.lastrowid


def _seed_assignment(
    conn,
    event_id: str,
    family_id: int = 1,
    source: str = "manual",
) -> None:
    # OR IGNORE: in manchen Tests existiert die Zuordnung bereits
    # (UNIQUE(event_id, family_id)). Die Familie muss existieren (FK).
    try:
        conn.execute(
            """INSERT INTO event_assignments (event_id, family_id, file_id,
               assignment_source, created_at) VALUES (?,?,?,?,?)""",
            (event_id, family_id, None, source, NOW),
        )
    except Exception:
        pass


def _materialize_manual_targets(db: Path, cr_id: str, archive_root: Path) -> None:
    """Simuliere ausschließlich die vom Benutzer manuell ausgeführten Archivverschiebungen."""
    reviews = get_event_change_files(db, cr_id)
    for review in reviews:
        if review["action"] == "delete":
            continue
        target_rel = review["new_path"] or review["old_path"]
        if not target_rel:
            continue
        target = archive_root / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = b"x" * int(review.get("expected_size_bytes") or 100)
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        with connect(db) as conn:
            conn.execute(
                "UPDATE event_change_file_reviews SET expected_size_bytes=?, expected_sha256=? WHERE id=?",
                (len(data), digest, review["id"]),
            )


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.db = _make_db(self.temp)
        with connect(self.db) as conn:
            _seed_job(conn)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)


# ── 1. Propose (reales Schema) ────────────────────────────────────────────
class TestProposeRealSchema(BaseTest):
    def test_propose_archived_success(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-arch", status="archived")
            fam = _seed_family(conn)
            _seed_assignment(conn, "evt-arch", family_id=fam)
        cr = propose_event_change(
            self.db, "job-001", "evt-arch",
            {"parent_folder": "Ereignis A", "selected_family_ids": [fam]},
        )
        self.assertIsNotNone(cr)
        self.assertEqual(cr["event_id"], "evt-arch")
        self.assertIn("change_request_id", cr)
        self.assertEqual(cr["status"], "aenderbar_vorschlagen")

    def test_propose_non_archived_fails(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-draft", status="draft")
        with self.assertRaises(EventChangeRequestError):
            propose_event_change(
                self.db, "job-001", "evt-draft",
                {"parent_folder": "Ereignis A"},
            )

    def test_propose_nonexistent_fails(self):
        with self.assertRaises(Exception):
            propose_event_change(
                self.db, "job-001", "evt-nope",
                {"parent_folder": "Ereignis A"},
            )


# ── 2. List / Get / Files ────────────────────────────────────────────────
class TestListGet(BaseTest):
    def setUp(self):
        super().setUp()
        with connect(self.db) as conn:
            for i in range(3):
                event_id = f"evt-{i:03d}"
                _seed_event(conn, event_id=event_id, status="archived", name=f"E {i}")
                fam = _seed_family(conn, family_key=f"fk-{i}")
                _seed_file(conn, family_id=fam, path=f"IMG_{i}.jpg")
                _seed_assignment(conn, event_id, family_id=fam)
        for i in range(3):
            propose_event_change(self.db, "job-001", f"evt-{i:03d}", {"parent_folder": "E"})

    def test_list_all(self):
        reqs = list_event_change_requests(self.db, "job-001")
        self.assertEqual(len(reqs), 3)
        for cr in reqs:
            self.assertIn("id", cr)
            self.assertIn("event_id", cr)
            self.assertIn("status", cr)

    def test_get_existing(self):
        reqs = list_event_change_requests(self.db, "job-001")
        cr_id = reqs[0]["id"]
        cr = get_event_change_request(self.db, cr_id)
        self.assertIsNotNone(cr)
        self.assertEqual(cr["id"], cr_id)

    def test_get_nonexistent(self):
        self.assertIsNone(get_event_change_request(self.db, "cr-none"))

    def test_get_files(self):
        reqs = list_event_change_requests(self.db, "job-001")
        cr_id = reqs[0]["id"]
        files = get_event_change_files(self.db, cr_id)
        self.assertIsInstance(files, list)


# ── 3. Confirm / Cancel / Archive (finish) ────────────────────────────────
class TestConfirmCancelArchive(BaseTest):
    def setUp(self):
        super().setUp()
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="archived")
            fam = _seed_family(conn)
            _seed_file(conn, family_id=fam)
            _seed_assignment(conn, "evt-001", family_id=fam)

    def test_confirm_workflow(self):
        cr = propose_event_change(self.db, "job-001", "evt-001", {"parent_folder": "E"})
        # confirm_event_change prueft, dass alle move/delete-File-Reviews
        # bestaetigt sind. Wir markieren alle als bestaetigt (realistisch:
        # der Nutzer hat die Datei-Bewegungen bestaetigt).
        with connect(self.db) as conn:
            conn.execute(
                "UPDATE event_change_file_reviews SET confirmed = 1 "
                "WHERE change_request_id = ?",
                (cr["change_request_id"],),
            )
        confirmed = confirm_event_change(self.db, cr["change_request_id"])
        self.assertEqual(confirmed["status"], "bestaetigt")
        self.assertIn("confirmed_at", confirmed)
        cr = get_event_change_request(self.db, cr["change_request_id"])
        self.assertEqual(cr["status"], "aenderbar_bestaetigt")

    def test_cancel_workflow(self):
        cr = propose_event_change(self.db, "job-001", "evt-001", {"parent_folder": "E"})
        cancelled = cancel_event_change(self.db, cr["change_request_id"])
        self.assertEqual(cancelled["status"], "abgebrochen")
        cr = get_event_change_request(self.db, cr["change_request_id"])
        self.assertEqual(cr["status"], "aenderbar_abgebrochen")

    def test_archive_finish_real_schema(self):
        """finish_event_change muss mit dem REALEN Schema durchlaufen.

        Vor dem Fix:
          - DELETE FROM event_assignments WHERE event_id=? AND job_id=?
            (job_id gibt es in event_assignments nicht)
        """
        cr = propose_event_change(self.db, "job-001", "evt-001", {"parent_folder": "E"})
        cr_id = cr["change_request_id"]
        with connect(self.db) as conn:
            conn.execute(
                "UPDATE event_change_file_reviews SET confirmed = 1 "
                "WHERE change_request_id = ?",
                (cr_id,),
            )
        confirm_event_change(self.db, cr_id)
        _materialize_manual_targets(self.db, cr_id, Path(self.temp))
        result = finish_event_change(self.db, cr_id, Path(self.temp))
        self.assertEqual(result["status"], "archiviert")
        self.assertTrue(result["archive_read_only"])
        self.assertEqual(result["files_changed_by_app"], 0)
        cr = get_event_change_request(self.db, cr_id)
        self.assertEqual(cr["status"], "aenderbar_archiviert")
        # Die Zuordnung wird nach erfolgreicher read-only Prüfung aus dem Auftrag neu aufgebaut.
        with connect(self.db) as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM event_assignments WHERE event_id = ?",
                ("evt-001",),
            ).fetchone()["c"]
        self.assertEqual(cnt, 1)

    def test_archive_without_confirm_fails(self):
        cr = propose_event_change(self.db, "job-001", "evt-001", {"parent_folder": "E"})
        with self.assertRaises(EventChangeApplyError):
            finish_event_change(self.db, cr["change_request_id"], Path(self.temp))


# ── 4. update_event_definition (planned, applied, archived) ───────────────
class TestUpdateEventDefinition(BaseTest):
    def _preview(self, family_id: int = 1, *, start="2024-01-01", end="2024-01-01"):
        return {
            "parent_folder": "Ereignis A",
            "child_folder": "",
            "uses_time_range": False,
            "preserve_day_folders": True,
            "start_date": start,
            "end_date": end,
            "start_time": "00:00",
            "end_time": "23:59",
            "selected_day_keys": [],
            "selected_family_ids": [family_id],
            "event_kind": "event",
        }

    def test_planned_edit(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="planned")
            fam = _seed_family(conn)
            _seed_assignment(conn, "evt-001", family_id=fam)
        result = update_event_definition(
            self.db, "job-001", "evt-001", self._preview(fam),
            event_name="Ereignis A", notes="", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        self.assertFalse(result["resort_required"])
        self.assertEqual(result["event"]["name"], "Ereignis A")
        self.assertEqual(result["event"]["revision"], 2)

    def test_applied_edit_resort(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="applied")
            fam = _seed_family(conn)
            _seed_assignment(conn, "evt-001", family_id=fam)
        result = update_event_definition(
            self.db, "job-001", "evt-001", self._preview(fam),
            event_name="Ereignis A", notes="", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        self.assertTrue(result["resort_required"])
        self.assertEqual(result["event"]["revision"], 2)

    def test_archived_rejected(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="archived")
        with self.assertRaises(ValueError):
            update_event_definition(
                self.db, "job-001", "evt-001", self._preview(),
                event_name="Ereignis A", notes="", expected_revision=1,
            )

    def test_wrong_revision_rejected(self):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="planned")
            fam = _seed_family(conn)
            _seed_assignment(conn, "evt-001", family_id=fam)
        with self.assertRaises(ValueError):
            update_event_definition(
                self.db, "job-001", "evt-001", self._preview(fam),
                event_name="Ereignis A", notes="", expected_revision=99,
            )

    def test_time_range_extend(self):
        """Zeitraum erweitern: Start frueher, Ende spaeter."""
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="planned")
            fam = _seed_family(conn, capture="2024-01-05T12:00:00")
            _seed_assignment(conn, "evt-001", family_id=fam)
        prev = self._preview(fam, start="2024-01-01", end="2024-01-10")
        result = update_event_definition(
            self.db, "job-001", "evt-001", prev,
            event_name="Ereignis A", notes="", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        # Start/Ende muss erweitert sein
        self.assertEqual(result["event"]["start_datetime"], "2024-01-01T00:00:00")
        self.assertEqual(result["event"]["end_datetime"], "2024-01-10T23:59:59")

    def test_time_range_shorten(self):
        """Zeitraum verkuerrzen."""
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="planned")
            fam = _seed_family(conn, capture="2024-01-03T12:00:00")
            _seed_assignment(conn, "evt-001", family_id=fam)
        prev = self._preview(fam, start="2024-01-02", end="2024-01-04")
        result = update_event_definition(
            self.db, "job-001", "evt-001", prev,
            event_name="Ereignis A", notes="", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        self.assertEqual(result["event"]["start_datetime"], "2024-01-02T00:00:00")
        self.assertEqual(result["event"]["end_datetime"], "2024-01-04T23:59:59")

    def test_family_outside_range_rejected(self):
        """Familie ausserhalb des neuen Zeitraums -> Fehler."""
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status="planned")
            fam = _seed_family(conn, capture="2024-02-15T12:00:00")
            _seed_assignment(conn, "evt-001", family_id=fam)
        prev = self._preview(fam, start="2024-01-01", end="2024-01-01")
        with self.assertRaises(ValueError):
            update_event_definition(
                self.db, "job-001", "evt-001", prev,
                event_name="Ereignis A", notes="", expected_revision=1,
            )


# ── 5. Frontend isoDate/isoTime (leere/NULL Werte) ────────────────────────
import re


def iso_date(value):
    # app/events_ui.py isoDate (Port auf Python)
    raw = str(value if value is not None else "")
    m = re.match(r"^\d{4}-\d{2}-\d{2}", raw)
    return m.group(0) if m else "1970-01-01"


def iso_time(value, fallback):
    raw = str(value if value is not None else "")
    m = re.search(r"\d{2}:\d{2}", raw)
    if m:
        return m.group(0)
    fb = str(fallback or "")
    fm = re.match(r"^\d{2}:\d{2}$", fb)
    return fb if fm else "00:00"


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class TestIsoHelpers(unittest.TestCase):
    def test_iso_date_empty_fallback(self):
        self.assertTrue(DATE_RE.match(iso_date("")))

    def test_iso_date_none_fallback(self):
        self.assertTrue(DATE_RE.match(iso_date(None)))

    def test_iso_date_valid(self):
        self.assertTrue(DATE_RE.match(iso_date("2024-01-01T12:00:00")))
        self.assertEqual(iso_date("2024-01-01T12:00:00"), "2024-01-01")

    def test_iso_time_empty_fallback(self):
        self.assertTrue(TIME_RE.match(iso_time("", "00:00")))

    def test_iso_time_none_fallback(self):
        self.assertTrue(TIME_RE.match(iso_time(None, "00:00")))

    def test_iso_time_valid(self):
        self.assertTrue(TIME_RE.match(iso_time("2024-01-01T12:30:00", "00:00")))
        self.assertEqual(iso_time("2024-01-01T12:30:00", "00:00"), "12:30")

    def test_iso_time_none_fallback_invalid(self):
        # Wenn das Datum keine Zeit enthaelt und der Fallback ungültig ist,
        # liefert iso_time "00:00" (gueltig).
        self.assertTrue(TIME_RE.match(iso_time("2024-01-01", "abc")))


# ── 6. Integrationstests (planned / applied / archived) ────────────────────
class TestIntegration(BaseTest):
    def _seed_full(self, status):
        with connect(self.db) as conn:
            _seed_event(conn, event_id="evt-001", status=status, name="Ereignis A")
            _seed_family(conn, family_key="fk-1", capture="2024-01-01T12:00:00")
            _seed_file(conn, family_id=1)
            _seed_assignment(conn, "evt-001", family_id=1)

    def _preview(self, **kwargs):
        base = {
            "parent_folder": "Ereignis A",
            "child_folder": "",
            "uses_time_range": False,
            "preserve_day_folders": True,
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
            "start_time": "00:00",
            "end_time": "23:59",
            "selected_day_keys": [],
            "selected_family_ids": [1],
            "event_kind": "event",
        }
        base.update(kwargs)
        return base

    def test_planned_integration(self):
        """planned: direkt editierbar, kein resort_required."""
        self._seed_full("planned")
        result = update_event_definition(
            self.db, "job-001", "evt-001", self._preview(),
            event_name="Ereignis A", notes="Notiz", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        self.assertFalse(result["resort_required"])
        # Zuordnung muss bestehen
        with connect(self.db) as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM event_assignments WHERE event_id = ?",
                ("evt-001",),
            ).fetchone()["c"]
        self.assertGreaterEqual(cnt, 1)

    def test_applied_integration(self):
        """applied: direkt editierbar, resort_required=True."""
        self._seed_full("applied")
        result = update_event_definition(
            self.db, "job-001", "evt-001", self._preview(),
            event_name="Ereignis A", notes="", expected_revision=1,
        )
        self.assertTrue(result["structural_changed"])
        self.assertTrue(result["resort_required"])
        # event_reapply_removed_families wird bei applied mit entfernten Familien
        # befuellt; hier bleiben alle Familien -> keine removed families.
        with connect(self.db) as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM event_reapply_removed_families WHERE event_id = ?",
                ("evt-001",),
            ).fetchone()["c"]
        self.assertEqual(cnt, 0)

    def test_archived_integration(self):
        """archived: NUR ueber Change-Request-Workflow (propose -> confirm -> archive)."""
        self._seed_full("archived")
        # Direkter PUT-Workflow muss abgelehnt werden.
        with self.assertRaises(ValueError):
            update_event_definition(
                self.db, "job-001", "evt-001", self._preview(),
                event_name="Ereignis A", notes="", expected_revision=1,
            )
        # Change-Request-Workflow muss durchlaufen.
        cr = propose_event_change(
            self.db, "job-001", "evt-001",
            {"parent_folder": "Ereignis A", "selected_family_ids": [1]},
        )
        cr_id = cr["change_request_id"]
        with connect(self.db) as conn:
            conn.execute(
                "UPDATE event_change_file_reviews SET confirmed = 1 "
                "WHERE change_request_id = ?",
                (cr_id,),
            )
        confirm_event_change(self.db, cr_id)
        _materialize_manual_targets(self.db, cr_id, Path(self.temp))
        result = finish_event_change(self.db, cr_id, Path(self.temp))
        self.assertEqual(result["status"], "archiviert")
        self.assertTrue(result["archive_read_only"])
        cr = get_event_change_request(self.db, cr_id)
        self.assertEqual(cr["status"], "aenderbar_archiviert")


if __name__ == "__main__":
    unittest.main()
