"""Conservative capture matching for media discovered in separate directories."""
from collections import defaultdict
from datetime import datetime, timezone
from itertools import chain
from fractions import Fraction
from pathlib import PurePosixPath
import re
import unicodedata


IDENTITY_TAGS = ("ImageUniqueID", "BodySerialNumber", "OriginalRawFileName")
IDENTITY_VERSION = 2


def _normalized(value):
    return unicodedata.normalize("NFC", str(value or "").strip().casefold())


def capture_identity(metadata):
    """Use only known identity tags and require agreement between copies."""
    ids = {_normalized(metadata.get(key)) for key in (
        "EXIF:ExifIFD:ImageUniqueID", "XMP:XMP-exifEX:ImageUniqueID", "XMP:XMP-exif:ImageUniqueID",
    )} - {""}
    serials = {_normalized(metadata.get(key)) for key in (
        "EXIF:ExifIFD:BodySerialNumber", "XMP:XMP-exifEX:BodySerialNumber",
    )} - {"", "unknown", "none", "n/a"}
    serials = {serial for serial in serials if any(char.isalnum() and char != "0" for char in serial)}
    valid_ids = {value for value in ids if re.fullmatch(r"[0-9a-f]{32}", value) and len(set(value)) > 1}
    return {
        "id": next(iter(valid_ids)) if len(valid_ids) == 1 else "",
        "serial": next(iter(serials)) if len(serials) == 1 else "",
        "original_raw": _normalized(metadata.get("DNG:IFD0:OriginalRawFileName")
                                    or metadata.get("EXIF:IFD0:OriginalRawFileName")),
        "conflict": len(ids) > 1 or len(serials) > 1,
    }


def _role(record):
    kind = record.get("media_type")
    return "dng" if kind == "raw" and record["extension"] == ".dng" else kind


def _camera(record):
    return _normalized(record.get("camera_make")), _normalized(record.get("camera_model"))


def _time(record):
    value = record.get("selected_capture_time")
    if not value or record.get("review_required") or record.get("metadata_error"):
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _same_setting(left, right):
    """Reject contradictory exposure evidence; accept equivalent numeric forms."""
    if left in (None, "") or right in (None, ""):
        return True
    try:
        return Fraction(str(left).strip()) == Fraction(str(right).strip())
    except (ValueError, ZeroDivisionError):
        return _normalized(left) == _normalized(right)


def _compatible(first, second):
    a, b = first["capture_identity"], second["capture_identity"]
    if a["id"] and b["id"] and a["id"] != b["id"]:
        return False
    if a["serial"] and b["serial"] and a["serial"] != b["serial"]:
        return False
    left, right = _time(first), _time(second)
    if left is None or right is None or left.replace(microsecond=0) != right.replace(microsecond=0):
        return False
    if left.microsecond and right.microsecond and left != right:
        return False
    a_settings = first.get("capture_settings") or {}
    b_settings = second.get("capture_settings") or {}
    if any(not _same_setting(a_settings.get(field), b_settings.get(field))
           for field in ("exposure", "aperture", "iso")):
        return False
    for converted, original in ((first, second), (second, first)):
        original_name = converted["capture_identity"].get("original_raw")
        if _role(converted) == "dng" and _role(original) == "raw" and original_name:
            if original_name != _normalized(PurePosixPath(original["relative_path"]).name):
                return False
    return True


def split_family_groups(groups, *, ending, cancel=lambda: None):
    """Yield only sets backed by unambiguous, mutually compatible evidence.

    Each input supplies its local family key, its member records and eligibility.
    False eligibility still contributes to ambiguity (e.g. already owned files).
    """
    by_id, by_precision, by_context = defaultdict(set), defaultdict(set), defaultdict(set)
    candidates = {}
    primary_by_name = defaultdict(set)
    standalone_sidecars = {}
    for key, members, eligible in groups:
        cancel()
        primaries = [item for item in members if _role(item) in {"raw", "jpeg", "dng"}]
        evidence = primaries or [item for item in members if _role(item) == "xmp"]
        # Keep explicit original.RAF.xmp sidecars discoverable even if the
        # sidecar contains no own EXIF camera identity or shooting timestamp.
        if not primaries and eligible and len(members) == 1 and _role(members[0]) == "xmp":
            standalone_sidecars[key] = members[0]
        for primary in primaries:
            # A sidecar can point to its media by exact filename without
            # assuming RAW/JPEG/XMP directories or any historic folder layout.
            name = _normalized(PurePosixPath(primary["relative_path"]).name)
            primary_by_name[name].add(key)
        if not evidence:
            continue
        # A local family with multiple media files is a single unit. Every
        # primary must corroborate it before it can acquire more members.
        usable = eligible and all(_role(item) in {"raw", "jpeg", "dng", "xmp"} for item in members)
        has_proof = False
        for item in evidence:
            identity = item.get("capture_identity") or {}
            camera = _camera(item)
            if not identity or not all(camera):
                continue
            if identity["id"]:
                by_id[(camera, identity["id"])].add(key)
                has_proof = True
            instant = _time(item)
            source = item.get("selected_capture_source") or ""
            if (instant and source.endswith(":DateTimeOriginal")
                    and _role(item) in {"raw", "jpeg", "dng"}):
                # Folder names are not part of capture identity. Use camera,
                # the original camera filename stem and the EXIF capture instant
                # to assemble *candidates* anywhere in the scanned collection.
                # The component validator then requires compatible exposures,
                # unique media roles and no competing same-role candidates.
                by_context[(camera, _normalized(PurePosixPath(key).name),
                            instant.replace(microsecond=0))].add(key)
                has_proof = True
                if identity["serial"] and instant.microsecond:
                    by_precision[(camera, identity["serial"],
                                  _normalized(PurePosixPath(key).name), instant)].add(key)
        if has_proof:
            candidates[key] = (members, evidence, usable)

    by_sidecar = {}
    for key, sidecar in standalone_sidecars.items():
        cancel()
        path = PurePosixPath(sidecar["relative_path"])
        original_name = path.stem if path.suffix.casefold() == ".xmp" else ""
        if PurePosixPath(original_name).suffix.casefold() not in {
            ".raf", ".nef", ".cr2", ".cr3", ".arw", ".orf", ".rw2",
            ".dng", ".jpg", ".jpeg",
        }:
            continue
        owners = primary_by_name.get(_normalized(original_name), set())
        # Sidecars with no independent capture identity are linked only when
        # there is one possible original in the *whole* scan. Ambiguity never
        # gets resolved by guessing from directory labels.
        if len(owners) != 1:
            continue
        [owner] = owners
        if owner not in candidates or not candidates[owner][2]:
            continue
        exact = [item for item in candidates[owner][0]
                 if _normalized(PurePosixPath(item["relative_path"]).name) == _normalized(original_name)]
        if len(exact) != 1:
            continue
        original = exact[0]
        identity = sidecar.get("capture_identity") or {}
        match = original.get("capture_identity") or {}
        if (sidecar.get("metadata_error") or sidecar.get("metadata_conflict")
                or (sidecar.get("review_required") and sidecar.get("selected_capture_time"))):
            continue
        if identity.get("conflict") or any(identity.get(tag) and match.get(tag)
                                           and identity[tag] != match[tag] for tag in ("id", "serial")):
            continue
        sidecar_settings = sidecar.get("capture_settings") or {}
        original_settings = original.get("capture_settings") or {}
        if any(not _same_setting(sidecar_settings.get(field), original_settings.get(field))
               for field in ("exposure", "aperture", "iso")):
            continue
        sidecar_camera = _camera(sidecar)
        if any(sidecar_camera) and sidecar_camera != _camera(original):
            continue
        sidecar_time = _time(sidecar)
        original_time = _time(original)
        if sidecar_time is not None and (original_time is None
                                         or sidecar_time.replace(microsecond=0)
                                         != original_time.replace(microsecond=0)):
            continue
        candidates[key] = ([sidecar], [], True)
        by_sidecar[key] = {key, owner}

    groups_by_key = defaultdict(list)
    for bucket in chain(by_id.values(), by_precision.values(), by_context.values(), by_sidecar.values()):
        if len(bucket) > 1:
            for key in bucket:
                groups_by_key[key].append(bucket)
    visited = set()
    for key in groups_by_key:
        cancel()
        if key in visited:
            continue
        component, pending = {key}, [key]
        expanded = set()
        while pending:
            for bucket in groups_by_key[pending.pop()]:
                if id(bucket) in expanded:
                    continue
                expanded.add(id(bucket))
                others = bucket - component
                component.update(others)
                pending.extend(others)
        visited.update(component)
        if len(component) > 7 or not all(candidates[item][2] for item in component):
            continue
        records = [item for key in sorted(component) for item in candidates[key][0]]
        evidence = [item for key in component for item in candidates[key][1]]
        primary = [item for item in records if _role(item) != "xmp"]
        roles = [_role(item) for item in primary]
        if not roles or len(set(roles)) != len(roles) or len(records) > 7:
            continue
        if len({_normalized(ending(item["relative_path"])) for item in records}) != len(records):
            continue
        if any(not item.get("capture_identity") or item["capture_identity"]["conflict"] for item in evidence):
            continue
        if len({_camera(item) for item in evidence}) != 1 or any(
            not _compatible(item, other) for index, item in enumerate(evidence) for other in evidence[:index]
        ):
            continue
        # A qualified sidecar names a particular primary rather than every
        # file in the family. Require that original, even across folders.
        originals = {_normalized(PurePosixPath(item["relative_path"]).name) for item in primary}
        if any(_role(item) == "xmp" and ending(item["relative_path"]).count(".") > 1
               and _normalized(PurePosixPath(item["relative_path"]).stem) not in originals
               for item in records):
            continue
        anchor = next(key for role in ("raw", "dng", "jpeg") for key in sorted(component)
                      if any(_role(item) == role for item in candidates[key][1]))
        yield anchor, component, records
