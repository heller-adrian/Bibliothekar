"""Promote the exact qualified GHCR manifest without rebuilding it."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REGISTRY = "https://ghcr.io"
PACKAGE = "heller-adrian/bibliothekar"
ACCEPT = ", ".join("application/vnd." + value for value in (
    "oci.image.index.v1+json", "oci.image.manifest.v1+json",
    "docker.distribution.manifest.list.v2+json", "docker.distribution.manifest.v2+json",
))


def token(scope, credentials=None):
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{PACKAGE}:{scope}"})
    request = Request(f"{REGISTRY}/token?{query}")
    if credentials:
        request.add_unredirected_header("Authorization", "Basic " + base64.b64encode(credentials.encode()).decode())
    with urlopen(request, timeout=20) as response:
        return json.load(response)["token"]


def manifest(ref, bearer, *, data=None, media_type=None, create_only=False):
    request = Request(f"{REGISTRY}/v2/{PACKAGE}/manifests/{ref}", data=data, headers={"Accept": ACCEPT},
                      method="GET" if data is None else "PUT")
    request.add_unredirected_header("Authorization", "Bearer " + bearer)
    if data is not None:
        request.add_header("Content-Type", media_type)
    if create_only:
        request.add_header("If-None-Match", "*")
    return urlopen(request, timeout=20)


def read(ref, bearer):
    with manifest(ref, bearer) as response:
        data = response.read()
        actual = "sha256:" + sha256(data).hexdigest()
        assert response.headers["Docker-Content-Digest"] == actual
        return actual, response.headers.get_content_type(), data


def read_optional(ref, bearer):
    try:
        return read(ref, bearer)[0]
    except HTTPError as error:
        if error.code == 404 and any(
            item.get("code") == "MANIFEST_UNKNOWN" for item in json.load(error)["errors"]
        ):
            return None
        raise


def main(phase):
    digest = os.environ["RELEASE_DIGEST"]
    version_tag = os.environ["TAG"]
    version = version_tag.removeprefix("v")
    source = os.environ["RELEASE_SOURCE"]
    candidate = os.environ["CANDIDATE_TAG"]
    previous = os.environ["PREVIOUS_TAG"]
    previous_digest = os.environ["PREVIOUS_DIGEST"]
    evidence = Path(os.environ["RELEASE_EVIDENCE"])
    assert phase in {"check", "version", "latest"}
    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version_tag)
    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", previous) and previous != version_tag
    assert re.fullmatch(re.escape(version_tag) + r"-rc\.[0-9]+", candidate)
    assert re.fullmatch(r"[0-9a-f]{40}", source)
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in (digest, previous_digest))
    public = token("pull")
    actual, media_type, data = read(digest, public)
    assert actual == digest == read(f"patch-{version}-{source}", public)[0]
    protected_tags = (candidate, previous, previous.removeprefix("v"))
    version_tags = (version, version_tag)
    tags = (*protected_tags, *version_tags, "latest")

    def observe():
        return {tag: read_optional(tag, public) for tag in tags}

    current = observe()
    assert current[candidate] == digest, "The release candidate does not point to the qualified digest."
    assert current[previous] == previous_digest, "The previous stable version no longer matches its evidence."
    assert current["latest"] in {previous_digest, digest}, "The stable channel advanced during release preparation."
    for tag in version_tags:
        assert current[tag] in {None, digest}, f"Version tag {tag} already has a different digest."
    if current["latest"] == digest or phase == "latest":
        assert all(current[tag] == digest for tag in version_tags), "Both version tags must be qualified first."

    snapshot = evidence / "registry-before.json"
    if phase == "check":
        snapshot.write_text(json.dumps(current, indent=2) + "\n")
        return

    baseline = json.loads(snapshot.read_text())
    assert all(current[tag] == baseline[tag] for tag in (*protected_tags, "latest")), "The registry changed since preflight."
    targets = ("latest",) if phase == "latest" else version_tags
    pending = [tag for tag in targets if current[tag] != digest]
    if pending:
        writer = token("pull,push", os.environ["GITHUB_ACTOR"] + ":" + os.environ["GH_TOKEN"])
        for tag in pending:
            assert read_optional(tag, public) == current[tag], f"Tag {tag} changed before promotion."
            with manifest(tag, writer, data=data, media_type=media_type, create_only=tag != "latest") as response:
                assert response.status == 201 and response.headers["Docker-Content-Digest"] == digest
    after = observe()
    assert all(after[tag] == digest for tag in targets)
    assert all(after[tag] == current[tag] for tag in tags if tag not in targets)
    if phase == "latest":
        (evidence / "promotion.json").write_text(json.dumps({
            "source": source, "main": os.environ["GITHUB_SHA"], "digest": digest,
            "qa_run": os.environ["RELEASE_QA_RUN"], "image_run": os.environ["QUALIFIED_IMAGE_RUN"],
            "promotion_run": os.environ["GITHUB_RUN_ID"], "before": baseline, "after": after,
        }, indent=2) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
