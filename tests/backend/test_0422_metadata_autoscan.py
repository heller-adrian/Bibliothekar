from pathlib import Path

from app.metadata_correction_ui import METADATA_CORRECTION_HTML


def test_0422_metadata_areas_scan_automatically_on_page_open():
    html = METADATA_CORRECTION_HTML

    assert 'Promise.all([' in html
    assert 'loadAreas(),' in html
    assert 'loadTasks()' in html
    assert 'scan(true,false).then(()=>{syncGeneralBusy();restoreGeneralJob();});' in html
    assert 'if(state.area==="multiple")return scanMultiple(announce);' in html


def test_0422_scan_button_and_status_show_busy_state():
    html = METADATA_CORRECTION_HTML

    assert 'function setScanBusy(busy)' in html
    assert 'button.classList.toggle("bk-busy",Boolean(busy))' in html
    assert 'button.setAttribute("aria-busy","true")' in html
    assert 'status.classList.toggle("bk-loading-status",Boolean(busy))' in html
    assert 'setScanBusy(true);' in html
    assert 'setScanBusy(false);' in html


def test_0422_manual_scan_button_remains_available():
    html = METADATA_CORRECTION_HTML

    assert 'id="meta-scan"' in html
    assert '>Bestand prüfen</button>' in html
    assert '$("meta-scan").addEventListener("click",()=>scan(true,true));' in html
