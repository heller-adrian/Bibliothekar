"""Plan, but never execute, one narrowly scoped Camera Raw XMP reference edit."""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from app.xmp_raw_filename import _raw_values, rewrite_raw_filename, XmpReferenceError


# RAW/DNG camera masters. A JPEG or export is never a RawFileName owner.
RAW_EXTENSIONS = {
    ".raf", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".cr2", ".cr3",
    ".crw", ".dng", ".orf", ".rw2", ".pef", ".3fr", ".iiq", ".mos",
    ".erf", ".k25", ".kdc", ".mef", ".mrw", ".raw", ".rwl", ".x3f",
}
MAX_XMP_BYTES = 16 * 1024 * 1024


class XmpPlanError(ValueError):
    pass


def raw_name_pair(family, targets, raw_name):
    owners = [
        (PurePosixPath(member["relative_path"]).name, PurePosixPath(target).name)
        for member, target in zip(family, targets, strict=True)
        if target and PurePosixPath(member["relative_path"]).suffix.casefold() in RAW_EXTENSIONS
        and PurePosixPath(member["relative_path"]).name.casefold() == raw_name.casefold()
    ]
    return owners[0] if len(owners) == 1 else None


def planned_edit(family, targets, payload: bytes):
    """Return old/new digests and names iff the referenced RAW is renamed.

    Only original members of the *already proven* family are eligible. A
    global filename search can match an unrelated reused camera filename.
    """
    if not isinstance(payload, bytes) or len(payload) > MAX_XMP_BYTES:
        raise XmpPlanError("XMP is too large for a safely bounded transformation.")
    try:
        original = _raw_values(payload)
    except XmpReferenceError as exc:
        raise XmpPlanError(str(exc)) from exc
    if not original:
        return None
    if len(original) != 1:
        raise XmpPlanError("XMP contains ambiguous RAW references.")
    old_name = original[0]
    owner = raw_name_pair(family, targets, old_name)
    if owner is None:
        raise XmpPlanError("XMP RawFileName does not refer to one uniquely matched master.")
    _, new_name = owner
    if old_name == new_name:
        return None
    try:
        edited = rewrite_raw_filename(payload, old_name, new_name)
    except XmpReferenceError as exc:
        raise XmpPlanError(str(exc)) from exc
    return {
        "xmp_old_raw_name": old_name,
        "xmp_new_raw_name": new_name,
        "current_sha256": hashlib.sha256(edited).hexdigest(),
        "current_size_bytes": len(edited),
    }
