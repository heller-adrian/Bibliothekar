import json
from pathlib import Path
import subprocess,sys
subprocess.run([sys.executable,'qa/rc13/export_ui.py',sys.argv[1]],check=True)
from app.workspace_ui import WORKSPACE_HTML
p=Path(sys.argv[1]);bundle=json.loads(p.read_text())
a=WORKSPACE_HTML.index('    function renderDays()');b=WORKSPACE_HTML.index('    function selectedDatedGroups()',a)
bundle['days']=WORKSPACE_HTML[a:b]
p.write_text(json.dumps(bundle))
