"""RC14 frozen earliest-preflight invariants for safe legacy no-effect handling.

The historical EXIF verification deliberately ignored unparseable tags.
Current verification rejects them. A *negative* proof of what RC14 would
have done must use the historical condition, never today's stricter one.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from app import metadata_legacy_rc14_recovery as legacy
from app.operation_health import DomainStartupError


def test_rc14_first_check_distinguishes_actual_old_offset_failure(tmp_path, monkeypatch):
    path=tmp_path/"original.JPG"
    path.write_bytes(b"synthetic")
    reply={"SourceFile":str(path),
           "EXIF:DateTimeOriginal":"2025:12:07 15:04:37",
           "EXIF:OffsetTimeOriginal":"+13:00"}
    def fake(cmd,**kwargs):
        assert cmd[0]=="exiftool"
        return SimpleNamespace(returncode=0,stdout=json.dumps([reply]))
    monkeypatch.setattr(subprocess,"run",fake)
    assert legacy._rc14_original_preflight_refused(path,"2025-12-07T15:04:37")
    # If the matching tag had the Berlin December offset, RC14 itself
    # would pass, therefore no retrospective no-effect certificate.
    reply["EXIF:OffsetTimeOriginal"]="+01:00"
    assert not legacy._rc14_original_preflight_refused(path,"2025-12-07T15:04:37")
    # RC14 ignored unparseable dates, whereas the new verifier rejects them.
    # A single valid matching original plus an invalid secondary date must
    # still be treated as a POTENTIALLY SUCCESSFUL original preflight.
    reply["XMP:CreateDate"]="this is not a datetime"
    assert not legacy._rc14_original_preflight_refused(path,"2025-12-07T15:04:37")
    # A second valid but conflicting tag must cause the original failure.
    reply["XMP:CreateDate"]="2024:12:07 15:04:37+01:00"
    assert legacy._rc14_original_preflight_refused(path,"2025-12-07T15:04:37")


def test_rc14_negative_proof_refuses_foreign_media_and_unreliable_exiftool(tmp_path,monkeypatch):
    original=tmp_path/"original.JPG"
    original.write_bytes(b"original media")
    import hashlib
    sha=hashlib.sha256(original.read_bytes()).hexdigest()
    assert legacy._file_identity(original,sha,len(b"original media"))[2]==sha
    other=tmp_path/"copy.JPG"
    os.link(original,other)
    with pytest.raises(DomainStartupError,match="nonexclusive_original_file|source_inode_or_size_changed"):
        legacy._file_identity(original,sha,len(b"original media"))
    other.unlink()
    with pytest.raises(DomainStartupError,match="source_bytes_changed"):
        legacy._file_identity(original,"0"*64,len(b"original media"))
    symlink=tmp_path/"alias.JPG"
    symlink.symlink_to(original)
    with pytest.raises(DomainStartupError,match="source_inode_or_size_changed"):
        legacy._file_identity(symlink,sha,len(b"original media"))
    monkeypatch.setattr(subprocess,"run",
        lambda *a,**k:SimpleNamespace(returncode=2,stdout=""))
    with pytest.raises(DomainStartupError,match="original_exiftool_unavailable"):
        legacy._rc14_original_preflight_refused(original,"2025-12-07T15:04:37")
