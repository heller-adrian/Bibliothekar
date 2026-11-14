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
import urllib.parse
import urllib.request
from zipfile import ZipFile


def startup_recovery_only(health):
    if not isinstance(health, dict):
        return False
    issues = health.get("issues")
    reservations = health.get("reservations")
    return (
        isinstance(issues, list)
        and isinstance(reservations, list)
        and all(isinstance(issue, dict)
                and issue.get("phase") == "recovery_in_progress"
                and issue.get("scope") == "workspace" for issue in issues)
        and all(isinstance(record, dict) and record.get("live") is True
                for record in reservations)
        and bool(health.get("writes_allowed") is True or issues)
    )


def open_request(client, request, *, expected, recovery_status=None):
    # These POSTs acquire the exclusive adoption lock before calling the endpoint.
    retry_busy = request.method == "POST" and urllib.parse.urlsplit(request.full_url).path in {
        "/api/libraries", "/api/setup/adoption", "/api/legacy-adoption/jobs",
    }
    attempts = 121 if recovery_status else (21 if retry_busy else 1)
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
            if error.code == expected and not (retry_busy and transient):
                return content.encode("utf-8")
            recovery = False
            if recovery_status and error.code == 409 and isinstance(detail, dict):
                message = detail.get("detail")
                if message == "operation_recovery_required":
                    operations = detail.get("operations")
                    recovery = (detail.get("storage_state") == "READY"
                                and startup_recovery_only(operations)
                                and operations.get("writes_allowed") is False
                                and bool(operations["issues"]))
                elif isinstance(message, str):
                    recovery = (message.startswith("operation_recovery_required:")
                                and "'phase': 'recovery_in_progress', 'scope': 'workspace'" in message)
            if not ((retry_busy and transient) or recovery) or attempt == attempts - 1:
                raise AssertionError(
                    f"{request.method} {request.full_url}: HTTP {error.code}: {content}"
                ) from error
            if recovery:
                status = recovery_status()
                assert (status["ready"] is True and not status.get("startup_error")
                        and startup_recovery_only(status["operation_health"])), status
                print("Repeated finalization is waiting for startup write admission.", flush=True)
            else:
                print(f"{request.method} {request.selector} is waiting for the adoption lock.", flush=True)
            time.sleep(0.25)


def smoke(container: str, source: Path, archive: Path, appdata: Path, method: str) -> None:
    def address():
        return "http://" + subprocess.check_output(["docker", "port", container, "8080/tcp"], text=True).strip()

    base = address()
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def request(path, *, method="GET", payload=None, expected=200, repeat_finalize=False):
        headers = {"Origin": base}
        if method != "GET":
            csrf = next((cookie.value for cookie in cookies if cookie.name == "bibliothekar_csrf"), "")
            headers.update({"Content-Type": "application/json", "X-Bibliothekar-CSRF": csrf})
        body = json.dumps(payload).encode() if payload is not None else None
        return open_request(
            client, urllib.request.Request(base + path, body, headers, method=method),
            expected=expected,
            recovery_status=(lambda: api("/api/settings/storage-health")) if repeat_finalize else None,
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
    choice = request("/workspace")
    assert "Hast du eine bestehende Fotosammlung?".encode() in choice
    assert b'id="bk-settings-dialog"' not in choice
    assert api("/api/jobs", expected=409)["code"] == "initial_setup_required"
    assert api("/api/settings/event-folder-layout", expected=409)["code"] == "initial_setup_required"
    if method == "skip":
        assert api("/api/setup/adoption", method="POST", payload={"decision": "skipped"}) == {"next": "/"}
        assert b'id="bk-settings-dialog"' in request("/")
        assert api("/api/legacy-adoption/jobs", method="POST", expected=409, payload={"root": "nas"})[
            "code"
        ] == "legacy_adoption_inactive"
        print("Explicit skip released normal access.")
        return
    assert api("/api/setup/adoption", method="POST", payload={"decision": "adopting"}) == {"next": "/legacy-adoption"}
    assert "Bestehende Fotosammlung übernehmen".encode() in request("/legacy-adoption")
    sources = api("/api/legacy-adoption/sources")
    assert sources["preferred"] == "nas"
    assert len(sources["roots"]) == 1
    nas = sources["roots"][0]
    assert nas["key"] == "nas" and nas["read_only"] and nas["dataset"].endswith("/media")
    if method == "review":
        originals = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()}
        job_id = api("/api/legacy-adoption/jobs", method="POST", expected=201, payload={"root": "nas"})["id"]
        job = "/api/legacy-adoption/jobs/" + job_id
        api(job + "/scan", method="POST", expected=202)
        for attempt in range(60):
            state = api(job)
            if state["state"] == "inventoried" and not state["scan_running"]:
                break
            if state["scan_error"] or attempt == 59:
                raise AssertionError(state)
            time.sleep(1)
        assert state["review_count"] == 1 and state["files"] == 3
        assert api(job + "/review/selection") == ["undated"]
        api(job + "/review/batch", method="POST", expected=202, payload={"family_keys": ["undated"]})
        for attempt in range(60):
            result = api(job + "/review/batch")
            if not result["running"]:
                break
            if attempt == 59:
                raise AssertionError(result)
            time.sleep(1)
        assert result == {"total": 1, "pending": 0, "copied": 1, "failed": 0, "running": False}, result
        assert not api(job + "/review/selection")
        api(job, method="DELETE")
        api("/api/setup/adoption", method="POST", payload={"decision": "skipped"})
        working = api("/api/metadata-correction/scan?area=general")["files"]
        assert {file["filename"] for file in working} == set(originals)
        assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()} == originals
        assert not list(archive.iterdir())
        print("Review batch preserved a complete RAW/JPEG/XMP family and read-only originals on native ZFS.")
        return
    folder = api("/api/legacy-adoption/source?root=nas&relative=first")
    assert folder["read_only"] and folder["dataset"] == nas["dataset"]
    assert folder["folders"] == ["old-folders"]
    day = "21" if method == "manual" else "22"
    def adopt(execution, relative, existing_event=None, *, rollback=False):
        nonlocal base
        host_source = source / relative
        originals = {str(path.relative_to(host_source)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in host_source.rglob("*") if path.is_file()}
        assert len(originals) == 2
        route = "/api/legacy-adoption/jobs" + ("?mode=library" if existing_event else "")
        job_id = api(route, method="POST", expected=201, payload={"root": "nas", "relative": relative})["id"]
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
        date = "2026-07-" + day
        if existing_event:
            matches = api(job + "/events?day=" + date)
            assert [event["id"] for event in matches] == [existing_event["id"]]
            definition = {"existing_id": existing_event["id"]}
        else:
            assert not list(archive.iterdir())
            definition = {"name": "Smoke " + execution, "start_date": date, "end_date": date,
                          "start_time": "12:00", "end_time": "15:00", "preserve_day_folders": True}
        draft = api(job + "/draft", method="PUT", payload={"revision": 0, "events": [definition]})
        if execution == "script":
            subprocess.run(["docker", "restart", container], check=True)
            base = address()
            wait_ready()
            login()
            resumed = api(job)
            assert resumed["draft_revision"] == draft["revision"] and all(resumed["draft"]["events"][0][key] == value for key, value in definition.items())
            assert b'id="safety"' in request("/")
            assert resumed["id"] == job_id
        plan = api(job + "/plan", method="POST", payload={"revision": draft["revision"]})
        [event] = plan["events"]
        assert (event["start_datetime"], event["end_datetime"]) == (date + "T12:00:00", date + "T15:00:59")
        if existing_event:
            for field in ("id", "start_datetime", "end_datetime", "folder_name"):
                assert event[field] == existing_event[field]
            assert event["existing"]
        api(job + "/documents", method="POST")
        command = {"plan_id": plan["id"]}
        confirmation = {**command, "method": execution, "acknowledged": True}
        if execution == "script":
            probe = api(job + "/script/probe", method="POST", payload=command)
            assert not probe["verified"] and probe["host"] is None
            subprocess.run(["/bin/bash", "-c", probe["command"]], check=True)
            proved = api(job + "/script/probe")
            assert proved["verified"] and proved["sha256"] == probe["sha256"]
            assert proved["host"] == {
                "package": str(appdata / "legacy-adoption" / job_id),
                "source": str(host_source), "archive": str(archive),
            }
            confirmation["probe_sha256"] = probe["sha256"]
        api(job + "/confirm", method="POST", payload=confirmation)
        assert api("/api/setup/adoption", method="POST", expected=409, payload={"decision": "skipped"})[
            "code"
        ] == "legacy_adoption_active"
        moves = api(job + "/moves")
        if execution == "manual":
            for artifact in ("folders", "documents"):
                with ZipFile(BytesIO(request(job + "/download/" + artifact))) as package:
                    package.extractall(archive)
            for move in moves:
                original = source / Path(move["source"]).relative_to("/sources/nas")
                target = archive / Path(move["target"]).relative_to("/main-library")
                original.rename(target)
        else:
            shell = api(job + "/script/release", method="POST", payload=command)["command"]
            if rollback:
                subprocess.run(["docker", "restart", container], check=True)
                base = address()
                wait_ready()
                login()
                assert api(job + "/script")["command"] == shell
            subprocess.run(["/bin/bash", "-c", shell], check=True)
            assert api(job + "/script")["status"]["state"] == "completed"
        for move in moves:
            target = archive / Path(move["target"]).relative_to("/main-library")
            assert hashlib.sha256(target.read_bytes()).hexdigest() == move["sha256"]
        assert api(job + "/verify", method="POST", payload=command)["state"] == "verified"
        if rollback:
            assert api(job + "/rollback/start", method="POST", payload=command)["execution"]["phase"] == "rolling_back"
            shell = api(job + "/script")["command"]
            subprocess.run(["/bin/bash", "-c", shell], check=True)
            assert api(job + "/rollback/check", method="POST", payload=command)["execution"]["phase"] == "rolled_back"
            for relative, digest in originals.items():
                assert hashlib.sha256((host_source / relative).read_bytes()).hexdigest() == digest
            assert not list(archive.rglob("event.json"))
            assert all(not (archive / Path(move["target"]).relative_to("/main-library")).exists() for move in moves)
            print("Released script resumed after a container restart and controlled rollback restored the source on native ZFS.")
            return event, moves
        assert api(job + "/finalize", method="POST", payload=command)["state"] == "completed"
        assert api(job + "/finalize", method="POST", payload=command,
                   repeat_finalize=True)["state"] == "completed"
        assert b'id="bk-settings-dialog"' in request("/workspace")
        receipt = request(f"/legacy-adoption/history?library=main&job={job_id}")
        assert b"Bestands" in receipt and b"SHA-256" in receipt
        assert f"&amp;event={event['id']}".encode() in receipt
        assert api("/api/legacy-adoption/jobs", method="POST", expected=409, payload={"root": "nas"})[
            "code"
        ] == "legacy_adoption_inactive"
        return event, moves

    if method == "rollback":
        adopt("script", "first", rollback=True)
        return
    event, moves = adopt(method, "first")
    if method == "manual":
        previous = {item["target_path"]: item["sha256"] for item in moves}
        documents = {path: path.read_bytes() for path in archive.rglob("event.json")}
        later = source / "later" / "old-folders" / "camera"
        later.mkdir(parents=True)
        (later / "extra.raf").write_bytes(b"native ZFS extension media")
        (later / "extra.xmp").write_text(
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreateDate="2026-07-21T14:15:00+02:00"/>'
            '</rdf:RDF></x:xmpmeta>'
        )
        assert api("/api/legacy-adoption/eligibility")["eligible"]
        adopt("script", "later", existing_event=event)
        assert all(hashlib.sha256((archive / path).read_bytes()).hexdigest() == digest
                   for path, digest in previous.items())
        assert any(path.read_bytes() != content for path, content in documents.items())
        print("Later scripted archive extension passed with automatic host discovery and native ZFS.")
    print(f"{method} adoption passed with native ZFS and separate read-only container mounts.")


if __name__ == "__main__":
    smoke(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5])
