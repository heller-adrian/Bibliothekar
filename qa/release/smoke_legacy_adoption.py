"""Exercise adoption through an authenticated loopback container and two RO mounts."""
import hashlib
import http.cookiejar
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from zipfile import ZipFile


def open_request(client, request, *, expected, retry_busy=False):
    attempts = 21 if retry_busy else 1
    for attempt in range(attempts):
        try:
            with client.open(request, timeout=45) as response:
                assert response.status == expected, (request.full_url, response.status)
                return response.read()
        except urllib.error.HTTPError as error:
            with error:
                content = error.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(content)
            except ValueError:
                detail = {}
            transient = (error.code == 409 and isinstance(detail, dict)
                         and detail.get("code") == "legacy_adoption_busy")
            if not retry_busy or not transient or attempt == attempts - 1:
                raise AssertionError(
                    f"{request.method} {request.full_url}: HTTP {error.code}: {content}"
                ) from error
            print("Adoption start is waiting for the current operation to release its lock.", flush=True)
            time.sleep(0.25)


def smoke(container: str, source: Path, archive: Path, appdata: Path) -> None:
    def address():
        return "http://" + subprocess.check_output(["docker", "port", container, "8080/tcp"], text=True).strip()

    base = address()
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def request(path, *, method="GET", payload=None, expected=200):
        headers = {"Origin": base}
        if method != "GET":
            csrf = next((cookie.value for cookie in cookies if cookie.name == "bibliothekar_csrf"), "")
            headers.update({"Content-Type": "application/json", "X-Bibliothekar-CSRF": csrf})
        body = json.dumps(payload).encode() if payload is not None else None
        return open_request(
            client, urllib.request.Request(base + path, body, headers, method=method),
            expected=expected, retry_busy=method == "POST" and path == "/api/legacy-adoption/jobs",
        )

    def api(path, **kwargs):
        return json.loads(request(path, **kwargs))

    def wait_ready():
        for attempt in range(90):
            try:
                request("/healthz")
                break
            except OSError:
                if attempt == 89:
                    raise
                time.sleep(1)

    def login():
        api("/auth/login", method="POST", payload={"password": os.environ["ADOPTION_SMOKE_PASSWORD"]})

    wait_ready()
    login()
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

    for method, day in (("manual", "21"), ("script", "22")):
        host_source = source / method
        originals = {str(path.relative_to(host_source)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in host_source.rglob("*") if path.is_file()}
        assert len(originals) == 2
        job_id = api("/api/legacy-adoption/jobs", method="POST", expected=201,
                     payload={"root": "nas", "relative": method})["id"]
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
        assert state["dataset"]["dataset"].endswith("/media")
        assert api(job + "/chronology") == [{"period": "2026", "families": 1, "review": 0}]
        for relative, digest in originals.items():
            assert hashlib.sha256((host_source / relative).read_bytes()).hexdigest() == digest
        if method == "manual":
            assert not list(archive.iterdir())
        name = "Smoke " + method
        draft = api(job + "/draft", method="PUT", payload={"revision": 0, "events": [{
            "name": name, "start_date": "2026-07-" + day, "end_date": "2026-07-" + day,
            "preserve_day_folders": True,
        }]})
        if method == "script":
            subprocess.run(["docker", "restart", container], check=True)
            base = address()
            wait_ready()
            login()
            resumed = api(job)
            assert resumed["draft_revision"] == draft["revision"] and resumed["draft"]["events"][0]["name"] == name
            assert b'id="safety"' in request("/")
            assert resumed["id"] == job_id
        plan = api(job + "/plan", method="POST", payload={"revision": draft["revision"]})
        api(job + "/documents", method="POST")
        command = {"plan_id": plan["id"]}
        confirmation = {**command, "method": method, "acknowledged": True}
        if method == "script":
            probe = api(job + "/script/probe", method="POST", payload={
                **command, "appdata": str(appdata), "source": str(host_source), "archive": str(archive),
            })
            subprocess.run(["sudo", "-n", "/bin/bash", "-c", probe["command"]], check=True)
            assert api(job + "/script/probe")["verified"]
            confirmation["probe_sha256"] = probe["sha256"]
        api(job + "/confirm", method="POST", payload=confirmation)
        moves = api(job + "/moves")
        if method == "manual":
            for artifact in ("folders", "documents"):
                with ZipFile(BytesIO(request(job + "/download/" + artifact))) as package:
                    package.extractall(archive)
            for move in moves:
                original = source / Path(move["source"]).relative_to("/sources/nas")
                target = archive / Path(move["target"]).relative_to("/main-library")
                original.rename(target)
        else:
            shell = api(job + "/script/release", method="POST", payload=command)["command"]
            subprocess.run(["sudo", "-n", "/bin/bash", "-c", shell], check=True)
            assert api(job + "/script")["status"]["state"] == "completed"
        for move in moves:
            target = archive / Path(move["target"]).relative_to("/main-library")
            assert hashlib.sha256(target.read_bytes()).hexdigest() == move["sha256"]
        assert api(job + "/verify", method="POST", payload=command)["state"] == "verified"
        for _ in range(2):
            assert api(job + "/finalize", method="POST", payload=command)["state"] == "completed"
    print("Manual and scripted adoption passed with native ZFS and separate read-only container mounts.")


if __name__ == "__main__":
    smoke(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
