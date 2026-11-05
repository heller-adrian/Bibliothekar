import json,subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,'qa/rc14/export_ui.py',sys.argv[1]],check=True)
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_pre import TRANSLATIONS
p=Path(sys.argv[1]);b=json.loads(p.read_text());b['metadata']=METADATA_CORRECTION_HTML;b['messages']=TRANSLATIONS;p.write_text(json.dumps(b))
