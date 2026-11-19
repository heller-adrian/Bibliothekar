"""Promote the exact qualified 1.1.1 RC3 OCI manifest; never rebuild or modify old tags."""
from hashlib import sha256
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import base64
import json
import os
import sys

REGISTRY = "https://ghcr.io"
PACKAGE = "heller-adrian/bibliothekar"
ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))

def token(scope, credentials=None):
    request = Request(REGISTRY + "/token?" + urlencode({
        "service": "ghcr.io",
        "scope": f"repository:{PACKAGE}:{scope}",
    }))
    if credentials is not None:
        basic = base64.b64encode(credentials.encode()).decode()
        request.add_unredirected_header("Authorization", "Basic " + basic)
    with urlopen(request, timeout=30) as response:
        return json.load(response)["token"]

def manifest(ref, bearer, *, content=None, media_type=None):
    request = Request(
        f"{REGISTRY}/v2/{PACKAGE}/manifests/{ref}",
        data=content,
        method="PUT" if content is not None else "GET",
        headers={"Accept": ACCEPT},
    )
    request.add_unredirected_header("Authorization", "Bearer " + bearer)
    if content is not None:
        request.add_header("Content-Type", media_type)
        request.add_header("If-None-Match", "*")
    return urlopen(request, timeout=30)

def read(ref, bearer):
    with manifest(ref, bearer) as response:
        content = response.read()
        digest = "sha256:" + sha256(content).hexdigest()
        assert response.headers["Docker-Content-Digest"] == digest, (ref, digest)
        return digest, response.headers.get_content_type(), content

def run(phase):
    source = os.environ["SOURCE"]
    qualified = os.environ["QUALIFIED_DIGEST"]
    assert qualified.startswith("sha256:") and len(qualified) == 71
    public = token("pull")
    frozen = ("1.0.0", "v1.0.0", "1.1.0", "v1.1.0",
              "v1.1.1-rc.1", "v1.1.1-rc.2", "v1.1.1-rc.3")
    before = {name: read(name, public)[0] for name in frozen}
    current_latest = read("latest", public)[0]
    assert current_latest in {before["v1.1.0"], qualified}, (
        "Latest is neither the previous stable nor this qualified release",
        current_latest,
    )
    assert before["1.1.0"] == before["v1.1.0"]
    assert before["v1.1.1-rc.3"] == qualified
    digest, media_type, content = read(qualified, public)
    assert digest == qualified
    assert read("patch-1.1.1-" + source, public)[0] == qualified

    if phase == "version":
        assert current_latest == before["v1.1.0"], (
            "Stable channel unexpectedly advanced before release",
            current_latest,
        )
        targets = ("1.1.1", "v1.1.1")
    elif phase == "latest":
        assert read("1.1.1", public)[0] == qualified
        assert read("v1.1.1", public)[0] == qualified
        targets = ("latest",)
    else:
        raise ValueError("Expected version or latest phase")

    writer = token(
        "pull,push",
        os.environ["REGISTRY_ACTOR"] + ":" + os.environ["REGISTRY_CREDENTIAL"],
    )
    for tag in targets:
        try:
            existing = read(tag, public)[0]
        except HTTPError as error:
            if error.code != 404:
                raise
            existing = None
        if existing == qualified:
            continue
        if tag == "latest":
            assert existing == before["v1.1.0"], (
                "latest shifted during promotion",
                existing,
            )
        else:
            assert existing is None, f"Immutable version tag exists with unexpected digest: {tag}"
        with manifest(tag, writer, content=content, media_type=media_type) as response:
            assert response.status == 201
            assert response.headers["Docker-Content-Digest"] == qualified
        assert read(tag, public)[0] == qualified, tag

    assert all(read(tag, public)[0] == qualified for tag in targets)
    assert {tag: read(tag, public)[0] for tag in frozen} == before
    print(f"Stable promotion {phase}: {PACKAGE} -> {qualified}")

if __name__ == "__main__":
    run(sys.argv[1])
