"""Conservative capture matching for media discovered in separate directories."""
from collections import defaultdict
from datetime import datetime, timezone
from itertools import chain
from fractions import Fraction
from pathlib import PurePosixPath
import re
import unicodedata

from app.filename_collisions import has_capture_fraction


IDENTITY_TAGS = ("ImageUniqueID", "BodySerialNumber", "OriginalRawFileName")
IDENTITY_VERSION = 5


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
        "sidecar_raw": _normalized(metadata.get("XMP:XMP-crs:RawFileName")),
        "document": _normalized(metadata.get("XMP:XMP-xmpMM:DocumentID")),
        "original_document": _normalized(metadata.get("XMP:XMP-xmpMM:OriginalDocumentID")),
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


def _compatible_time(first, second, left, right):
    if left is None or right is None or left.replace(microsecond=0) != right.replace(microsecond=0):
        return False
    return (left == right or not all(
        has_capture_fraction(item["selected_capture_time"]) for item in (first, second)
    ))


def _compatible(first, second):
    a, b = first["capture_identity"], second["capture_identity"]
    if a["id"] and b["id"] and a["id"] != b["id"]:
        return False
    if a["serial"] and b["serial"] and a["serial"] != b["serial"]:
        return False
    left, right = _time(first), _time(second)
    if not _compatible_time(first, second, left, right):
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


def split_family_groups(groups, *, ending, cancel=lambda: None, preserve_xmp_versions=False):
    """Yield only sets backed by unambiguous, mutually compatible evidence.

    Each input supplies its local family key, its member records and eligibility.
    False eligibility still contributes to ambiguity (e.g. already owned files).
    """
    by_id, by_precision, by_context = defaultdict(set), defaultdict(set), defaultdict(set)
    candidates = {}
    primary_by_name = defaultdict(set)
    primary_by_stem = defaultdict(set)
    standalone_sidecars = {}
    dng_by_document = defaultdict(list)
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
            primary_by_stem[_normalized(PurePosixPath(primary["relative_path"]).stem)].add(key)
            lineage = (primary.get("capture_identity") or {}).get("original_document")
            if preserve_xmp_versions and _role(primary) == "dng" and lineage:
                dng_by_document[lineage].append((key, primary))
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
                stem = _normalized(PurePosixPath(key).name)
                settings = item.get("capture_settings") or {}
                # Keep coarse candidates available for a proven sidecar, but
                # never connect primaries on a model/stem/whole second alone.
                has_proof = True
                if identity["serial"] and has_capture_fraction(item["selected_capture_time"]):
                    by_precision[(camera, identity["serial"], stem, instant)].add(key)
                if all(settings.get(field) not in (None, "") for field in ("exposure", "aperture", "iso")):
                    by_context[(camera, stem, instant.replace(microsecond=0))].add(key)
        if has_proof:
            candidates[key] = (members, evidence, usable)

    by_sidecar = {}
    by_lineage = []
    for key, sidecar in standalone_sidecars.items():
        cancel()
        path = PurePosixPath(sidecar["relative_path"])
        if path.suffix.casefold() != ".xmp":
            continue
        original_name = _normalized(path.stem)
        identity = sidecar.get("capture_identity") or {}
        raw_hint = identity.get("sidecar_raw") or ""
        named_extension = PurePosixPath(original_name).suffix.casefold()
        exact_named = named_extension in {
            ".raf", ".nef", ".cr2", ".cr3", ".arw", ".orf", ".rw2",
            ".dng", ".jpg", ".jpeg",
        }
        # An explicit RAW filename is authoritative about the *name*, not
        # globally unique capture identity. Resolve it against the entire
        # inventory and require a single, corroborated capture.
        if raw_hint:
            if exact_named and original_name != raw_hint:
                continue
            owners = primary_by_name.get(raw_hint, set())
        elif exact_named:
            owners = primary_by_name.get(original_name, set())
        else:
            # Adobe's common DSCF1234.xmp sidecar has no extension hint.
            # Only corroborating camera AND capture time can qualify it.
            owners = primary_by_stem.get(original_name, set())

        if (sidecar.get("metadata_error") or sidecar.get("metadata_conflict")
                or identity.get("conflict")):
            continue
        sidecar_camera = _camera(sidecar)
        # XMP CreateDate can describe a later edit or sidecar creation;
        # only DateTimeOriginal is an independently usable capture instant.
        sidecar_source = str(sidecar.get("selected_capture_source") or "")
        sidecar_time = (_time(sidecar) if sidecar_source.endswith(":DateTimeOriginal")
                        else None)
        if not raw_hint and not exact_named:
            if sidecar_time is None or not all(sidecar_camera):
                continue
        if sidecar.get("review_required") and sidecar.get("selected_capture_time"):
            continue

        qualified = {}
        for owner in owners:
            if owner not in candidates or not candidates[owner][2]:
                continue
            primaries = candidates[owner][0]
            exact = [
                item for item in primaries
                if _normalized(PurePosixPath(item["relative_path"]).name) == raw_hint
            ] if raw_hint else [
                item for item in primaries
                if (_normalized(PurePosixPath(item["relative_path"]).name) == original_name
                    if exact_named else
                    _normalized(PurePosixPath(item["relative_path"]).stem) == original_name)
            ]
            for original in exact:
                if raw_hint and _role(original) not in {"raw", "dng"}:
                    continue
                match = original.get("capture_identity") or {}
                if any(identity.get(tag) and match.get(tag)
                       and identity[tag] != match[tag] for tag in ("id", "serial")):
                    continue
                if any(sidecar_camera) and sidecar_camera != _camera(original):
                    continue
                original_time = _time(original)
                if sidecar_time is not None:
                    if not _compatible_time(sidecar, original, sidecar_time, original_time):
                        continue
                elif not (identity.get("id") and identity["id"] == match.get("id")
                          or sidecar_camera == _camera(original) and all(sidecar_camera)
                          and identity.get("serial") and identity["serial"] == match.get("serial")):
                    continue
                if not all(sidecar_camera) and not (identity.get("id") and identity["id"] == match.get("id")):
                    continue
                if not raw_hint:
                    # Without an explicit RAW reference, original capture
                    # settings provide an additional conservative fence.
                    settings = sidecar.get("capture_settings") or {}
                    original_settings = original.get("capture_settings") or {}
                    if any(not _same_setting(settings.get(field), original_settings.get(field))
                           for field in ("exposure", "aperture", "iso")):
                        continue
                qualified[(owner, original["relative_path"])] = original

        if not qualified:
            continue
        # Two RAW files can reuse the same name, even in different folders.
        # Never choose arbitrarily; leave ambiguous cases for review.
        unique_owners = {owner for owner, _ in qualified}
        if raw_hint or exact_named:
            if len(qualified) != 1:
                continue
        else:
            raw_candidates = {
                (owner, name) for (owner, name), item in qualified.items()
                if _role(item) == "raw"
            }
            if len(raw_candidates) > 1 or (not raw_candidates and len(unique_owners) != 1):
                continue
            # Plain XMP can bind to one RAW, but cannot itself prove a
            # relationship between that RAW and a separately stored JPEG.
            if raw_candidates:
                unique_owners = {owner for owner, _ in raw_candidates}
        candidates[key] = ([sidecar], [], True)
        by_sidecar[key] = {key, *unique_owners}
        if preserve_xmp_versions and raw_hint:
            ((owner, _), original), = qualified.items()
            lineage = identity.get("original_document") or identity.get("document")
            derived = [
                (dng_key, dng) for dng_key, dng in dng_by_document.get(lineage, ())
                if _camera(dng) == _camera(original) and dng.get("capture_identity")
                and not dng["capture_identity"].get("conflict")
                and _compatible(dng, original)
            ]
            # A document lineage supplements an already proven RAW binding.
            # An ambiguous lineage must not choose between multiple DNGs.
            if _role(original) == "raw" and len(derived) == 1 and derived[0][0] in candidates:
                by_lineage.append({owner, derived[0][0]})

    groups_by_key = defaultdict(list)
    for bucket in chain(by_id.values(), by_precision.values(), by_context.values(), by_sidecar.values(), by_lineage):
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
        if (not preserve_xmp_versions and len(component) > 7) or not all(candidates[item][2] for item in component):
            continue
        records = [item for key in sorted(component) for item in candidates[key][0]]
        evidence = [item for key in component for item in candidates[key][1]]
        primary = [item for item in records if _role(item) != "xmp"]
        roles = [_role(item) for item in primary]
        if not roles or len(set(roles)) != len(roles) or (not preserve_xmp_versions and len(records) > 7):
            continue
        ending_buckets = defaultdict(list)
        for item in records:
            ending_buckets[_normalized(ending(item["relative_path"]))].append(item)
        if any(len(items) > 1 and not (
            preserve_xmp_versions and all(
                _role(item) == "xmp" and (item.get("capture_identity") or {}).get("sidecar_raw")
                for item in items
            )
        ) for items in ending_buckets.values()):
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
        masters = [_normalized(PurePosixPath(item["relative_path"]).name) for item in primary
                   if _role(item) in {"raw", "dng"}]
        if any(masters.count(hint) != 1 for item in records if _role(item) == "xmp"
               and (hint := (item.get("capture_identity") or {}).get("sidecar_raw"))):
            continue
        if any(_role(item) == "xmp" and ending(item["relative_path"]).count(".") > 1
               and _normalized(PurePosixPath(item["relative_path"]).stem) not in originals
               for item in records):
            continue
        anchor = next(key for role in ("raw", "dng", "jpeg") for key in sorted(component)
                      if any(_role(item) == role for item in candidates[key][1]))
        yield anchor, component, records
