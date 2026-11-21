"""Pure XMP edit tests; no source/archived media is modified."""
import hashlib

import pytest

from app.xmp_raw_filename import XmpReferenceError, rewrite_raw_filename


PREFIX = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
)
END = b'</rdf:RDF></x:xmpmeta>\n<?xpacket end="w"?>'
CRS = b'xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'


def raw_attribute(value=b"DSCF2915.RAF"):
    return (PREFIX + b'<rdf:Description ' + CRS +
            b' crs:RawFileName="' + value +
            b'" crs:Exposure2012="+0.50" xmlns:dc="http://purl.org/dc/elements/1.1/" dc:title="Edited"/>'
            + END)


def test_rewrites_only_explicit_reference_and_preserves_all_other_edit_bytes():
    original = raw_attribute()
    digest = hashlib.sha256(original).hexdigest()
    renamed = rewrite_raw_filename(original, "DSCF2915.RAF",
                                   "20250416_193726_Fuji-X-H2S.RAF")
    assert renamed == original.replace(
        b'crs:RawFileName="DSCF2915.RAF"',
        b'crs:RawFileName="20250416_193726_Fuji-X-H2S.RAF"')
    assert b'crs:Exposure2012="+0.50"' in renamed
    assert b'dc:title="Edited"' in renamed
    assert hashlib.sha256(original).hexdigest() == digest
    assert original != renamed
    assert rewrite_raw_filename(renamed, "20250416_193726_Fuji-X-H2S.RAF",
                                "DSCF2915.RAF") == original


def test_child_element_form_with_persisted_history_is_byte_preserved():
    source = (PREFIX + b'<rdf:Description ' + CRS +
              b'><crs:RawFileName>DSCF2915.RAF</crs:RawFileName>'
              b'<crs:Exposure2012>-0.33</crs:Exposure2012></rdf:Description>' + END)
    result = rewrite_raw_filename(source, "DSCF2915.RAF", "New.RAF")
    assert result == source.replace(b">DSCF2915.RAF<", b">New.RAF<")


def test_namespace_alias_does_not_matter_if_it_is_true_camera_raw_namespace():
    content = PREFIX + (
        b'<rdf:Description xmlns:camera="http://ns.adobe.com/camera-raw-settings/1.0/"'
        b' camera:RawFileName="DSCF2915.RAF"/>'
    ) + END
    assert b'camera:RawFileName="New.RAF"' in rewrite_raw_filename(
        content, "DSCF2915.RAF", "New.RAF")


@pytest.mark.parametrize("payload", [
    b'<root/>',
    raw_attribute(b"WRONG.RAF"),
    raw_attribute(b"DSCF2915.RAF").replace(b'crs:RawFileName="', b'crs:RawFileName="x'),
    raw_attribute(b"DSCF2915.RAF").replace(b'crs:RawFileName="', b'other:RawFileName="'),
    raw_attribute(b"DSCF2915.RAF").replace(
        b'crs:RawFileName="DSCF2915.RAF"',
        b'crs:RawFileName="DSCF2915.RAF" xmlns:c2="http://ns.adobe.com/camera-raw-settings/1.0/" c2:RawFileName="DSCF2915.RAF"'),
    b'<?xml version="1.0" encoding="UTF-16"?><root/>',
    b"\xff\xfe<\x00x\x00m\x00l\x00",
])
def test_invalid_or_ambiguous_metadata_fails_closed(payload):
    with pytest.raises(XmpReferenceError):
        rewrite_raw_filename(payload, "DSCF2915.RAF", "New.RAF")


@pytest.mark.parametrize("name", ["../new.RAF", "folder/new.RAF", "folder\\new.RAF", "", "."])
def test_rejects_non_basename_target(name):
    with pytest.raises(XmpReferenceError):
        rewrite_raw_filename(raw_attribute(), "DSCF2915.RAF", name)


def test_no_change_is_idempotent_when_existing_reference_matches():
    xmp = raw_attribute()
    assert rewrite_raw_filename(xmp, "DSCF2915.RAF", "DSCF2915.RAF") == xmp


def test_rewrite_does_not_follow_duplicate_filename_elsewhere():
    xmp = (PREFIX + b'<rdf:Description ' + CRS
           + b' crs:RawFileName="DSCF2915.RAF"'
           + b' xmlns:dc="http://purl.org/dc/elements/1.1/"'
           + b' dc:description="This photograph used to be called DSCF2915.RAF"/>'
           + END)
    changed = rewrite_raw_filename(xmp, "DSCF2915.RAF", "Renamed.RAF")
    assert b'crs:RawFileName="Renamed.RAF"' in changed
    assert b'dc:description="This photograph used to be called DSCF2915.RAF"' in changed
