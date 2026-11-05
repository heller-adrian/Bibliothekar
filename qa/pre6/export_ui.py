"""Actual templates/functions for isolated offline acceptance of seven findings."""
import json,sys
from pathlib import Path
from app import main
from app.workspace_ui import WORKSPACE_HTML as ws
from app.events_ui import EVENTS_HTML as ev
from app.metadata_correction_ui import METADATA_CORRECTION_HTML as meta
from app.ui_i18n import I18N_UI_JS
from app.ui_shell import apply_shell

def part(s,a,b):return s[s.index(a):s.index(b,s.index(a))]
index=main.index()
json.dump({'index':index,'i18n':I18N_UI_JS,
 'database':part(index,"    const databaseDiagnosis =",'    let sourceDevices ='),
 'backup':part(ws,'    function selectableBackup','    function renderBackupFilter'),
 'save':part(ws,'    async function saveEvent()','    function onBackupFilterChange'),
 'events':apply_shell(ev,active_area='workspace',subarea='events'),
 'change':part(ev,'    async function showChangeRequestDetail(','    async function changeRequestAction('),
 'helpers':part(ev,'    function bk0511EventLabel','    async function showArchiveReversalDetail'),
 'families':part(ev,'    function mediaTypeLabel','    function fitMonospaceTree'),
 'meta':part(meta,'  function metadataTaskError','  async function applyTask')},
 Path(sys.argv[1]).open('w'))
