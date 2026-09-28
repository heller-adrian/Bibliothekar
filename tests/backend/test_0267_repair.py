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
    assert APP_VERSION == "0.27.3"
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


def test_0267_workspace_selection_is_permanently_docked_in_0269():
    assert 'id="selection-bar-anchor"' in WORKSPACE_HTML
    assert 'getElementById("bk-workspace-dock")' in WORKSPACE_HTML
    assert "function positionWorkspaceChrome()" in WORKSPACE_HTML
    assert 'selectionDockTarget.appendChild(selectionBar)' in WORKSPACE_HTML
    assert 'selectionBar.classList.add("is-header-docked")' in WORKSPACE_HTML
    assert ".selection-bar.is-header-docked" in WORKSPACE_HTML
    assert "selectionMorphDistance" not in WORKSPACE_HTML
    assert "applySelectionMorphProgress" not in WORKSPACE_HTML
    assert "selectionFrameLeft" not in WORKSPACE_HTML
    assert "normalizedExpo" not in WORKSPACE_HTML
    assert 'window.addEventListener("scroll",updateSelectionDock' not in WORKSPACE_HTML
    assert ".bk-workspace-subnav" in BIBLIOTHEKAR_CSS


def test_0267_selection_summary_is_aligned_to_workspace_tab_from_start():
    assert 'const workspaceTab=document.querySelector(\'.bk-tab[data-area="workspace"]\');' in WORKSPACE_HTML
    assert "function alignHeaderSelectionSummary()" in WORKSPACE_HTML
    assert 'selectionSummary.style.left=(tabRect.left+tabRect.width/2-barRect.left)+"px"' in WORKSPACE_HTML
    assert "requestAnimationFrame(alignHeaderSelectionSummary)" in WORKSPACE_HTML


def test_0267_metrics_move_into_capture_heading_on_desktop():
    assert 'getElementById("bk-capture-summary-slot")' in WORKSPACE_HTML
    assert 'captureSummarySlot.appendChild(summarySection)' in WORKSPACE_HTML
    assert 'summarySection?.classList.add("compact-heading-summary")' in WORKSPACE_HTML
    assert ".summary.compact-heading-summary" in WORKSPACE_HTML


def test_0267_event_creation_dialog_keeps_date_time_pairs_compact():
    assert "#event-dialog{inline-size:min(700px" in WORKSPACE_HTML
    assert ".event-boundaries{display:grid;grid-template-columns:minmax(0,1fr)" in WORKSPACE_HTML
    assert ".create-subevent-grid{display:grid;grid-template-columns:minmax(0,1fr)" in WORKSPACE_HTML
    assert ".create-subevent-top{display:flex" in WORKSPACE_HTML
    assert ".create-subevent-boundaries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in WORKSPACE_HTML
    assert "@media (max-width:460px){.event-boundary,.create-subevent-boundary{grid-template-columns:1fr}" in WORKSPACE_HTML
    assert 'class="create-subevent-name"' in WORKSPACE_HTML
    assert 'class="danger-button create-subevent-remove"' in WORKSPACE_HTML
    assert "Unterereignisse organisieren Teilzeiträume" not in WORKSPACE_HTML
    assert ".create-subevent-head button{white-space:nowrap" in WORKSPACE_HTML
