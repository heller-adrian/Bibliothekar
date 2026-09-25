import subprocess
import textwrap

from app.main import APP_VERSION
from app.workspace_ui import WORKSPACE_HTML
from app.ui_shell import BIBLIOTHEKAR_CSS


def _js_block(start_marker: str, end_marker: str) -> str:
    start = WORKSPACE_HTML.index(start_marker)
    end = WORKSPACE_HTML.index(end_marker, start)
    return WORKSPACE_HTML[start:end]


def test_0267_version_and_planning_helpers_are_present():
    assert APP_VERSION == "0.26.8"
    assert "function planningOverview()" in WORKSPACE_HTML
    assert "function availableDayGroups()" in WORKSPACE_HTML


def test_0267_dom_smoke_renders_eight_day_cards_with_real_render_days_code():
    helpers = _js_block("    function planningOverview()", "    function renderDays()")
    renderer = _js_block("    function renderDays()", "    function renderSelection()")
    script = textwrap.dedent(
        r"""
        const groups = Array.from({length: 8}, (_, index) => {
          const day = String(19 + index).padStart(2, "0");
          return {
            group_type: "day",
            card_key: "2026-07-" + day,
            day_key: "2026-07-" + day,
            has_date: true,
            file_count: 2,
            family_count: 1,
            total_size_bytes: 100,
            review_required_count: 0,
            reassignment_pending: false,
            partially_assigned: false
          };
        });
        let workspace = {
          planning_overview: {
            event_groups: [],
            available_day_groups: groups,
            timeline_groups: groups
          }
        };
        let selectedDays = new Set();

        function element() {
          return {
            className: "",
            dataset: {},
            style: {},
            children: [],
            checked: false,
            textContent: "",
            type: "",
            _html: "",
            classList: { add(){}, remove(){}, toggle(){} },
            appendChild(child) { this.children.push(child); },
            addEventListener(){},
            set innerHTML(value) { this._html = value; },
            get innerHTML() { return this._html; }
          };
        }
        const dayList = element();
        const document = { createElement(){ return element(); } };
        function formatDay(value){ return value; }
        function formatBytes(value){ return String(value); }
        function formatTimelineDateRange(){ return ""; }
        function workspaceStatusLabel(value){ return value || ""; }
        function escapeHtml(value){ return String(value ?? ""); }
        function openStoredEventPreview(){}
        function renderSelection(){}
        """
    ) + "\n" + helpers + "\n" + renderer + textwrap.dedent(
        r"""
        renderDays();
        if (dayList.children.length !== 8) {
          throw new Error("expected 8 rendered day cards, got " + dayList.children.length);
        }
        """
    )
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_0267_sticky_header_is_scroll_linked_and_not_time_triggered():
    assert 'id="selection-bar-anchor"' in WORKSPACE_HTML
    assert 'getElementById("bk-workspace-dock")' in WORKSPACE_HTML
    assert "const selectionMorphDistance=128" in WORKSPACE_HTML
    assert "function selectionMorphProgressForPositions(anchorTop,targetTop)" in WORKSPACE_HTML
    assert "function applySelectionMorphProgress(progress)" in WORKSPACE_HTML
    assert "selectionBar.animate" not in WORKSPACE_HTML
    assert "animateSelectionMorph" not in WORKSPACE_HTML
    assert "selectionDockTarget.appendChild(selectionBar)" not in WORKSPACE_HTML
    assert "selectionBarAnchor.after(selectionBar)" not in WORKSPACE_HTML
    assert 'setProperty("position","fixed","important")' in WORKSPACE_HTML
    assert 'setProperty("z-index","3105","important")' in WORKSPACE_HTML
    assert "z-index:3105 !important" in WORKSPACE_HTML
    assert "const padRight=64" in WORKSPACE_HTML
    assert "const xP=1-Math.pow(1-p,2.15)" in WORKSPACE_HTML
    assert "const yP=normalizedExpo(p,1.35,6)" in WORKSPACE_HTML
    assert "const summaryTargetCenter=window.innerWidth/2" in WORKSPACE_HTML
    assert "function selectionFrameLeft(anchorLeft,targetLeft,xProgress,summaryLeft,padding=14)" in WORKSPACE_HTML
    assert "const targetFrameLeft=summaryTargetCenter-summaryWidth/2-14" in WORKSPACE_HTML
    assert "let selectionSummaryStartCenter=0" in WORKSPACE_HTML
    assert 'selectionSummary.style.position="absolute"' in WORKSPACE_HTML
    assert "const compactP=smoothStep(clamp01(p/.86))" in WORKSPACE_HTML
    assert "const targetFrameLeft=summaryTargetCenter-summaryWidth/2-14" in WORKSPACE_HTML
    assert "selectionFrameLeft(" in WORKSPACE_HTML
    assert 'setProperty("--selection-button-height",buttonHeight+"px")' in WORKSPACE_HTML
    assert 'setProperty("--selection-button-font-size",buttonFont+"rem")' in WORKSPACE_HTML
    assert "const buttonHeight=42+(38-42)*compactP" in WORKSPACE_HTML
    assert "const frameFade=clamp01((p-.40)/.30)" in WORKSPACE_HTML
    assert "const surfaceFade=clamp01((p-.46)/.30)" in WORKSPACE_HTML
    assert 'classList.toggle("is-stuck",subnavStuck)' in WORKSPACE_HTML
    assert 'selectionMorphProgressForPositions(anchorTop,target.top)' in WORKSPACE_HTML
    assert 'padding-bottom:clamp(170px,18vh,240px) !important;' in WORKSPACE_HTML
    assert 'border-color:transparent !important;' in WORKSPACE_HTML
    assert 'window.matchMedia("(min-width: 821px)")' in WORKSPACE_HTML
    assert ".selection-bar.is-docked" in WORKSPACE_HTML
    assert ".selection-bar.is-scroll-floating .selection-top-button" in WORKSPACE_HTML
    assert '.bk-shell::after {' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="workspace"] .bk-shell::after' not in BIBLIOTHEKAR_CSS
    assert ".bk-workspace-subnav.is-stuck" in BIBLIOTHEKAR_CSS
    assert "@media (min-width: 821px) and (max-width: 1180px)" in BIBLIOTHEKAR_CSS


def test_0267_scroll_morph_progress_is_continuous():
    start = WORKSPACE_HTML.index("    function clamp01(value)")
    end = WORKSPACE_HTML.index("    function selectionDockGeometry()", start)
    helpers = WORKSPACE_HTML[start:end]
    script = helpers + r"""
const selectionMorphDistance=128;
const far=selectionMorphProgressForPositions(500,100);
const halfway=selectionMorphProgressForPositions(164,100);
const dock=selectionMorphProgressForPositions(100,100);
if (far !== 0) throw new Error("far position must not morph");
if (Math.abs(halfway-.5) > .0001) throw new Error("halfway must be 0.5: "+halfway);
if (dock !== 1) throw new Error("dock position must be 1");
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_0267_scroll_morph_curve_moves_horizontal_before_vertical():
    start = WORKSPACE_HTML.index("    function clamp01(value)")
    end = WORKSPACE_HTML.index("    function selectionDockGeometry()", start)
    helpers = WORKSPACE_HTML[start:end]
    script = helpers + r"""
const p=.5;
const xP=1-Math.pow(1-p,2.15);
const yP=normalizedExpo(p,1.35,6);
if (!(xP > yP)) throw new Error("horizontal progress must lead vertical progress");
if (!(xP > .7)) throw new Error("horizontal midpoint should already be advanced: "+xP);
if (!(yP < .4)) throw new Error("vertical midpoint should still lag: "+yP);
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_0267_selection_summary_targets_true_viewport_center():
    assert 'const selectionSummary=selectionBar?.querySelector(".selection-summary")' in WORKSPACE_HTML
    assert "const summaryTargetCenter=window.innerWidth/2" in WORKSPACE_HTML
    assert "summaryTargetCenter-selectionSummaryStartCenter" in WORKSPACE_HTML
    assert 'selectionSummary.style.left=(summaryCenter-left-summaryWidth/2)+"px"' in WORKSPACE_HTML
    assert "margin-left:auto" in WORKSPACE_HTML
    assert "z-index:3105 !important" in WORKSPACE_HTML


def test_0267_selection_frame_keeps_summary_inside_and_finishes_snug():
    start = WORKSPACE_HTML.index("    function clamp01(value)")
    end = WORKSPACE_HTML.index("    function clearSelectionMorphStyles()", start)
    helpers = WORKSPACE_HTML[start:end]
    script = helpers + r"""
const summaryLeft=500;
const midway=selectionFrameLeft(100,486,.75,summaryLeft,14);
if (midway > 486) throw new Error("frame must never overtake summary left edge");
const end=selectionFrameLeft(100,486,1,summaryLeft,14);
if (end !== 486) throw new Error("end frame must finish 14px before summary");
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_0267_event_creation_dialog_uses_spacious_two_row_layout():
    assert "#event-dialog{inline-size:min(700px" in WORKSPACE_HTML
    assert ".event-boundaries{display:grid;grid-template-columns:minmax(0,1fr)" in WORKSPACE_HTML
    assert ".create-subevent-grid{display:grid;grid-template-columns:minmax(0,1fr)" in WORKSPACE_HTML
    assert ".create-subevent-end-row{display:grid;grid-template-columns:minmax(0,1fr) auto" in WORKSPACE_HTML
    assert 'class="create-subevent-name"' in WORKSPACE_HTML
    assert 'class="danger-button create-subevent-remove"' in WORKSPACE_HTML
    assert "Unterereignisse organisieren Teilzeiträume" not in WORKSPACE_HTML
    assert ".create-subevent-head button{white-space:nowrap" in WORKSPACE_HTML
