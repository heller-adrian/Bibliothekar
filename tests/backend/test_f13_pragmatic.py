import hashlib
from pathlib import Path
import pytest
from app import ssd_archive_guard as guard
from app.transfer_ui import TRANSFER_HTML
from app.ui_i18n import UI_TRANSLATIONS
from qa.f13.test_f13_ssd_guard import RehashOnly


def test_f13_rehash_detects_changed_archive_and_preserves_source(tmp_path,monkeypatch):
    monkeypatch.setattr(guard,'InotifyWatcher',RehashOnly)  # explicit B comparison
    archive=tmp_path/'archive';archive.mkdir();p=archive/'A.JPG';src=tmp_path/'ssd.JPG'
    original=b'synthetic-original';p.write_bytes(original);src.write_bytes(original)
    g=guard.ArchiveGuard(archive,['A.JPG'])
    try:
        g.verify('A.JPG',len(original),hashlib.sha256(original).hexdigest(),src.stat())
        with p.open('r+b') as writer:writer.write(b'X'*len(original));writer.flush()
        with pytest.raises(guard.ArchiveConflict):g.verify('A.JPG',len(original),hashlib.sha256(original).hexdigest(),src.stat())
        assert src.read_bytes()==original
    finally:g.close()


def test_f13_dialog_warns_and_retry_is_explicit():
    assert 'Arbeitsbereich freigeben – unterbrochen' in TRANSFER_HTML
    assert 'möglicherweise nicht wiederherstellbar' in TRANSFER_HTML
    assert 'Archivdateien während der Freigabe nicht extern verändern' in TRANSFER_HTML
    assert 'Freigabe erneut versuchen' in TRANSFER_HTML
    assert TRANSFER_HTML.count('const confirmation=')==1
    assert "detail.textContent=String(error||'')" in TRANSFER_HTML
    assert 'Release workspace – interrupted' in UI_TRANSLATIONS.values()
