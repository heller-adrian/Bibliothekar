"""Publish approved work in private AppData for a separately started host process."""
import base64
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
from secrets import token_hex
from time import monotonic

from app import legacy_adoption_discover as discovery, legacy_adoption_host as host
from app.appdata import root as appdata_root
from app.database import database_connection
from app.legacy_adoption_dataset import DatasetError, mount_id, mount_table
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError, bound_file, bound_sha256, relative_parent, file_identity
from app.legacy_adoption_plan import _roots
from app.legacy_adoption_verify import _plan, assert_original_layout, move_rows
from app.legacy_adoption_xmp_plan import MAX_XMP_BYTES
from app.xmp_raw_filename import rewrite_raw_filename, XmpReferenceError
from app.private_storage_security import qualified


PACKAGE_ROOT = "legacy-adoption"
RUNNER_FILES = ("legacy_adoption_host.py", "legacy_adoption_dataset.py")
DISCOVERY_FILE = "legacy_adoption_discover.py"
# Bytes shipped in RC17. Only the recognized executor and bootstrap may be
# refreshed under the package lock. The manifest and journal stay bound.
_RC17_RUNNER_DIGESTS = {
    "legacy_adoption_host.py": "cdbb9ad9ea8e9a891ba9f4e686cc593b4789ddf510cccafb7c81bc14ad4e6e04",
    "legacy_adoption_dataset.py": "a96557670afa37aaed905749f3c469f731752a321ead216a50ff04e64459bd65",
    DISCOVERY_FILE: "3e283d3291ef222e7eb111fb23c0f55f89eb9baa9bfca391573e35bc11474cd2",
}

# The discovery program embeds the runner hashes at packaging time.
_RC1_RUNNER_DIGESTS = {
    "legacy_adoption_host.py": "37a523687593d898ebe0366511553e26b8d0c18f4ce9bef3315b49edf27d2aa7",
    DISCOVERY_FILE: "8f3d9d9fdd31cacd221e353629c306d8e852a3897f9d38023d399ae7ee83211d",
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def _package(identifier, *, create=False, expected=None):
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise AdoptionError("Ungültige Kennung für das Skriptpaket.")
    base = appdata_root()
    if base is None:
        raise AdoptionError("Für die Skriptmethode muss dauerhaftes AppData eingerichtet sein.")
    path = base / PACKAGE_ROOT / identifier
    if create:
        for entry in (path.parent, path):
            with qualified(entry.parent, directory=True) as (parent, check):
                check()
                try:
                    os.mkdir(entry.name, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                else:
                    os.fsync(parent)
    with qualified(path, directory=True) as (descriptor, check):
        if expected is not None and host.inode(os.fstat(descriptor)) != expected:
            raise AdoptionError("Das freigegebene AppData-Skriptpaket wurde ausgetauscht.")
        check()
        yield descriptor


def _initialize_files(descriptor):
    for name in ("execution.lock", "journal.jsonl"):
        try:
            fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        except FileExistsError:
            continue
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    os.fsync(descriptor)


def _read_json(descriptor, name):
    for _ in range(3):
        try:
            return json.loads(host.read_bytes(descriptor, name))
        except FileNotFoundError:
            return None
        except host.ExecutionError as error:
            if not str(error).startswith("The file changed while"):
                raise
    raise AdoptionError("Der Skriptstatus hat sich beim Lesen geändert. Versuche es erneut.")


def _put_json(descriptor, name, value):
    data = host.json_bytes(value)
    host.write_atomic(descriptor, name, data)
    return _sha(data)


def _host_paths(plan_id, host_appdata, host_source, host_archive):
    for path in (host_appdata, host_source, host_archive):
        host.path_parts(path, absolute=True)
        if any(ord(character) < 32 or ord(character) == 127 for character in path):
            raise AdoptionError("Hostpfade dürfen keine Steuerzeichen enthalten.")
    return {"package": str(PurePosixPath(host_appdata) / PACKAGE_ROOT / plan_id),
            "source": host_source, "archive": host_archive}


def _command(mode, descriptor, paths, digest):
    if host.info_at(descriptor, DISCOVERY_FILE) is not None:
        return _launch(descriptor, paths["package"], mode, digest, paths["source"], paths["archive"])
    # Keep the command available for previously prepared packages and journals.
    device, inode = host.inode(os.fstat(descriptor))
    checks = [_sha(Path(__file__).with_name(name).read_bytes()) + "  " + name for name in RUNNER_FILES]
    command = ["python3", "-E", "-s", "-B", "./" + RUNNER_FILES[0], mode,
               "--package", paths["package"], "--source", paths["source"], "--archive", paths["archive"],
               "--sha256", digest, "--package-device", str(device), "--package-inode", str(inode)]
    return ("cd " + shlex.quote(paths["package"]) + " && " +
            shlex.join(["printf", r"%s\n", *checks]) +
            " | sha256sum --check --strict && " + shlex.join(command))


def _probe_package(job_id, plan_id):
    base = appdata_root()
    if base is not None and (base / PACKAGE_ROOT / job_id).exists():
        return job_id
    return plan_id  # Packages prepared before the job-based layout.


def _host_proof(descriptor, probe, digest):
    if _probe_error(descriptor, digest):
        return None
    proof = _read_json(descriptor, "host-proof.json")
    if not isinstance(proof, dict) or set(proof) != {"probe", "package", "source", "archive"} or proof["probe"] != digest:
        return None
    paths = {key: proof[key] for key in ("package", "source", "archive")}
    if probe["host"] is not None:
        return paths if paths == probe["host"] else None
    package = PurePosixPath(paths["package"])
    if package.name != probe["job_id"] or package.parent.name != PACKAGE_ROOT:
        return None
    checked = _host_paths(probe["job_id"], str(package.parent.parent), paths["source"], paths["archive"])
    return paths if paths == checked else None


def _probe_error(descriptor, digest):
    failure = _read_json(descriptor, "host-check-error.json")
    if isinstance(failure, dict) and failure.get("probe") == digest and isinstance(failure.get("detail"), str):
        return failure["detail"]
    return None


def _discovery_script():
    checksums = {name: _sha(Path(__file__).with_name(name).read_bytes()) for name in reversed(RUNNER_FILES)}
    return f"RUNNER_CHECKSUMS = {checksums!r}\n".encode() + Path(__file__).with_name(DISCOVERY_FILE).read_bytes()


def _launch(descriptor, path, *args, automatic=False):
    device, inode = host.inode(os.fstat(descriptor))
    return shlex.join(["sudo", "python3", "-I", "-B", "-c", discovery.bootstrap(automatic=automatic),
                       path, f"{os.major(device)}:{os.minor(device)}", str(inode), _sha(_discovery_script()), *args])


def _package_mount(path, descriptor):
    try:
        mount = mount_table()[mount_id(descriptor)]
        device = os.fstat(descriptor).st_dev
        if mount.device == f"{os.major(device)}:{os.minor(device)}":
            return {"directory": str(mount.root / PurePosixPath(path).relative_to(mount.target)), "device": mount.device}
    except (OSError, KeyError, ValueError, DatasetError):
        pass
    return None


def _probe_result(descriptor, probe, digest):
    paths = _host_proof(descriptor, probe, digest)
    diagnostic = _probe_error(descriptor, digest)
    command = None
    if probe["host"] is not None:
        command = _command("probe", descriptor, probe["host"], digest)
    elif mount := probe.get("package_mount"):
        command = _launch(descriptor, mount["directory"], digest, automatic=True)
    else:
        diagnostic = "Bereite die automatische Hostprüfung erneut vor. Falls kein Befehl verfügbar ist, verwende die manuelle Hostpfadprüfung."
    return {"command": command, "host": paths or probe["host"], "sha256": digest,
            "verified": paths is not None, "dataset": probe["dataset"]["dataset"], "diagnostic": diagnostic}


def prepare_probe(library, job_id, plan_id, host_appdata=None, host_source=None, host_archive=None):
    supplied = (host_appdata, host_source, host_archive)
    paths = _host_paths(job_id, *supplied) if any(value is not None for value in supplied) else None
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if (plan["id"] != plan_id or plan["filename_method"] not in {None, "script"}
                or not plan["documents_at"] or connection.execute(
            "SELECT 1 FROM legacy_adoption_execution WHERE plan_id = ?", (plan_id,),
        ).fetchone()):
            raise AdoptionError("Der aktuelle Plan muss für die Hostpfadprüfung unverbindlich vorbereitet sein.")
        with ExitStack() as stack:
            _roots(stack, library, job)
            descriptor = stack.enter_context(_package(job_id, create=True))
            _initialize_files(descriptor)
            stack.enter_context(host.package_lock(descriptor))
            for name in RUNNER_FILES:
                host.write_atomic(descriptor, name, Path(__file__).with_name(name).read_bytes())
            package_path = appdata_root() / PACKAGE_ROOT / job_id
            host.write_atomic(descriptor, DISCOVERY_FILE, _discovery_script())
            probe = {
                "job_id": job_id, "plan_id": plan_id, "library_id": library.library_id, "host": paths,
                "container": {
                    "package": str(package_path),
                    "source": job["source_root"], "archive": job["archive_root"],
                },
                "package_mount": _package_mount(package_path, descriptor) if paths is None else None,
                "nonce": token_hex(16),
                "dataset": json.loads(job["dataset_json"]),
                "source_inode": [job["source_device"], job["source_inode"]],
                "archive_inode": [job["archive_device"], job["archive_inode"]],
            }
            digest = _put_json(descriptor, "probe.json", probe)
            return _probe_result(descriptor, probe, digest)


def probe_details(library, job_id, plan_id):
    base = appdata_root()
    identifier = _probe_package(job_id, plan_id)
    if base is None or not (base / PACKAGE_ROOT / identifier).is_dir():
        return {}
    with _package(identifier) as descriptor:
        try:
            data = host.read_bytes(descriptor, "probe.json")
        except FileNotFoundError:
            return {}
        probe = json.loads(data)
        if (probe["job_id"], probe["library_id"]) != (job_id, library.library_id):
            raise AdoptionError("Die Hostpfadprüfung gehört zu einem anderen Auftrag.")
        if probe["plan_id"] != plan_id:
            return {}
        return _probe_result(descriptor, probe, _sha(data))


def _approved_host(descriptor, library, job, plan_id, probe_digest):
    try:
        data = host.read_bytes(descriptor, "probe.json")
    except FileNotFoundError as error:
        raise AdoptionError("Bereite zuerst die Prüfung der Hostpfade vor.") from error
    if _sha(data) != probe_digest:
        raise AdoptionError("Die bestätigte Hostpfadprüfung ist veraltet. Lade den Auftrag erneut.")
    probe = json.loads(data)
    if (probe["job_id"], probe["plan_id"], probe["library_id"]) != (job["id"], plan_id, library.library_id):
        raise AdoptionError("Die Hostpfadprüfung gehört zu einem anderen Auftrag.")
    paths = _host_proof(descriptor, probe, probe_digest)
    if paths is None:
        raise AdoptionError("Der Nachweis fehlt. Führe den Prüfungsbefehl in der TrueNAS-Shell aus.")
    return {**probe, "host": paths}


def _bound_proof(root, path, size, expected, *, inventory_identity=None, xmp=False, on_bytes=None):
    content = None
    with relative_parent(root, path) as (parent, name):
        with bound_file(parent, name) as (fd, info):
            if (info.st_dev != os.fstat(root).st_dev or info.st_size != size
                    or (inventory_identity is not None
                        and file_identity(info)[:4] != tuple(inventory_identity[:4]))):
                raise AdoptionError("Die Dateiidentität weicht von der Inventur ab: " + path)
            if xmp:
                if size > MAX_XMP_BYTES:
                    raise AdoptionError("XMP-Datei erfordert eine separate Prüfung (zu groß): " + path)
                content = os.pread(fd, size, 0)
                if on_bytes:
                    on_bytes(len(content))
                actual = _sha(content) if len(content) == size else None
            else:
                actual = bound_sha256(fd, progress_callback=on_bytes)
            if actual != expected:
                raise AdoptionError("Dateiinhalt weicht vom freigegebenen Plan ab: " + path)
            return {"stamp": host.stamp(info), "sha256": expected}, content


def prepare_manifest(connection, library, job, plan, probe_digest, *, progress=None):
    plan_id = plan["id"]
    with ExitStack() as stack:
        descriptor = stack.enter_context(_package(_probe_package(job["id"], plan_id)))
        stack.enter_context(host.package_lock(descriptor))
        probe = _approved_host(descriptor, library, job, plan_id, probe_digest)
        if probe["dataset"] != json.loads(job["dataset_json"]):
            raise AdoptionError("Die Hostpfadprüfung ist veraltet.")
        directories = [row[0] for row in connection.execute(
            "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ? ORDER BY relative_path",
            (plan_id,),
        )]
        source_rows = list(move_rows(connection, job["id"], plan_id, include_duplicates=True))
        archive_totals = connection.execute(
            "SELECT count(*), coalesce(sum(size_bytes), 0) FROM legacy_adoption_baseline WHERE plan_id=?",
            (plan_id,),
        ).fetchone()
        phase_started = previous_update = monotonic()
        phase, total_files, total_bytes = "source", len(source_rows), sum(row["size_bytes"] for row in source_rows)
        done_files = done_bytes = 0

        def checkpoint(force=False):
            nonlocal previous_update
            now = monotonic()
            if progress and (force or now - previous_update >= 1):
                progress(descriptor, done_files, total_files, done_bytes, total_bytes,
                         phase=phase, elapsed_seconds=int(now - phase_started))
                previous_update = now

        def next_phase(name, files, size):
            nonlocal phase, total_files, total_bytes, done_files, done_bytes, phase_started
            checkpoint(True)
            phase, total_files, total_bytes = name, files, size
            done_files = done_bytes = 0
            phase_started = monotonic()
            checkpoint(True)

        def read_bytes(count):
            nonlocal done_bytes
            done_bytes += count
            checkpoint()

        moves, xmp_edits = [], []
        archive_proofs, duplicate_proofs = {}, {}

        def source_check(root, row):
            nonlocal done_files
            original, target = row["relative_path"], row["target_path"]
            proof, content = _bound_proof(
                root, original, row["size_bytes"], row["sha256"],
                inventory_identity=json.loads(row["identity"]), xmp=bool(row["current_sha256"]),
                on_bytes=read_bytes if progress else None,
            )
            if target is None:
                duplicate_proofs[original] = proof
            else:
                moves.append({"source": original, "target": target, **proof})
            if content is not None:
                try:
                    rewritten = rewrite_raw_filename(content, row["xmp_old_raw_name"], row["xmp_new_raw_name"])
                except XmpReferenceError as error:
                    raise AdoptionError("Die geplante XMP-Umbenennung ist nicht mehr gültig: " + original) from error
                if len(rewritten) != row["current_size_bytes"] or _sha(rewritten) != row["current_sha256"]:
                    raise AdoptionError("Der bestätigte XMP-Zielinhalt weicht von der Planung ab: " + original)
                xmp_edits.append({
                    "source": original, "target": target, "original_sha256": row["sha256"],
                    "sha256": row["current_sha256"], "size_bytes": row["current_size_bytes"],
                    "content": base64.b64encode(rewritten).decode("ascii"),
                })
            done_files += 1
            checkpoint(done_files == total_files)

        def archive_check(root, path, size, digest):
            nonlocal done_files
            if phase != "archive":
                next_phase("archive", *archive_totals)
            archive_proofs[path], _ = _bound_proof(root, path, size, digest,
                                                   on_bytes=read_bytes if progress else None)
            done_files += 1
            checkpoint(done_files == total_files)

        checkpoint(True)
        assert_original_layout(connection, library, job, plan, source_check=source_check, archive_check=archive_check)
        next_phase("manifest", 0, 0)
        documents = []
        for row in connection.execute(
            """SELECT new.relative_path, new.content, new.sha256, old.size_bytes, old.sha256
                 FROM legacy_adoption_documents new
                 LEFT JOIN legacy_adoption_baseline old USING (plan_id, relative_path)
                WHERE new.plan_id = ? ORDER BY new.relative_path""", (plan_id,),
        ):
            path, content, digest, old_size, old_digest = row
            original = archive_proofs[path] if old_digest else None
            documents.append({"path": path, "original": original, "sha256": digest,
                              "content": base64.b64encode(content).decode("ascii")})
        manifest = {**probe, "format": 2 if xmp_edits else 1,
                    "directories": directories, "moves": moves, "documents": documents,
                    "release_proofs": {"archive": archive_proofs, "duplicates": duplicate_proofs},
                    **({"xmp_edits": xmp_edits} if xmp_edits else {})}
        excluded = json.loads(plan["draft_json"]).get("file_exclusions")
        if excluded:
            manifest["excluded_sources"] = list(excluded.values())
        host.validate_plan(manifest)
        if _read_json(descriptor, "permission.json") is not None:
            raise AdoptionError("Das Paket wurde bereits zur Ausführung freigegeben.")
        digest = _put_json(descriptor, "manifest.json", manifest)
        connection.execute(
            """INSERT INTO legacy_adoption_scripts
               (plan_id, manifest_sha256, package_device, package_inode, host_json)
               VALUES (?, ?, ?, ?, ?)""",
            (plan_id, digest, *host.inode(os.fstat(descriptor)), json.dumps(probe["host"])),
        )


def _script_row(library, job_id, plan_id):
    with database_connection(library.database_path) as connection:
        _job(connection, library.library_id, job_id)
        row = connection.execute(
            """SELECT script.*, execution.phase FROM legacy_adoption_scripts script
                 JOIN legacy_adoption_execution execution USING (plan_id)
                 JOIN legacy_adoption_plans plan ON plan.id = script.plan_id
                WHERE plan.job_id = ? AND script.plan_id = ?""",
            (job_id, plan_id),
        ).fetchone()
        if row is None:
            raise AdoptionError("Für diesen Übernahmeauftrag ist kein verbindliches Skriptpaket gespeichert.")
        return row


def _script_package(script, job_id, plan_id):
    identifier = PurePosixPath(json.loads(script["host_json"])["package"]).name
    if identifier not in {job_id, plan_id}:
        raise AdoptionError("Die Kennung des freigegebenen Skriptpakets stimmt nicht überein.")
    return identifier


@contextmanager
def locked_script(library, job_id, plan_id):
    script = _script_row(library, job_id, plan_id)
    expected = [script["package_device"], script["package_inode"]]
    with _package(_script_package(script, job_id, plan_id), expected=expected) as descriptor, host.package_lock(descriptor):
        yield descriptor, script


def _runner_differences(descriptor):
    expected = {name: Path(__file__).with_name(name).read_bytes() for name in RUNNER_FILES}
    if host.info_at(descriptor, DISCOVERY_FILE) is not None:
        expected[DISCOVERY_FILE] = _discovery_script()
    differences = {}
    for name, current in expected.items():
        previous = host.read_bytes(descriptor, name)
        if previous != current:
            recognized = {_RC17_RUNNER_DIGESTS[name]}
            if name in _RC1_RUNNER_DIGESTS:
                recognized.add(_RC1_RUNNER_DIGESTS[name])
            if _sha(previous) not in recognized:
                raise AdoptionError("Die Skriptdateien stimmen nicht mit dieser Bibliothekar-Version überein.")
            differences[name] = current
    return differences


def script_journal_started(descriptor):
    with bound_file(descriptor, "journal.jsonl") as (_, info):
        return bool(info.st_size)


def retire_unstarted_package(descriptor, script):
    if script["phase"] != "script_prepared" or script_journal_started(descriptor):
        raise AdoptionError("Das Skript wurde bereits ausgeführt. Verwende die kontrollierte Wiederherstellung.")
    permit(descriptor, script, None)
    for name in ("manifest.json", "permission.json", "status.json", "preparation.json"):
        try:
            os.unlink(name, dir_fd=descriptor)
        except FileNotFoundError:
            pass
    os.fsync(descriptor)


def assert_unstarted_release_current(library, job_id, plan_id, descriptor, script):
    """Recheck the bound manifest under the package lock before first execution."""
    if script_journal_started(descriptor):
        # The host will validate the journal against the same digest.
        return
    content = host.read_bytes(descriptor, "manifest.json")
    if _sha(content) != script["manifest_sha256"]:
        raise AdoptionError("Das Skriptmanifest stimmt nicht mit dem bestätigten Auftrag überein.")
    manifest = json.loads(content)
    if (manifest["job_id"], manifest["plan_id"], manifest["library_id"]) != (job_id, plan_id, library.library_id):
        raise AdoptionError("Der Skriptnachweis gehört zu einem anderen Auftrag.")
    release_proofs = manifest.get("release_proofs")
    moves = {row["source"]: row for row in manifest["moves"]}

    def check_proof(root, path, proof, digest):
        if proof is None or proof["sha256"] != digest:
            raise AdoptionError("Der gebundene Dateinachweis fehlt: " + path)
        with relative_parent(root, path) as (parent, name):
            with bound_file(parent, name) as (_, info):
                if info.st_dev != os.fstat(root).st_dev or host.stamp(info) != proof["stamp"]:
                    raise AdoptionError("Die Datei wurde nach der Skriptvorbereitung verändert: " + path)

    def source_check(root, row):
        path = row["relative_path"]
        proof = moves.get(path) if row["target_path"] else release_proofs["duplicates"].get(path)
        if row["target_path"] and (not proof or proof["target"] != row["target_path"]):
            raise AdoptionError("Der vorbereitete Zielpfad stimmt nicht mit dem Plan überein: " + path)
        check_proof(root, path, proof, row["sha256"])

    def archive_check(root, path, size, digest):
        check_proof(root, path, release_proofs["archive"].get(path), digest)

    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["id"] != plan_id or json.loads(job["dataset_json"]) != manifest["dataset"]:
            raise AdoptionError("Der Dataset-Nachweis für das Skript ist veraltet.")
        assert_original_layout(
            connection, library, job, plan,
            source_check=source_check if release_proofs is not None else None,
            archive_check=archive_check if release_proofs is not None else None,
        )
        if release_proofs is None:
            # A historical package lacks the additional archive proof.
            # Rehash above and still check its originally approved stamps.
            with ExitStack() as stack:
                source, _ = _roots(stack, library, job)
                for path, proof in moves.items():
                    check_proof(source, path, proof, proof["sha256"])


def permit(descriptor, script, mode):
    digest = script["manifest_sha256"]
    if mode is not None:
        if _sha(host.read_bytes(descriptor, "manifest.json")) != digest:
            raise AdoptionError("Das Skriptmanifest stimmt nicht mit dem bestätigten Auftrag überein.")
        # Verify every file before writing any of them. Old and new bootstrap
        # commands both reject an interrupted refresh until it is completed.
        for name, data in _runner_differences(descriptor).items():
            host.write_atomic(descriptor, name, data)
    _put_json(descriptor, "permission.json", {"manifest": digest, "mode": mode})
    return _command(mode, descriptor, json.loads(script["host_json"]), digest) if mode else None


def script_status(descriptor, script):
    status = _read_json(descriptor, "status.json")
    if status and status.get("manifest") != script["manifest_sha256"]:
        raise AdoptionError("Das externe Skript meldet einen anderen Verschiebeplan.")
    return status


def script_details(library, job_id, plan_id):
    script = _script_row(library, job_id, plan_id)
    expected = [script["package_device"], script["package_inode"]]
    with _package(_script_package(script, job_id, plan_id), expected=expected) as descriptor:
        status = script_status(descriptor, script)
        running = False
        can_reopen = False
        try:
            with host.package_lock(descriptor):
                can_reopen = script["phase"] == "script_prepared" and not script_journal_started(descriptor)
        except host.ExecutionError:
            running = True
        result = {"status": status, "running": running, "host": json.loads(script["host_json"]),
                  "can_reopen": can_reopen}
        allowed = _read_json(descriptor, "permission.json")
        if (allowed and allowed.get("manifest") == script["manifest_sha256"]
                and allowed.get("mode") in {"apply", "rollback"} and not _runner_differences(descriptor)):
            result["command"] = _command(allowed["mode"], descriptor, result["host"], script["manifest_sha256"])
        return result


def read_manifest(library, job_id, plan_id):
    script = _script_row(library, job_id, plan_id)
    expected = [script["package_device"], script["package_inode"]]
    with _package(_script_package(script, job_id, plan_id), expected=expected) as descriptor:
        content = host.read_bytes(descriptor, "manifest.json")
        if _sha(content) != script["manifest_sha256"]:
            raise AdoptionError("Das Skriptmanifest stimmt nicht mit dem bestätigten Auftrag überein.")
        return content


def inspect_runner(name):
    if name not in (*RUNNER_FILES, DISCOVERY_FILE):
        raise AdoptionError("Unbekannte Skriptdatei.")
    return Path(__file__).with_name(name).read_text()
