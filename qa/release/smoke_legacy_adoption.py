"""Exercise adoption through an authenticated loopback container and two RO mounts."""
import hashlib
import http.cookiejar
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
from zipfile import ZipFile


def smoke(base: str, source: Path, archive: Path) -> None:
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def request(path, *, method="GET", payload=None, expected=200):
        headers = {"Origin": base}
        if method != "GET":
            csrf = next((cookie.value for cookie in cookies if cookie.name == "bibliothekar_csrf"), "")
            headers.update({"Content-Type": "application/json", "X-Bibliothekar-CSRF": csrf})
        body = json.dumps(payload).encode() if payload is not None else None
        with client.open(urllib.request.Request(base + path, body, headers, method=method), timeout=45) as response:
            assert response.status == expected, (path, response.status)
            return response.read()

    def api(path, **kwargs):
        return json.loads(request(path, **kwargs))

    for attempt in range(90):
        try:
            request("/healthz")
            break
        except OSError:
            if attempt == 89:
                raise
            time.sleep(1)

    api("/auth/login", method="POST", payload={"password": os.environ["ADOPTION_SMOKE_PASSWORD"]})
    assert api("/api/settings/storage-health")["ready"]
    checked = api("/api/libraries/check", method="POST", payload={
        "work_root": "", "archive_root": "/main-library", "default_library_id": "smoke",
    })
    assert checked["valid"] and checked["archive_read_only"], checked
    library = api("/api/libraries", method="POST", expected=201, payload={
        "display_name": "Smoke", "work_root": "", "archive_root": "/main-library",
    })["library"]
    assert library["library_id"] == "main"
    assert api("/api/health")["version"] == "1.0.1"
    assert "Bestehende Fotosammlung übernehmen".encode() in request("/legacy-adoption")

    originals = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in source.rglob("*") if path.is_file()}
    assert len(originals) == 2
    job_id = api("/api/legacy-adoption/jobs", method="POST", expected=201, payload={"root": "nas"})["id"]
    job = "/api/legacy-adoption/jobs/" + job_id
    api(job + "/scan", method="POST", expected=202)
    for attempt in range(60):
        state = api(job)
        if state["state"] == "inventoried":
            break
        if state["scan_error"] or attempt == 59:
            raise AssertionError(state)
        time.sleep(1)
    assert state["files"] == 2 and state["families"] == 1
    assert api(job + "/chronology") == [{"period": "2026", "families": 1, "review": 0}]
    for relative, digest in originals.items():
        assert hashlib.sha256((source / relative).read_bytes()).hexdigest() == digest
    assert not list(archive.iterdir())
    draft = api(job + "/draft", method="PUT", payload={"revision": 0, "events": [{
        "name": "Smoke", "start_date": "2026-07-21", "end_date": "2026-07-21",
        "preserve_day_folders": True,
    }]})
    plan = api(job + "/plan", method="POST", payload={"revision": draft["revision"]})
    api(job + "/documents", method="POST")
    command = {"plan_id": plan["id"]}
    api(job + "/confirm", method="POST", payload={**command, "method": "manual", "acknowledged": True})
    for name in ("folders", "documents"):
        with ZipFile(BytesIO(request(job + "/download/" + name))) as package:
            package.extractall(archive)
    for move in api(job + "/moves"):
        original = source / Path(move["source"]).relative_to("/sources/nas")
        target = archive / Path(move["target"]).relative_to("/main-library")
        original.rename(target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == move["sha256"]
    assert api(job + "/verify", method="POST", payload=command)["state"] == "verified"
    for _ in range(2):
        assert api(job + "/finalize", method="POST", payload={"plan_id": plan["id"]})["state"] == "completed"
    print("Legacy adoption container smoke passed with source and archive mounted read-only.")


if __name__ == "__main__":
    smoke(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
