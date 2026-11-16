    if method == "review-cancel":
        def wait_for(route, predicate, *, timeout=120):
            deadline = time.monotonic() + timeout
            while True:
                result = api(route)
                if predicate(result):
                    return result
                assert time.monotonic() < deadline, result
                time.sleep(.05)

        def as_owner(*args):
            return subprocess.check_output(["docker", "exec", "--user", "568:568", container, *args], text=True)

        def file_hash(path):
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()

        originals = {item.name: file_hash(item) for item in source.iterdir()}
        job_id = api("/api/legacy-adoption/jobs", method="POST", expected=201, payload={"root": "nas"})["id"]
        job = "/api/legacy-adoption/jobs/" + job_id
        endpoint = job + "/review/batch"
        api(job + "/scan", method="POST", expected=202)
        inventory = wait_for(job, lambda s: s["state"] == "inventoried" and not s["scan_running"])
        assert inventory["review_count"] == 3 and inventory["files"] == 5, inventory
        selected = api(job + "/review/selection")
        assert selected == ["a-before", "undated", "z-video"], selected
        general, = as_owner("find", "/workspace", "-type", "d", "-name", "General").splitlines()
        as_owner("sh", "-c", 'printf "existing copy" > "$1/keep.jpg"', "sh", general)
        batch_id = api(endpoint, method="POST", expected=202, payload={"family_keys": selected})["batch_id"]
        live = wait_for(endpoint + "?details=true", lambda s: s["copied"] == 2 and (s["active"] or {}).get("family_key") == "z-video")
        assert live["state"] == "active" and live["running"] and live["batch_id"] == batch_id, live
        # A foreign inode at a published name stops cleanup after the first family.
        as_owner("mv", general + "/undated.jpg", general + "/user-parked-copy")
        as_owner("sh", "-c", 'printf "foreign replacement" > "$1/undated.jpg"', "sh", general)
        cancel = {"batch_id": batch_id}
        api(endpoint + "/cancel", method="POST", expected=202, payload=cancel)
        stuck = wait_for(endpoint, lambda s: s["state"] == "cancelling" and not s["running"])
        assert stuck["cancel_error"], stuck
        as_owner("test", "!", "-e", general + "/a-before.jpg")
        assert as_owner("cat", general + "/undated.jpg") == "foreign replacement"

        subprocess.run(["docker", "kill", "--signal", "KILL", container], check=True, capture_output=True)
        assert subprocess.check_output(["docker", "inspect", "--format", "{{.State.ExitCode}}", container],text=True).strip() == "137"
        subprocess.run(["docker", "update", "--cpus", "1", container], check=True, capture_output=True)
        subprocess.run(["docker", "start", container], check=True, capture_output=True)
        base = address()
        cookies.clear()
        wait_ready()
        login()
        restored = api(endpoint)
        assert restored["state"] == "cancelling" and restored["batch_id"] == batch_id and not restored["running"], restored
        as_owner("mv", general + "/undated.jpg", general + "/user-replacement.jpg")
        as_owner("mv", general + "/user-parked-copy", general + "/undated.jpg")
        api(endpoint + "/cancel", method="POST", expected=202, payload=cancel)
        final = wait_for(endpoint + "?details=true", lambda s: s["state"] == "cancelled" and not s["running"])
        assert final["pending"] == final["copied"] == final["failed"] == final["bytes_written"] == 0, final
        assert api(job + "/review/selection") == selected
        assert set(as_owner("find", general, "-type", "f", "-printf", "%f\n").splitlines()) == {"keep.jpg", "user-replacement.jpg"}
        assert as_owner("cat", general + "/keep.jpg") == "existing copy"
        assert as_owner("cat", general + "/user-replacement.jpg") == "foreign replacement"
        assert {item.name: file_hash(item) for item in source.iterdir()} == originals
        assert not list(archive.iterdir())
        api(endpoint, method="POST", expected=202, payload={"family_keys": ["undated"]})
        fresh = wait_for(endpoint, lambda s: s["state"] == "finished" and not s["running"])
        assert fresh["copied"] == 1 and not fresh["failed"], fresh
        print("RC14 native ZFS copy cleanup passed after a real container SIGKILL and restart.", flush=True)
        return
