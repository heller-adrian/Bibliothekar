"""Generate actual warning HTML for isolated offline DE/EN browser probes."""
import json,sys
from pathlib import Path
from app.storage_warning_ui import storage_warning_html
base={'issues':[{'path':'/workspace/Trash','code':'missing'}],'can_initialize':False}
Path(sys.argv[1]).write_text(json.dumps({'allowed':storage_warning_html({**base,'can_setup_again':True,'setup_token':'a'*64}),'blocked':storage_warning_html({**base,'can_setup_again':False,'setup_blocker':'archive_content_survives'})}))
