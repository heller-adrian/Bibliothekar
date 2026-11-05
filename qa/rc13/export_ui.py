"""Export actual RC13 templates/renderer for offline Chromium acceptance."""
import json
from pathlib import Path
import sys
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.transfer_ui import TRANSFER_HTML
from app.ui_i18n import I18N_UI_JS
from app.ui_shell import apply_shell, BIBLIOTHEKAR_0444_JS, BIBLIOTHEKAR_0444_CSS
from app.storage_warning_ui import storage_warning_html

def part(s,start,end):return s[s.index(start):s.index(end,s.index(start))]
bundle={
 'events':apply_shell(EVENTS_HTML,active_area='workspace',subarea='events'),
 'workspace':apply_shell(WORKSPACE_HTML,active_area='workspace',subarea='captures'),
 'archive':apply_shell(TRANSFER_HTML,active_area='archive'),
 'i18n':I18N_UI_JS,
 'change':part(EVENTS_HTML,'    async function showChangeRequestDetail(','    async function changeRequestAction('),
 'reversal':part(EVENTS_HTML,'    async function showArchiveReversalDetail','    async function showChangeRequestDetail'),
 'helpers':part(EVENTS_HTML,'    function bk0511EventLabel','    async function showArchiveReversalDetail'),
 'families':part(EVENTS_HTML,'    function mediaTypeLabel','    function fitMonospaceTree'),
 'sort':part(EVENTS_HTML,'    function renderSortPlan(','    async function pollSortRun('),
 'activity':BIBLIOTHEKAR_0444_JS,
 'activity_css':BIBLIOTHEKAR_0444_CSS,
 'warning':storage_warning_html({'ready':False,'state':'DEGRADED','existing_installation':True,
    'workspace':'/private/tmp/rc13-ui-unused','issues':[{'code':'missing','path':'/workspace/Trash'}],
    'folders':[{'key':'trash_directory_name','path':'/workspace/Trash','expected_identity':[97,27734],'status':'missing'}]}),
}
Path(sys.argv[1]).write_text(json.dumps(bundle))
