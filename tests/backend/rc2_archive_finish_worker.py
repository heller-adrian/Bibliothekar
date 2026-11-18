"""Kill only this synthetic archive worker at a deterministic finish boundary."""
import json
import os
from pathlib import Path
import signal
import sys

from app import archive_staging, root_operations
from app.event_change_apply import finish_event_change

case = json.loads(Path(sys.argv[1]).read_text())


def crash():
    Path(case['checkpoint']).write_text(case['phase'])
    os.kill(os.getpid(), signal.SIGKILL)


if case['phase'] == 'before_commit':
    archive_staging.cleanup_archive_change_staging = lambda *args, **kwargs: crash()
elif case['phase'] == 'after_commit':
    original = root_operations._write

    def write(path, value):
        if Path(path).name.startswith('finished-') and any(
                record['ids'].get('function') == 'app.event_change_apply.finish_event_change'
                for record in root_operations._ACTIVE.get()):
            crash()
        return original(path, value)

    root_operations._write = write
else:
    raise AssertionError(case['phase'])

finish_event_change(Path(case['db']), case['cr_id'], Path(case['archive']), Path(case['workspace']))
raise AssertionError('The selected synthetic crash boundary was not reached')
