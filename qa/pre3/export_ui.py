import json,sys
from pathlib import Path
from app.storage_warning_ui import storage_warning_html
status={'state':'AMBIGUOUS','ready':False,'issues':[{'code':'startup_failed','path':'/workspace','detail':'metadata_transfer_target_missing: /workspace/synthetic.JPG'}],
        'existing_installation':True,'folders':[],'can_initialize':False,'can_setup_again':False}
Path(sys.argv[1]).write_text(json.dumps({'html':storage_warning_html(status)}))
