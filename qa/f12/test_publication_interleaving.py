"""Same F12 operation order/assertion, barrier at the new exclusive rename.

The historical module remains byte-identical; its os.replace hook is obsolete.
This is explicitly a new reproduction, not a renamed original PASS.
"""
import hashlib
import threading
from pathlib import Path

from test_interleavings import seed, finish, thread_call
from test_process_crashes import snapshot, checks_sql


def test_original_F12_sequence_at_exclusive_rename(tmp_path, monkeypatch):
    from app import folder_import as fi, import_publication as publication
    case, ev, data, db, ws = seed(tmp_path, 'trash', 'P402-new-atomic-boundary', monkeypatch)
    root = ws / 'SD-Kartensicherungen'
    original = root / '.incoming/P4/Original'; original.mkdir(parents=True)
    src = original / 'S.JPG'; src.write_bytes(b'synthetic-import')
    target = root / '2030/T.JPG'; target.parent.mkdir()
    plan = [dict(source_relative_path='S.JPG', destination_relative_path='2030/T.JPG',
                 size_bytes=src.stat().st_size, sha256=hashlib.sha256(src.read_bytes()).hexdigest())]
    reached = threading.Event(); proceed = threading.Event(); native = publication._native_rename
    def pause(*args):
        reached.set(); assert proceed.wait(10)
        return native(*args)
    monkeypatch.setattr(publication, '_native_rename', pause)
    thread, result = thread_call(lambda: fi.move_import_into_workspace(original, root, plan))
    assert reached.wait(10)
    target.write_bytes(b'synthetic-foreign')
    snapshot(case, ev / 'foreign-before-publication.json')
    proceed.set(); thread.join(10); assert not thread.is_alive()
    finish(case, ev, {'order': ['exists check', 'competing writer publishes target', 'exclusive rename'], 'result': result})
    assert target.read_bytes() == b'synthetic-foreign', 'Foreign destination overwritten between check and replace'
    assert src.read_bytes() == b'synthetic-import'
    assert result[0]['ok'] is False and 'existiert bereits' in result[0]['error']
    assert (original.parent / 'move-journal.json').is_file()
    checks_sql(snapshot(case, ev / 'verified-final.json'))
