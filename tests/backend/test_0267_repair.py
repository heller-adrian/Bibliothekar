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
    assert APP_VERSION == "0.26.7"
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
    assert "const padRight=64" in WORKSPACE_HTML
    assert 'classList.toggle("is-stuck",subnavStuck)' in WORKSPACE_HTML
    assert 'selectionMorphProgressForPositions(anchorTop,target.top)' in WORKSPACE_HTML
    assert 'padding-bottom:clamp(170px,18vh,240px) !important;' in WORKSPACE_HTML
    assert 'border-color:transparent !important;' in WORKSPACE_HTML
    assert 'window.matchMedia("(min-width: 821px)")' in WORKSPACE_HTML
    assert ".selection-bar.is-docked" in WORKSPACE_HTML
    assert ".selection-bar.is-scroll-floating .selection-top-button" in WORKSPACE_HTML
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
