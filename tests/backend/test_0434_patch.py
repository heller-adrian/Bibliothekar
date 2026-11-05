from pathlib import Path

from app import main


def test_0434_interrupted_and_failed_imports_stop_eta():
    html = main.index()
    assert 'job.state === "interrupted" || job.state === "failed"' in html
    assert 'return "—";' in html


def test_0434_terminal_imports_offer_remove_action():
    html = main.index()
    assert "const removableInterrupted =" in html
    assert 'job.state === "interrupted" || job.state === "failed"' in html
    assert 'data-discard-import="' in html
    assert ">Import entfernen</button>" in html
    assert 'host.querySelectorAll("[data-discard-import]")' in html
    assert "bindHistoryButtons(jobsElement)" in html
    assert '/api/jobs/${encodeURIComponent(jobId)}/discard' in html
    assert '{method:"DELETE"}' in html


def test_0434_backend_has_terminal_import_discard_route_and_cleanup():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert 'def _discard_terminal_import_job(job_id: str)' in source
    assert 'state not in {"failed", "interrupted"}' in source
    assert 'central_root / ".incoming" / job_id' in source
    assert "sha256_file(candidate) != expected_sha" in source
    assert "_remove_cancelled_import_job(job_id)" in source
    assert '"/api/jobs/{job_id}/discard"' in source
    assert "def api_discard_terminal_import(job_id: str)" in source


def test_0434_restart_guard_remains_in_place():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "mark_running_jobs_interrupted" in source
    assert "repair_interrupted_jobs_from_terminal_evidence" in source


def test_0434_each_import_lifecycle_has_a_terminal_action():
    html = main.index()
    assert 'data-cancel-import="' in html
    assert '"Import abbrechen"' in html
    assert "data-force-import=" in html
    assert 'data-discard-import="' in html
    assert ">Import entfernen</button>" in html
    assert 'data-delete-backup="' in html
    assert "Sicherung löschen" in html
