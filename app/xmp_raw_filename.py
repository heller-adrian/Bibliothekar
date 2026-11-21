"""Conservative, byte-preserving Adobe Camera Raw sidecar reference rewrite.

This module is a pure transformation. It never opens or changes media files.
It does not authorize rewriting during adoption: the host executor still needs
separate old/new checksum proofs, a recoverable original and crash-safe journaling.
"""
from __future__ import annotations

from html import escape as xml_escape
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET


CAMERA_RAW_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
_RAW_KEY = "{" + CAMERA_RAW_NS + "}RawFileName"
_ATTR = re.compile(
    rb"(?P<qname>(?P<prefix>[A-Za-z_][\w.-]*):RawFileName)"
    rb"(?P<separator>\s*=\s*)(?P<quote>[\x22\x27])"
    rb"(?P<content>[^\x22\x27<>]*)(?P=quote)"
)
_ELEMENT = re.compile(
    rb"<(?P<qname>(?P<prefix>[A-Za-z_][\w.-]*):RawFileName)>"
    rb"(?P<content>[^<>]*)</(?P=qname)>"
)
_ENCODING = re.compile(rb"<\?xml\b[^>]*\bencoding\s*=\s*[\x22\x27]([^\x22\x27]+)", re.I)


class XmpReferenceError(ValueError):
    """An XMP reference could not be rewritten without ambiguity."""


def _filename(value: str) -> str:
    if (not isinstance(value, str) or not value
            or value in {".", ".."} or "\x00" in value
            or "/" in value or "\\" in value
            or PurePosixPath(value).name != value):
        raise XmpReferenceError("Only individual RAW basenames may be rewritten.")
    return value


def _raw_values(payload: bytes) -> list[str]:
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, UnicodeError, ValueError) as exc:
        raise XmpReferenceError("Sidecar is not parseable XML.") from exc
    values = []
    for element in root.iter():
        for key, value in element.attrib.items():
            if key == _RAW_KEY:
                values.append(value)
        if element.tag == _RAW_KEY:
            values.append(element.text or "")
    return values


def rewrite_raw_filename(payload: bytes, old_name: str, new_name: str) -> bytes:
    """Rewrite exactly one proven XMP-crs:RawFileName, nothing else.

    Fail closed when the XML, namespace, representation, or field is ambiguous.
    Return a new bytes value; leave the input untouched. An unchanged mapping
    is idempotent, but does not authorize an external in-place file write.
    """
    old_name = _filename(old_name)
    new_name = _filename(new_name)
    if not isinstance(payload, bytes):
        raise XmpReferenceError("XMP payload must be bytes.")
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise XmpReferenceError("UTF-16 XMP requires a separate qualified transform.")
    declared = _ENCODING.search(payload[:256])
    if declared and declared.group(1).lower() not in {b"utf-8", b"utf8"}:
        raise XmpReferenceError("Only UTF-8 XMP may be rewritten byte-preservingly.")
    if _raw_values(payload) != [old_name]:
        raise XmpReferenceError("RawFileName is missing, different or ambiguous.")
    if old_name == new_name:
        return payload

    old_encoded = xml_escape(old_name, quote=True).replace("&#x27;", "&apos;").encode("utf-8")
    new_encoded = xml_escape(new_name, quote=True).replace("&#x27;", "&apos;").encode("utf-8")
    # Do not normalize or reserialize Adobe's edit history, ordering, or bytes.
    # Both XML attribute and element forms are supported, but only when one
    # literal ASCII/UTF-8 representation is present in a RawFileName field.
    matches = []
    for pattern in (_ATTR, _ELEMENT):
        for match in pattern.finditer(payload):
            if match.group("content") == old_encoded:
                matches.append(match)
    if len(matches) != 1:
        raise XmpReferenceError("Unambiguous literal RawFileName token was not found.")
    match = matches[0]
    output = payload[:match.start("content")] + new_encoded + payload[match.end("content"):]
    if _raw_values(output) != [new_name]:
        raise XmpReferenceError("The rewritten reference failed XML verification.")
    return output
