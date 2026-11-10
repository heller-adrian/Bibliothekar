"""Publish approved work in private AppData for a separately started host process."""
import base64
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex

from app import legacy_adoption_host as host
from app.appdata import root as appdata_root
from app.database import database_connection
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError, bound_file, bound_sha256, relative_parent
from app.legacy_adoption_plan import _roots
from app.legacy_adoption_verify import _plan
from app.private_storage_security import qualified


PACKAGE_ROOT = "legacy-adoption"
RUNNER_FILES = ("legacy_adoption_host.py", "legacy_adoption_dataset.py")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def _package(plan_id, *, create=False, expected=None):
    if not re.fullmatch(r"[a-f0-9]{32}", plan_id):
        raise AdoptionError("Ungültige Kennung für das Skriptpaket.")
    base = appdata_root()
    if base is None:
        raise AdoptionError("Für die Skriptmethode muss dauerhaftes AppData eingerichtet sein.")
    path = base / PACKAGE_ROOT / plan_id
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
    device, inode = host.inode(os.fstat(descriptor))
    checks = [_sha(Path(__file__).with_name(name).read_bytes()) + "  " + name for name in RUNNER_FILES]
    command = ["python3", "-E", "-s", "-B", "./" + RUNNER_FILES[0], mode,
               "--package", paths["package"], "--source", paths["source"], "--archive", paths["archive"],
               "--sha256", digest, "--package-device", str(device), "--package-inode", str(inode)]
    return ("cd " + shlex.quote(paths["package"]) + " && " +
            shlex.join(["printf", r"%s\n", *checks]) +
            " | sha256sum --check --strict && " + shlex.join(command))


def prepare_probe(library, job_id, plan_id, host_appdata, host_source, host_archive):
    paths = _host_paths(plan_id, host_appdata, host_source, host_archive)
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["id"] != plan_id or not plan["documents_at"] or connection.execute(
            "SELECT 1 FROM legacy_adoption_execution WHERE plan_id = ?", (plan_id,),
        ).fetchone():
            raise AdoptionError("Der aktuelle Plan muss für die Hostpfadprüfung unverbindlich vorbereitet sein.")
        with ExitStack() as stack:
            _roots(stack, library, job)
            descriptor = stack.enter_context(_package(plan_id, create=True))
            _initialize_files(descriptor)
            stack.enter_context(host.package_lock(descriptor))
            for name in RUNNER_FILES:
                source = Path(__file__).with_name(name).read_bytes()
                host.write_atomic(descriptor, name, source)
            digest = _put_json(descriptor, "probe.json", {
                "job_id": job_id, "plan_id": plan_id, "library_id": library.library_id, "host": paths,
                "dataset": json.loads(job["dataset_json"]),
                "source_inode": [job["source_device"], job["source_inode"]],
                "archive_inode": [job["archive_device"], job["archive_inode"]],
            })
            return {"command": _command("probe", descriptor, paths, digest), "host": paths, "sha256": digest}


def probe_details(library, job_id, plan_id):
    base = appdata_root()
    if base is None or not (base / PACKAGE_ROOT / plan_id).is_dir():
        return {}
    with _package(plan_id) as descriptor:
        try:
            data = host.read_bytes(descriptor, "probe.json")
        except FileNotFoundError:
            return {}
        probe = json.loads(data)
        if (probe["job_id"], probe["plan_id"], probe["library_id"]) != (job_id, plan_id, library.library_id):
            raise AdoptionError("Die Hostpfadprüfung gehört zu einem anderen Auftrag.")
        digest = _sha(data)
        paths = probe["host"]
        return {"command": _command("probe", descriptor, paths, digest), "host": paths, "sha256": digest,
                "verified": _read_json(descriptor, "host-proof.json") == {"probe": digest, **paths}}


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
    if _read_json(descriptor, "host-proof.json") != {"probe": _sha(data), **probe["host"]}:
        raise AdoptionError("Der Nachweis fehlt. Führe den Prüfungsbefehl in der TrueNAS-Shell aus.")
    return probe


def _bound_proof(root, path, size, expected):
    with relative_parent(root, path) as (parent, name):
        with bound_file(parent, name) as (fd, info):
            if info.st_size != size or bound_sha256(fd) != expected:
                raise AdoptionError("Dateiinhalt weicht vom freigegebenen Plan ab: " + path)
            return {"stamp": host.stamp(info), "sha256": expected}


def prepare_manifest(connection, library, job, plan, probe_digest):
    plan_id = plan["id"]
    with ExitStack() as stack:
        descriptor = stack.enter_context(_package(plan_id))
        stack.enter_context(host.package_lock(descriptor))
        probe = _approved_host(descriptor, library, job, plan_id, probe_digest)
        source, archive = _roots(stack, library, job)
        if probe["dataset"] != json.loads(job["dataset_json"]):
            raise AdoptionError("Die Hostpfadprüfung ist veraltet.")
        directories = [row[0] for row in connection.execute(
            "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ? ORDER BY relative_path",
            (plan_id,),
        )]
        moves = []
        for row in connection.execute(
            """SELECT move.relative_path, move.target_path, inventory.size_bytes, move.sha256
                 FROM legacy_adoption_moves move JOIN legacy_adoption_inventory inventory
                   ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
                WHERE move.plan_id = ? AND move.target_path IS NOT NULL ORDER BY move.relative_path""",
            (job["id"], plan_id),
        ):
            original, target, size, digest = row
            moves.append({"source": original, "target": target,
                          **_bound_proof(source, original, size, digest)})
        documents = []
        for row in connection.execute(
            """SELECT new.relative_path, new.content, new.sha256, old.size_bytes, old.sha256
                 FROM legacy_adoption_documents new
                 LEFT JOIN legacy_adoption_baseline old USING (plan_id, relative_path)
                WHERE new.plan_id = ? ORDER BY new.relative_path""", (plan_id,),
        ):
            path, content, digest, old_size, old_digest = row
            original = _bound_proof(archive, path, old_size, old_digest) if old_digest else None
            documents.append({"path": path, "original": original, "sha256": digest,
                              "content": base64.b64encode(content).decode("ascii")})
        manifest = {**probe, "format": 1, "directories": directories, "moves": moves, "documents": documents}
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


@contextmanager
def locked_script(library, job_id, plan_id):
    script = _script_row(library, job_id, plan_id)
    expected = [script["package_device"], script["package_inode"]]
    with _package(plan_id, expected=expected) as descriptor, host.package_lock(descriptor):
        yield descriptor, script


def permit(descriptor, script, mode):
    digest = script["manifest_sha256"]
    if mode is not None:
        if _sha(host.read_bytes(descriptor, "manifest.json")) != digest:
            raise AdoptionError("Das Skriptmanifest stimmt nicht mit dem bestätigten Auftrag überein.")
        for name in RUNNER_FILES:
            if host.read_bytes(descriptor, name) != Path(__file__).with_name(name).read_bytes():
                raise AdoptionError("Die Skriptdateien stimmen nicht mit dieser Bibliothekar-Version überein.")
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
    with _package(plan_id, expected=expected) as descriptor:
        status = script_status(descriptor, script)
        running = False
        try:
            with host.package_lock(descriptor):
                pass
        except host.ExecutionError:
            running = True
        result = {"status": status, "running": running, "host": json.loads(script["host_json"])}
        allowed = _read_json(descriptor, "permission.json")
        if (allowed and allowed.get("manifest") == script["manifest_sha256"]
                and allowed.get("mode") in {"apply", "rollback"}):
            result["command"] = _command(allowed["mode"], descriptor, result["host"], script["manifest_sha256"])
        return result


def inspect_runner(name):
    if name not in RUNNER_FILES:
        raise AdoptionError("Unbekannte Skriptdatei.")
    return Path(__file__).with_name(name).read_text()
