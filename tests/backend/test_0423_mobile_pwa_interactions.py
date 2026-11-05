from __future__ import annotations

from pathlib import Path

import app.metadata_correction as metadata_correction
from app.metadata_correction import preview_multiple_metadata_correction
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_shell import BIBLIOTHEKAR_0423_CSS, BIBLIOTHEKAR_JS
from app.workspace_ui import WORKSPACE_HTML


def _multi_row(name: str, stamp: str) -> dict:
    return {
        "relative_path": name,
        "filename": name,
        "media_type": "jpeg",
        "selected_capture_time": stamp,
        "capture_time_confidence": "high",
        "size_bytes": 10,
        "sha256": ("a" if name.startswith("A") else "b" if name.startswith("B") else "c") * 64,
    }


def test_0423_multiple_preview_can_target_real_subset(monkeypatch):
    scan = {
        "files": [
            _multi_row("A.JPG", "2026-01-01T10:00:00"),
            _multi_row("B.JPG", "2026-01-01T10:05:00"),
            _multi_row("C.JPG", "2026-01-01T10:10:00"),
        ]
    }
    monkeypatch.setattr(metadata_correction, "_multiple_scan", lambda **_: scan)

    preview = preview_multiple_metadata_correction(
        workspace_root=Path("/workspace"),
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-01-01T11:00:00",
        selected_relative_paths=["A.JPG", "B.JPG"],
    )

    assert preview["file_count"] == 2
    assert preview["total_file_count"] == 3
    assert preview["selection_is_subset"] is True
    assert [row["relative_path"] for row in preview["files"]] == ["A.JPG", "B.JPG"]
    assert preview["files"][1]["new_datetime"] == "2026-01-01T11:05:00"


def test_0423_explicit_full_multiple_selection_keeps_full_folder_semantics(monkeypatch):
    scan = {
        "files": [
            _multi_row("A.JPG", "2026-01-01T10:00:00"),
            _multi_row("B.JPG", "2026-01-01T10:05:00"),
        ]
    }
    monkeypatch.setattr(metadata_correction, "_multiple_scan", lambda **_: scan)

    preview = preview_multiple_metadata_correction(
        workspace_root=Path("/workspace"),
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-01-01T11:00:00",
        selected_relative_paths=["A.JPG", "B.JPG"],
    )

    assert preview["file_count"] == 2
    assert preview["total_file_count"] == 2
    assert preview["selection_is_subset"] is False


def test_0423_mobile_metadata_detail_uses_real_detail_card_in_dialog():
    html = METADATA_CORRECTION_HTML

    assert 'id="meta-detail-card"' in html
    assert 'id="multi-detail-card"' in html
    assert 'id="meta-mobile-dialog"' in html
    assert 'id="meta-mobile-dialog-close"' in html
    assert 'function openMobileDetail(kind,mode="full")' in html
    assert 'function closeMobileDetail()' in html
    assert 'openMobileDetail("meta","full")' in html
    assert 'openMobileDetail("multiple","full")' in html
    assert "closeMobileDetail();\n      await scan(false,true);" in html


def test_0423_metadata_cards_wrap_and_modal_are_standalone_only():
    css = BIBLIOTHEKAR_0423_CSS

    assert 'html[data-bk-display-mode="standalone"] body[data-bk-area="metadata"] .meta-file' in css
    assert "overflow-wrap: anywhere !important" in css
    assert "white-space: normal !important" in css
    assert '#meta-mobile-dialog #meta-detail-card' in css
    assert '#meta-mobile-dialog #multi-detail-card' in css
    assert 'html[data-bk-display-mode="browser"] body[data-bk-area="metadata"]' not in css


def test_0423_workspace_review_badge_stays_inside_pwa_card():
    css = BIBLIOTHEKAR_0423_CSS

    assert 'body[data-bk-area="workspace"] .day-card.review-card' in css
    assert "minmax(72px, 88px)" in css
    assert ".day-card.review-card > .badge" in css
    assert "max-width: 88px !important" in css


def test_0423_quick_select_gesture_is_pwa_only_and_animated():
    shell = BIBLIOTHEKAR_JS

    assert 'root.dataset.bkDisplayMode === "standalone"' in shell
    assert 'matchMedia?.("(max-width: 820px)")' in shell
    assert 'touchstart' in shell
    assert 'touchmove' in shell
    assert 'event.preventDefault();' in shell
    assert 'document.elementFromPoint' in shell
    assert '"bk:pwa-select"' in shell
    assert "bk-pwa-select-wobble" in shell
    assert "@keyframes bk-pwa-select-wobble" in BIBLIOTHEKAR_0423_CSS


def test_0423_workspace_and_metadata_cards_opt_into_quick_select():
    assert 'card.dataset.bkPwaSelect = "workspace-capture"' in WORKSPACE_HTML
    assert 'card.addEventListener("bk:pwa-select"' in WORKSPACE_HTML

    html = METADATA_CORRECTION_HTML
    assert 'data-bk-pwa-select="metadata-file"' in html
    assert 'data-bk-pwa-select="metadata-multiple"' in html
    assert 'row.addEventListener("bk:pwa-select"' in html
    assert "multipleSelectedSet:new Set()" in html
    assert "selected_relative_paths:" in html


def test_0423_subset_direct_import_is_guarded_before_apply():
    source = Path("app/main.py").read_text(encoding="utf-8")

    assert 'mode == "apply_and_import" and selected_relative_paths' in source
    assert 'selection_preview.get("selection_is_subset")' in source
    assert "Eine Teilmenge kann korrigiert, aber nicht direkt als kompletter" in source
