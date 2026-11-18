"""Promote the exact qualified GHCR manifest without rebuilding it."""
import base64
from hashlib import sha256
import json
import os
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


def main(phase):
    digest = os.environ["RELEASE_DIGEST"]
    version_tag = os.environ["TAG"]
    version = version_tag.removeprefix("v")
    source = os.environ["RELEASE_SOURCE"]
    public = token("pull")
    old = {tag: read(tag, public)[0] for tag in ("1.0.0", "v1.0.0")}
    actual, media_type, data = read(digest, public)
    assert actual == digest == read(f"patch-{version}-{source}", public)[0]

    if phase == "latest":
        assert all(read(tag, public)[0] == digest for tag in (version, version_tag))
        targets = ("latest",)
    else:
        assert phase == "version"
        targets = (version, version_tag)
    writer = token("pull,push", os.environ["GITHUB_ACTOR"] + ":" + os.environ["GH_TOKEN"])
    changes = []
    for tag in targets:
        try:
            current = read(tag, public)[0]
        except HTTPError as error:
            if error.code != 404 or tag == "latest":
                raise
            current = None
        if current == digest:
            continue
        if tag == "latest":
            assert current == old["v1.0.0"], "The stable channel advanced during release preparation."
        else:
            assert current is None, f"Version tag {tag} already has a different digest."
        changes.append(tag)
    for tag in changes:
        with manifest(tag, writer, data=data, media_type=media_type, create_only=tag != "latest") as response:
            assert response.status == 201 and response.headers["Docker-Content-Digest"] == digest
    assert all(read(tag, public)[0] == digest for tag in targets)
    assert {tag: read(tag, public)[0] for tag in old} == old


if __name__ == "__main__":
    main(sys.argv[1])
