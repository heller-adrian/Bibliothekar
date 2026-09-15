from pathlib import Path

from app.archive_reassignment import _target_for_new_event


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _FakeConnection:
    def __init__(self):
        self.rows = [
            {"id": 1, "selected_capture_time": "2026-07-23T15:31:43", "family_key": "DSCF1443"},
            {"id": 2, "selected_capture_time": "2026-07-23T18:01:49", "family_key": "DSCF1477"},
            {"id": 3, "selected_capture_time": "2026-07-23T21:51:39", "family_key": "DSCF1517"},
        ]

    def execute(self, sql, params):
        return _Result(self.rows)


def test_archive_reassignment_new_event_has_no_implicit_child_time_folder():
    target = _target_for_new_event(
        _FakeConnection(),
        "job",
        [1, 2, 3],
        "Test 23 später",
        "2026-07-23T12:00:00",
        "2026-07-23T23:00:59",
    )
    assert target["uses"] == 0
    assert target["child_name"] is None
    assert target["child_folder"] is None
    assert target["preserve"] == 0
    # Grenzen stammen aus dem exakt freigewordenen Segment, nicht aus
    # Min/Max der tatsächlich vorhandenen Aufnahmen.
    assert target["start"] == "2026-07-23T12:00:00"
    assert target["end"] == "2026-07-23T23:00:59"
    assert target["folder"] == "07-23 - Test 23 später"


def test_events_ui_has_visible_change_request_verification_feedback():
    source = Path("app/events_ui.py").read_text()
    assert 'id="change-verify-progress"' in source
    assert 'Prüfung läuft …' in source
    assert '✓ Prüfung erfolgreich' in source
    assert '✕ Prüfung mit Problemen' in source
    assert 'Fehlt am Ziel' in source
    assert 'Liegt noch am alten Ort' in source
    assert 'SHA-256 abweichend' in source
    assert 'Nach erfolgreicher Prüfung abschließen' in source
