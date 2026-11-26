"""Validate and prepare a bounded byte patch for an oversized Adobe sidecar."""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
import mmap
import os
from pathlib import Path
import re
import subprocess
import sys
from xml.parsers import expat

from app.legacy_adoption_host import ExecutionError, stream_xmp_patch
from app.xmp_raw_filename import CAMERA_RAW_NS, XmpReferenceError, _filename

MAX_STREAM_BYTES = 128 * 1024 * 1024
BLOCK = 1024 * 1024
RESULT_KEY = CAMERA_RAW_NS + " RawFileName"


def _chunks(fd, size):
    for offset in range(0, size, BLOCK):
        yield os.pread(fd, min(BLOCK, size - offset), offset)


def _reference(chunks):
    parser = expat.ParserCreate("UTF-8", namespace_separator=" ")
    values = []
    parts = None
    length = depth = 0
    digest = sha256()

    def reject(*_):
        raise XmpReferenceError("Unsupported or ambiguous XMP structure.")

    def collect(value):
        if values or len(value.encode("utf-8")) > 1024:
            reject()
        values.append(value)

    def start(name, attrs):
        nonlocal parts, depth, length
        depth += 1
        if depth > 128 or parts is not None:
            reject()
        if RESULT_KEY in attrs:
            collect(attrs[RESULT_KEY])
        if name == RESULT_KEY:
            parts, length = [], 0

    def end(name):
        nonlocal parts, depth
        if name == RESULT_KEY:
            collect("".join(parts))
            parts = None
        depth -= 1

    def text(value):
        nonlocal length
        if parts is not None:
            length += len(value)
            if length > 1024:
                reject()
            parts.append(value)

    def xml_encoding(_version, encoding, _standalone):
        if encoding and encoding.casefold() not in {"utf-8", "utf8"}:
            reject()

    parser.StartElementHandler, parser.EndElementHandler, parser.CharacterDataHandler = start, end, text
    parser.StartDoctypeDeclHandler = parser.ExternalEntityRefHandler = reject
    parser.XmlDeclHandler = xml_encoding
    for chunk in chunks:
        digest.update(chunk)
        parser.Parse(chunk, False)
    parser.Parse(b"", True)
    if len(values) != 1:
        reject()
    return _filename(values[0]), digest.hexdigest()


def _encoded(name):
    return escape(name, quote=True).replace("&#x27;", "&apos;").encode("utf-8")


def _proof(fd, size, expected_name, new_name):
    if not 0 < size <= MAX_STREAM_BYTES:
        raise XmpReferenceError("XMP exceeds the supported streaming size.")
    old_name, original_digest = _reference(_chunks(fd, size))
    if old_name.casefold() != expected_name.casefold():
        raise XmpReferenceError("RawFileName differs from the inventory.")
    result = {"original_sha256": original_digest}
    if old_name == new_name:
        return result
    original, replacement = _encoded(old_name), _encoded(_filename(new_name))
    # Require exactly one literal candidate and reparse the modified stream.
    # A comment, unrelated namespace or other token cannot pass both checks.
    literal = re.escape(original)
    field = b":RawFileName"
    token = re.compile(
        field + rb"(?:[ \t\r\n]{0,128}=[ \t\r\n]{0,128}(?P<quote>['\"])(?P<attribute>" + literal + rb")(?P=quote)"
        rb"|>(?P<element>" + literal + rb")</)"
    )
    with mmap.mmap(fd, size, access=mmap.ACCESS_READ) as data:
        offset = None
        cursor = data.find(field)
        while cursor != -1:
            match = token.match(data, cursor)
            if match:
                if offset is not None:
                    raise XmpReferenceError("A unique literal RawFileName token is required.")
                offset = match.start("attribute" if match.group("attribute") is not None else "element")
            cursor = data.find(field, cursor + len(field))
        if offset is None:
            raise XmpReferenceError("A unique literal RawFileName token is required.")
    patch = {"offset": offset, "old": original.hex(), "new": replacement.hex()}
    reread, target_digest = _reference(stream_xmp_patch(fd, size, patch))
    if reread != new_name:
        raise XmpReferenceError("The patched XMP reference differs from the intended value.")
    return {
        **result, "patch": patch,
        "xmp_old_raw_name": old_name, "xmp_new_raw_name": new_name,
        "current_sha256": target_digest, "current_size_bytes": size - len(original) + len(replacement),
    }


def large_xmp_proof(fd, size, expected_name, new_name):
    """Isolate XML parser memory for large attributes and layered masks."""
    # Validate basenames before passing private input to the bounded worker.
    _filename(expected_name)
    _filename(new_name)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.large_xmp", str(fd), str(size), expected_name, new_name],
            pass_fds=(fd,), capture_output=True, check=True, timeout=120,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise XmpReferenceError("Large XMP could not be validated within the supported resource limits.") from error


if __name__ == "__main__":
    # Expat keeps a complete markup token in memory. Restrict the separate
    # process as well as the input size, including for a huge XML attribute.
    if sys.platform == "linux":
        import resource
        limit = 768 * 1024 * 1024
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (min(limit, hard) if hard != resource.RLIM_INFINITY else limit, hard))
    try:
        print(json.dumps(_proof(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4])))
    except (ExecutionError, MemoryError, OSError, ValueError, expat.ExpatError):
        sys.exit(1)
