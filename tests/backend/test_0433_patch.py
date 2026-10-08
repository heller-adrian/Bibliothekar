from app import main


def test_0433_eta_appears_early_and_normalizes_backend_timestamps():
    html = main.index()
    assert "function backendTimestampMs(value)" in html
    assert "elapsed < 2000" in html
    assert "wird berechnet …" in html
    assert 'return "ca. " + seconds + " Sek."' in html


def test_0433_progress_percent_is_only_repeated_in_summary_not_bar_caption():
    html = main.index()
    assert '<span>Aktuelle Phase</span>' in html
    assert 'bk-stage-badge bk-stage-badge-header' in html
    assert '<span>${job.state === "completed" ? "Abgeschlossen" : "Gesamt"}</span>' in html
    assert 'class="bk-stage-value">${stagePercent} %</span>' in html
    assert "<span>${percent} %</span>" not in html
    assert "Fortschritt gesamt:" in html


def test_0433_completed_import_only_renders_overall_progress_row():
    html = main.index()
    assert 'progress-stack ${job.state === "completed" ? "completed-only" : ""}' in html
    assert '${job.state === "completed" ? "" : `' in html
    assert 'class="${job.state === "completed" ? "completed" : ""}"' in html
    assert '"Abgeschlossen" : "Gesamt"' in html


def test_0433_progress_stack_is_more_compact():
    html = main.index()
    assert "gap: 0.38rem;" in html
    assert "margin-top: 0.78rem;" in html
    assert "gap: 0.18rem;" in html
