from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_shell import BIBLIOTHEKAR_0424_CSS, BIBLIOTHEKAR_JS
from app.workspace_ui import WORKSPACE_HTML


def test_0424_quick_select_is_reversible_range_with_continuous_autoscroll():
    shell = BIBLIOTHEKAR_JS

    assert "rangeKeys: new Set()" in shell
    assert "baseline: new Map()" in shell
    assert "function bkPwaApplyRange(" in shell
    assert 'bkPwaDispatchSelect(card, "set", desired)' in shell
    assert "gesture.baseline.get(key)" in shell
    assert "window.requestAnimationFrame(bkPwaSelectionFrame)" in shell
    assert "window.scrollBy(0, speed)" in shell
    assert "bkPwaUpdateGesturePoint(gesture)" in shell
    assert "function bkPwaSelectionSafeBounds()" in shell
    assert "item.rect.top >= bounds.top" in shell
    assert "item.rect.bottom <= bounds.bottom" in shell


def test_0424_workspace_respects_select_and_deselect_from_range_gesture():
    html = WORKSPACE_HTML

    assert 'card.dataset.bkPwaKey = key' in html
    assert 'const desired = phase === "set"' in html
    assert 'selectedDays.delete(key)' in html
    assert 'checkbox.checked = desired' in html
    assert 'card.classList.toggle("selected", desired)' in html


def test_0424_metadata_long_press_enters_real_checkbox_selection_mode():
    html = METADATA_CORRECTION_HTML

    assert 'data-bk-pwa-key="' in html
    assert "esc(fileKey(file))" in html
    assert 'if(phase==="start"&&!state.selectionMode)' in html
    assert "state.selectionMode=true;" in html
    assert "renderFiles();renderDetails();" in html
    assert 'const desired=phase==="set"' in html
    assert "state.selectedSet.delete(index)" in html
    assert 'checkbox.checked=desired' in html


def test_0424_multiple_correction_has_same_real_selection_mode():
    html = METADATA_CORRECTION_HTML

    assert 'id="multi-select-mode"' in html
    assert 'id="multi-select-all"' in html
    assert "multipleSelectionMode:false" in html
    assert 'data-multi-check="' in html
    assert 'if(phase==="start"&&!state.multipleSelectionMode)' in html
    assert "state.multipleSelectionMode=true;" in html
    assert "state.multipleSelectedSet.delete(index)" in html
    assert 'checkbox.checked=desired' in html


def test_0424_single_detail_is_fullscreen_and_multi_selection_is_nonmodal_sheet():
    html = METADATA_CORRECTION_HTML
    css = BIBLIOTHEKAR_0424_CSS

    assert 'function openMobileDetail(kind,mode="full")' in html
    assert 'if(normalizedMode==="compact")dialog.show();' in html
    assert "else dialog.showModal();" in html
    assert 'openMobileDetail("meta","full")' in html
    assert 'openMobileDetail("multiple","full")' in html
    assert 'openMobileDetail(kind,"compact")' in html

    assert "#meta-mobile-dialog.full-detail[open]" in css
    assert "height: 100dvh;" in css
    assert "max-height: none;" in css
    assert "#meta-mobile-dialog.compact-selection[open]" in css
    assert "max-height: 44dvh;" in css
    assert "-webkit-overflow-scrolling: touch;" in css
    assert "backdrop-filter: none;" in css


def test_0424_wobble_no_longer_scales_cards_at_viewport_edges():
    css = BIBLIOTHEKAR_0424_CSS

    assert "@keyframes bk-pwa-select-wobble" in css
    assert "translateX(-2px)" in css
    assert "translateX(2px)" in css
    assert "scale(" not in css
