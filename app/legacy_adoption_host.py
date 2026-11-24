"""Standalone executor for one confirmed legacy adoption on a Linux ZFS host."""
import argparse
import base64
from contextlib import ExitStack, contextmanager
import ctypes
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from unicodedata import normalize
from uuid import uuid4

if __package__:
    from .legacy_adoption_dataset import DatasetError, mount_id, revalidate
else:
    from legacy_adoption_dataset import DatasetError, mount_id, revalidate


_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
RENAME_NOREPLACE = 1


class ExecutionError(RuntimeError):
    pass


def path_parts(value, *, absolute=False):
    if not isinstance(value, str) or value.startswith("/") != absolute:
        raise ExecutionError("Invalid path in the approved package.")
    parts = value[1:].split("/") if absolute else value.split("/")
    if any(part in {"", ".", ".."} or "\0" in part for part in parts):
        raise ExecutionError("Invalid path in the approved package.")
    return parts


def inode(info):
    return [info.st_dev, info.st_ino]


def stamp(info):
    return [*inode(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def info_at(parent, name):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


@contextmanager
def directory(path, expected):
    parts = path_parts(path, absolute=True)
    with ExitStack() as stack:
        parent = os.open("/", _DIRECTORY)
        stack.callback(os.close, parent)
        for name in parts:
            parent = os.open(name, _DIRECTORY, dir_fd=parent)
            stack.callback(os.close, parent)
        if inode(os.fstat(parent)) != expected:
            raise ExecutionError("The supplied host directory does not match the approved directory: " + path)
        yield parent


def check_child(parent, name, descriptor):
    current = info_at(parent, name)
    if (current is None or inode(current) != inode(os.fstat(descriptor)) or
            mount_id(parent) != mount_id(descriptor)):
        raise ExecutionError("A path was replaced or crosses a mount boundary: " + name)


@contextmanager
def relative_parent(root, relative, *, create=False):
    parts = path_parts(relative)
    parent = root
    links = []
    with ExitStack() as stack:
        for name in parts[:-1]:
            if create:
                try:
                    os.mkdir(name, 0o777, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            child = os.open(name, _DIRECTORY, dir_fd=parent)
            stack.callback(os.close, child)
            check_child(parent, name, child)
            links.append((parent, name, child))
            parent = child

        def check():
            for link in links:
                check_child(*link)

        yield parent, parts[-1], check
        check()


@contextmanager
def file_at(parent, name):
    descriptor = os.open(name, _FILE, dir_fd=parent)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ExecutionError("Not a regular file: " + name)
        check_child(parent, name, descriptor)
        yield descriptor, info
        current = info_at(parent, name)
        if current is None or stamp(os.fstat(descriptor)) != stamp(info) or stamp(current) != stamp(info):
            raise ExecutionError("The file changed while being read: " + name)
    finally:
        os.close(descriptor)


def hash_fd(descriptor):
    hasher = hashlib.sha256()
    while block := os.read(descriptor, 1024 * 1024):
        hasher.update(block)
    return hasher.hexdigest()


def verify_file(parent, name, expected, *, allow_ctime_change=False):
    with file_at(parent, name) as (fd, info):
        actual = stamp(info)
        fields = ("device", "inode", "size", "mtime_ns", "ctime_ns")
        compared = 4 if allow_ctime_change else len(fields)
        if actual[:compared] != expected["stamp"][:compared]:
            differences = ", ".join(field for field, value, approved in
                                    zip(fields[:compared], actual, expected["stamp"]) if value != approved)
            raise ExecutionError(f"File identity differs from the approved plan: {name} ({differences})")
        if hash_fd(fd) != expected["sha256"]:
            raise ExecutionError("File checksum differs from the approved plan: " + name)
    return actual


def rename_noreplace(source, source_name, target, target_name):
    if not sys.platform.startswith("linux"):
        raise ExecutionError("The execution host must run Linux.")
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise ExecutionError("Atomic no-replace rename is unavailable.") from error
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source, os.fsencode(source_name), target, os.fsencode(target_name), RENAME_NOREPLACE):
        code = ctypes.get_errno()
        if code == errno.EXDEV:
            raise ExecutionError("The host rejected a rename across mounts. No file was copied.")
        raise OSError(code, os.strerror(code), target_name)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def read_bytes(parent, name):
    with file_at(parent, name) as (fd, _):
        with os.fdopen(os.dup(fd), "rb") as stream:
            return stream.read()


def write_atomic(parent, name, data):
    temporary = ".new-" + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)  # Package directory remains private; the app can read host-written evidence.
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        if info_at(parent, temporary) is not None:
            os.unlink(temporary, dir_fd=parent)


@contextmanager
def package_lock(root):
    fd = os.open("execution.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
    try:
        check_child(root, "execution.lock", fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExecutionError("Invalid package lock.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ExecutionError("Another process is using this adoption package.") from error
        check_child(root, "execution.lock", fd)
        yield
    finally:
        os.close(fd)


class Journal:
    """Durable append-only transitions. The final partial line is discarded on resume."""

    def __init__(self, package_fd, binding):
        self.package_fd = package_fd
        self.binding = binding
        self.latest = {}
        self.proofs = {}
        self.direction = None

    def __enter__(self):
        fd = os.open("journal.jsonl", os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=self.package_fd)
        try:
            check_child(self.package_fd, "journal.jsonl", fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ExecutionError("Invalid execution journal.")
            self.stream = os.fdopen(os.dup(fd), "a+b")
        finally:
            os.close(fd)
        try:
            self.stream.seek(0)
            while line := self.stream.readline():
                if not line.endswith(b"\n"):
                    self.stream.seek(-len(line), os.SEEK_CUR)
                    self.stream.truncate()
                    self._sync()
                    break
                item = json.loads(line)
                if item["manifest"] != self.binding:
                    raise ExecutionError("The journal does not belong to the confirmed manifest.")
                self._apply(item)
        except BaseException:
            self.stream.close()
            raise
        return self

    def __exit__(self, *exc):
        self.stream.close()

    def _sync(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def _apply(self, item):
        if item["operation"] is None:
            self.direction = item["state"]
        else:
            self.latest[item["operation"]] = item["state"]
            if "proof" in item:
                self.proofs[item["operation"]] = item["proof"]

    def append(self, operation, state, *, proof=None):
        item = {"manifest": self.binding, "operation": operation, "state": state,
                "at": datetime.now(timezone.utc).isoformat()}
        if proof is not None:
            item["proof"] = proof
        self.stream.write(json_bytes(item))
        self._sync()
        self._apply(item)


def move(journal, operation, source, source_path, target, target_path, expected, check_roots, *, reverse=False):
    """Reconcile the two names against the last durable intent before any rename."""
    intent, done = ("reverse_intent", "reverse_done") if reverse else ("forward_intent", "forward_done")
    previous = journal.latest.get(operation)
    # Filesystem metadata may change ctime between approval and execution.
    # Media still needs the original inode, mtime, size and full SHA-256.
    # file_at and the pre-rename stat retain ctime as a concurrent-change fence.
    media = operation.startswith("media:")
    if reverse and previous is None:
        return
    if reverse and previous == "forward_intent":
        with relative_parent(target, target_path) as (parent, name, _):
            # A forward intent may have been logged before the actual rename.
            if info_at(parent, name) is not None:
                verify_file(parent, name, expected, allow_ctime_change=media)
                with relative_parent(source, source_path) as (other, other_name, _):
                    if info_at(other, other_name) is not None:
                        raise ExecutionError("Both names are present after an interrupted operation: " + target_path)
                journal.append(operation, done)
                return
    with relative_parent(source, source_path) as (left, original, check_left), \
            relative_parent(target, target_path) as (right, destination, check_right):
        old = info_at(left, original)
        new = info_at(right, destination)
        if old is None and new is not None and previous in {intent, done}:
            verify_file(right, destination, expected, allow_ctime_change=True)
            os.fsync(left)
            os.fsync(right)
            if previous != done:
                journal.append(operation, done)
            return
        if old is None or new is not None or previous == done:
            raise ExecutionError("Unexpected file state for " + source_path + " → " + target_path)
        actual = verify_file(left, original, expected, allow_ctime_change=reverse or media)
        if previous != intent:
            journal.append(operation, intent)
        if media:
            canonical = normalize("NFC", destination).casefold()
            if any(normalize("NFC", name).casefold() == canonical for name in os.listdir(right)):
                raise ExecutionError("A filename already occupies the approved destination: " + target_path)
        check_roots()
        check_left()
        check_right()
        current = info_at(left, original)
        if current is None or stamp(current) != actual:
            raise ExecutionError("The source changed before rename: " + source_path)
        rename_noreplace(left, original, right, destination)
        os.fsync(left)
        os.fsync(right)
        verify_file(right, destination, expected, allow_ctime_change=True)
        if info_at(left, original) is not None:
            raise ExecutionError("The source path reappeared after rename: " + source_path)
        journal.append(operation, done)


def stream_xmp_patch(fd, size, patch):
    """Copy byte ranges with one verified substitution, using bounded reads."""
    offset = patch["offset"]
    old, new = bytes.fromhex(patch["old"]), bytes.fromhex(patch["new"])
    if os.pread(fd, len(old), offset) != old:
        raise ExecutionError("The original XMP token differs from the approved patch.")

    def read(start, end):
        while start < end:
            block = os.pread(fd, min(1024 * 1024, end - start), start)
            if not block:
                raise ExecutionError("The original XMP ended during staging.")
            yield block
            start += len(block)

    yield from read(0, offset)
    yield new
    yield from read(offset + len(old), size)


def write_document(holding, name, data, size, digest):
    if info_at(holding, name) is not None:
        return  # A crash may have followed creation but preceded the journal record.
    temporary = ".document-" + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, dir_fd=holding)
    try:
        with os.fdopen(fd, "wb") as stream:
            checksum = hashlib.sha256()
            written = 0
            for block in (data,) if isinstance(data, bytes) else data:
                stream.write(block)
                checksum.update(block)
                written += len(block)
            if (written, checksum.hexdigest()) != (size, digest):
                raise ExecutionError("The generated file differs from the approved output: " + name)
            stream.flush()
            os.fsync(stream.fileno())
        rename_noreplace(holding, temporary, holding, name)
        os.fsync(holding)
    finally:
        if info_at(holding, temporary) is not None:
            os.unlink(temporary, dir_fd=holding)


def apply_document(journal, item, archive, holding, prefix, index, check_roots, reverse):
    install = f"document:{index}"
    save = f"original-document:{index}"
    stage = f"stage-document:{index}"
    ready_name = f"new-{index}.json"
    ready = prefix + "/" + ready_name
    saved = prefix + f"/original-{index}.json"
    current = item["path"]

    proof = journal.proofs.get(stage)
    if proof is not None and proof["sha256"] != item["sha256"]:
        raise ExecutionError("The staged document proof differs from the manifest: " + current)

    if reverse:
        if journal.latest.get(install) is not None:
            if journal.latest.get(save) in {"reverse_intent", "reverse_done"}:
                verify_file(holding, ready_name, proof, allow_ctime_change=True)
            else:
                move(journal, install, archive, current, archive, ready,
                     proof, check_roots, reverse=True)
        if item["original"] and journal.latest.get(save) is not None:
            move(journal, save, archive, saved, archive, current,
                 item["original"], check_roots, reverse=True)
        return

    if proof is None:
        data = base64.b64decode(item["content"], validate=True)
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ExecutionError("The prepared document differs from the manifest: " + current)
        check_roots()
        if info_at(holding, ready_name) is None:
            write_document(holding, ready_name, data, len(data), item["sha256"])
        with file_at(holding, ready_name) as (fd, info):
            if info.st_size != len(data) or hash_fd(fd) != item["sha256"]:
                raise ExecutionError("The staged document differs from the manifest: " + current)
            proof = {"stamp": stamp(info), "sha256": item["sha256"]}
        journal.append(stage, "document_staged", proof=proof)
    if item["original"]:
        if journal.latest.get(install) is not None:
            verify_file(holding, f"original-{index}.json", item["original"], allow_ctime_change=True)
        else:
            move(journal, save, archive, current, archive, saved, item["original"], check_roots)
    move(journal, install, archive, ready, archive, current, proof, check_roots)


def apply_xmp_edit(journal, item, original_move, archive, holding, prefix, index,
                   check_roots, *, reverse=False):
    """Journal a two-way, byte-preserving XMP content swap.

    The original inode/bytes are kept under the protected archive holding
    directory until verification or rollback. The revised file is installed
    by no-replace rename; nothing is overwritten in place.
    """
    stage = f"xmp-stage:{index}"
    save = f"media:xmp-save:{index}"
    install = f"media:xmp-install:{index}"
    ready_name = f"new-xmp-{index}.xmp"
    saved_name = f"original-xmp-{index}.xmp"
    ready = prefix + "/" + ready_name
    saved = prefix + "/" + saved_name
    target = item["target"]
    original = {"stamp": original_move["stamp"], "sha256": original_move["sha256"]}
    staged = journal.proofs.get(stage)

    if reverse:
        if journal.latest.get(save) is None and journal.latest.get(install) is None:
            return
        if staged is None:
            raise ExecutionError("XMP staging proof missing during rollback: " + target)
        if journal.latest.get(install) is not None:
            if journal.latest.get(save) in {"reverse_intent", "reverse_done"}:
                verify_file(holding, ready_name, staged, allow_ctime_change=True)
            else:
                move(journal, install, archive, target, archive, ready,
                     staged, check_roots, reverse=True)
        if journal.latest.get(save) is not None:
            move(journal, save, archive, saved, archive, target,
                 original, check_roots, reverse=True)
        return

    if staged is None:
        check_roots()
        if info_at(holding, ready_name) is None:
            size, digest = item["size_bytes"], item["sha256"]
            if "patch" in item:
                with relative_parent(archive, target) as (directory, name, check), file_at(directory, name) as (fd, info):
                    if stamp(info)[:4] != original["stamp"][:4]:
                        raise ExecutionError("Original XMP identity differs from the manifest: " + target)
                    write_document(holding, ready_name, stream_xmp_patch(fd, info.st_size, item["patch"]), size, digest)
                    check()
            else:
                content = base64.b64decode(item["content"], validate=True)
                write_document(holding, ready_name, content, size, digest)
        with file_at(holding, ready_name) as (fd, info):
            if info.st_size != item["size_bytes"] or hash_fd(fd) != item["sha256"]:
                raise ExecutionError("Staged XMP content has changed: " + target)
            staged = {"stamp": stamp(info), "sha256": item["sha256"]}
        journal.append(stage, "xmp_staged", proof=staged)
    elif journal.latest.get(install) is None:
        verify_file(holding, ready_name, staged, allow_ctime_change=True)

    if journal.latest.get(save) != "forward_done":
        move(journal, save, archive, target, archive, saved,
             original, check_roots)
    else:
        verify_file(holding, saved_name, original, allow_ctime_change=True)

    # If the install intent was journaled but the rename crashed, move()
    # reconciles the existing name before a new operation is attempted.
    move(journal, install, archive, ready, archive, target, staged, check_roots)
    verify_file(holding, saved_name, original, allow_ctime_change=True)


def validate_plan(plan):
    if plan["format"] not in {1, 2} or not re.fullmatch(r"[0-9a-f]{32}", plan["plan_id"]):
        raise ExecutionError("Unknown adoption package format.")
    if not re.fullmatch(r"[0-9a-f]{32}", plan["job_id"]) or not plan["library_id"]:
        raise ExecutionError("Missing adoption or library identity.")
    for path in plan["directories"]:
        path_parts(path)
    paths = {"source": set(), "target": set()}
    for entry in plan["moves"]:
        for field in paths:
            path = entry[field]
            path_parts(path)
            if path in paths[field]:
                raise ExecutionError("The manifest includes a duplicate path: " + path)
            paths[field].add(path)
    for document in plan["documents"]:
        parts = path_parts(document["path"])
        if parts[-1] != "event.json" or document["path"] in paths["target"]:
            raise ExecutionError("Invalid event document destination.")
        paths["target"].add(document["path"])
    edits = plan.get("xmp_edits", [])
    if not isinstance(edits, list) or (plan["format"] == 1 and edits):
        raise ExecutionError("Invalid XMP extension in the approved manifest.")
    original_moves = {item["source"]: item for item in plan["moves"]}
    seen_edits = set()
    for edit in edits:
        source, destination = edit["source"], edit["target"]
        path_parts(source)
        path_parts(destination)
        original = original_moves.get(source)
        if (original is None or original["target"] != destination
                or not destination.casefold().endswith(".xmp")
                or source in seen_edits or
                edit["original_sha256"] != original["sha256"]):
            raise ExecutionError("XMP rewrite does not match one approved source move.")
        seen_edits.add(source)
        expected_size = edit["size_bytes"]
        if not isinstance(expected_size, int):
            raise ExecutionError("Invalid XMP output size.")
        if "patch" in edit:
            patch = edit["patch"]
            size = original["stamp"][2]
            if ("content" in edit or not isinstance(patch, dict)
                    or set(patch) != {"offset", "old", "new"}
                    or type(patch["offset"]) is not int
                    or not all(isinstance(patch[key], str) and re.fullmatch(r"(?:[0-9a-f]{2}){1,2048}", patch[key])
                               for key in ("old", "new"))
                    or not 0 < size <= 128 * 1024 * 1024):
                raise ExecutionError("Invalid streaming XMP patch.")
            old_size, new_size = len(patch["old"]) // 2, len(patch["new"]) // 2
            if (not 0 <= patch["offset"] <= size - old_size
                    or expected_size != size - old_size + new_size
                    or not re.fullmatch(r"[0-9a-f]{64}", edit["sha256"])):
                raise ExecutionError("Invalid streaming XMP patch proof.")
        else:
            if not 0 <= expected_size <= 16 * 1024 * 1024:
                raise ExecutionError("XMP rewrite exceeds the supported size limit.")
            data = base64.b64decode(edit["content"], validate=True)
            if (len(data) != expected_size or
                    hashlib.sha256(data).hexdigest() != edit["sha256"]):
                raise ExecutionError("Approved XMP rewrite checksum is inconsistent.")
    if plan["format"] == 2 and not edits:
        raise ExecutionError("The extended manifest has no bound XMP edits.")
    reserved = ".bibliothekar-adoption-" + plan["plan_id"]
    if any(path.split("/", 1)[0] == reserved for path in (*paths["target"], *plan["directories"])):
        raise ExecutionError("A planned path overlaps the protected document holding area.")


def probe_roots(source_path, archive_path, binding, source, archive):
    revalidate(binding["dataset"], source_path, archive_path, source, archive)
    if mount_id(source) != mount_id(archive):
        raise ExecutionError("Use the two native directories of the same ZFS mount on the host.")
    if any(os.fstatvfs(fd).f_flag & os.ST_RDONLY for fd in (source, archive)):
        raise ExecutionError("The supplied host directories are mounted read-only.")
    if any(not os.access(".", os.W_OK | os.X_OK, dir_fd=fd, effective_ids=True) for fd in (source, archive)):
        raise ExecutionError("The current shell user cannot modify the supplied host directories.")


def remove_empty_directory(root, path, *, expected=None):
    try:
        with relative_parent(root, path) as (parent, name, check):
            child = os.open(name, _DIRECTORY, dir_fd=parent)
            try:
                check()
                check_child(parent, name, child)
                if expected is not None and inode(os.fstat(child)) != expected:
                    raise ExecutionError("A rollback directory was replaced: " + path)
                os.rmdir(name, dir_fd=parent)
                os.fsync(parent)
            finally:
                os.close(child)
    except FileNotFoundError:
        pass


def cleanup_rollback(journal, plan, archive, directories, check_roots):
    """Remove only verified generated copies and empty, approved directories."""
    prefix = ".bibliothekar-adoption-" + plan["plan_id"]
    check_roots()
    if info_at(archive, prefix) is not None:
        staged = {f"new-{index}.json": item["sha256"] for index, item in enumerate(plan["documents"])}
        staged.update((f"new-xmp-{index}.xmp", item["sha256"])
                      for index, item in enumerate(plan.get("xmp_edits", ())))
        with relative_parent(archive, prefix + "/.directory") as (holding, _, check):
            if inode(os.fstat(holding)) != journal.proofs.get("holding"):
                raise ExecutionError("The document holding directory was replaced.")
            names = sorted(os.listdir(holding))
            if not set(names) <= staged.keys():
                raise ExecutionError("Unrestored originals or unknown files remain in the holding directory.")
            for name in names:
                check_roots()
                with file_at(holding, name) as (fd, info):
                    if hash_fd(fd) != staged[name]:
                        raise ExecutionError("A generated rollback file changed: " + name)
                check()
                current = info_at(holding, name)
                if current is None or stamp(current) != stamp(info):
                    raise ExecutionError("A generated rollback file changed: " + name)
                os.unlink(name, dir_fd=holding)
                os.fsync(holding)
        remove_empty_directory(archive, prefix, expected=journal.proofs["holding"])

    for path in sorted(directories, key=lambda p: (-p.count("/"), p)):
        check_roots()
        remove_empty_directory(archive, path)


def execute(package, binding, plan, source_path, archive_path, *, reverse, rollback_directories=None):
    validate_plan(plan)
    direction = "rollback" if reverse else "apply"
    completed = "rolled_back" if reverse else "completed"

    def status(state, processed, *, error=None):
        result = {"manifest": binding, "state": state, "mode": direction, "processed": processed,
                  "total": len(plan["moves"]) + len(plan["documents"]) + len(plan.get("xmp_edits", []))}
        if error:
            result["error"] = str(error)
        write_atomic(package, "status.json", json_bytes(result))

    processed = 0
    try:
        with ExitStack() as stack:
            source = stack.enter_context(directory(source_path, plan["source_inode"]))
            archive = stack.enter_context(directory(archive_path, plan["archive_inode"]))

            def check_roots():
                with directory(source_path, plan["source_inode"]) as actual_source, \
                        directory(archive_path, plan["archive_inode"]) as actual_archive:
                    if (mount_id(source) != mount_id(actual_source)
                            or mount_id(archive) != mount_id(actual_archive)):
                        raise ExecutionError("An approved host path changed mounts.")
                    probe_roots(source_path, archive_path, plan, actual_source, actual_archive)

            check_roots()
            journal = stack.enter_context(Journal(package, binding))
            if not reverse and journal.direction in {"rollback", "rolled_back"}:
                raise ExecutionError("Rollback was already started. This package can only finish rollback.")
            journal.append(None, direction)
            status("running", processed)
            if reverse and journal.latest.get("rollback-cleanup") == "media_restored":
                if rollback_directories is None:
                    raise ExecutionError("The rollback cleanup scope is missing.")
                cleanup_rollback(journal, plan, archive, rollback_directories, check_roots)
                journal.append(None, completed)
                status(completed, len(plan["moves"]) + len(plan["documents"]) + len(plan.get("xmp_edits", ())))
                return

            if not reverse:
                for path in plan["directories"]:
                    check_roots()
                    with relative_parent(archive, path + "/.directory", create=True):
                        pass

            holding = None
            prefix = ".bibliothekar-adoption-" + plan["plan_id"]
            if plan["documents"] or plan.get("xmp_edits"):
                holding_state = journal.latest.get("holding")
                current = info_at(archive, prefix)
                if holding_state is None and not reverse:
                    if current is not None:
                        raise ExecutionError("The reserved document holding path already exists.")
                    journal.append("holding", "directory_intent")
                    holding_state = "directory_intent"
                if holding_state is not None and (current is not None or not reverse):
                    holding, _, check_holding = stack.enter_context(
                        relative_parent(archive, prefix + "/.directory", create=holding_state == "directory_intent"),
                    )
                    check_holding()
                    actual = inode(os.fstat(holding))
                    if holding_state == "directory_intent":
                        if os.listdir(holding):
                            raise ExecutionError("The unconfirmed document holding directory is not empty.")
                        journal.append("holding", "directory_ready", proof=actual)
                    elif actual != journal.proofs["holding"]:
                        raise ExecutionError("The document holding directory was replaced.")

            def documents():
                if holding is None:
                    if reverse and any(operation.startswith(("document:", "original-document:"))
                                       for operation in journal.latest):
                        raise ExecutionError("The holding directory for event documents is missing.")
                    return
                nonlocal processed
                indexes = range(len(plan["documents"]))
                for index in reversed(indexes) if reverse else indexes:
                    check_roots()
                    check_holding()
                    apply_document(journal, plan["documents"][index], archive, holding,
                                   prefix, index, check_roots, reverse)
                    processed += 1
                    status("running", processed)

            edits = plan.get("xmp_edits", [])
            move_by_source = {item["source"]: item for item in plan["moves"]}
            edited_sources = {item["source"] for item in edits}

            def xmp_edits():
                nonlocal processed
                if holding is None:
                    if edits and (not reverse or any(
                        operation.startswith(("media:xmp-save:", "media:xmp-install:")) for operation in journal.latest
                    )):
                        raise ExecutionError("The XMP backup holding directory is missing.")
                    return
                indexes = range(len(edits))
                for index in reversed(indexes) if reverse else indexes:
                    item = edits[index]
                    original_operation = "media:" + item["source"]
                    # After rollback of a complete XMP swap, the original
                    # media is at its source name; never replay the swap.
                    if reverse and journal.latest.get(original_operation) in {
                        "reverse_intent", "reverse_done"
                    }:
                        continue
                    check_roots()
                    check_holding()
                    apply_xmp_edit(
                        journal, item, move_by_source[item["source"]],
                        archive, holding, prefix, index, check_roots, reverse=reverse,
                    )
                    processed += 1
                    status("running", processed)

            if reverse:
                documents()
                xmp_edits()
            items = reversed(plan["moves"]) if reverse else plan["moves"]
            for item in items:
                check_roots()
                operation = "media:" + item["source"]
                if reverse:
                    move(journal, operation, archive, item["target"], source, item["source"],
                         item, check_roots, reverse=True)
                else:
                    # The unmodified sidecar is now saved in the recovery
                    # holding directory (or its swap has completed). Replaying
                    # the original move would compare it to the edited bytes.
                    edit_index = next(
                        (i for i, entry in enumerate(edits)
                         if entry["source"] == item["source"]), None,
                    )
                    if (edit_index is None or
                            journal.latest.get(f"media:xmp-save:{edit_index}") is None):
                        move(journal, operation, source, item["source"],
                             archive, item["target"], item, check_roots)
                processed += 1
                status("running", processed)
            if not reverse:
                xmp_edits()
                documents()
            elif rollback_directories is not None:
                journal.append("rollback-cleanup", "media_restored")
                cleanup_rollback(journal, plan, archive, rollback_directories, check_roots)
            check_roots()
            journal.append(None, completed)
            status(completed, processed)
    except (OSError, DatasetError, ExecutionError, ValueError, KeyError, TypeError) as error:
        status("attention_required", processed, error=error)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "apply", "rollback"))
    parser.add_argument("--package", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--package-device", type=int, required=True)
    parser.add_argument("--package-inode", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{64}", args.sha256):
            raise ExecutionError("Invalid package digest.")
        with directory(args.package, [args.package_device, args.package_inode]) as package, package_lock(package):
            name = "probe.json" if args.mode == "probe" else "manifest.json"
            content = read_bytes(package, name)
            if hashlib.sha256(content).hexdigest() != args.sha256:
                raise ExecutionError("The package digest differs from the approved command.")
            binding = json.loads(content)
            if args.mode == "probe":
                if binding["host"] != {"package": args.package, "source": args.source, "archive": args.archive}:
                    raise ExecutionError("The host paths differ from the requested probe.")
                with directory(args.source, binding["source_inode"]) as source, \
                        directory(args.archive, binding["archive_inode"]) as archive:
                    probe_roots(args.source, args.archive, binding, source, archive)
                    write_atomic(package, "host-proof.json", json_bytes({
                        "probe": args.sha256, "package": args.package,
                        "source": args.source, "archive": args.archive,
                    }))
            else:
                if binding["host"] != {"package": args.package, "source": args.source, "archive": args.archive}:
                    raise ExecutionError("The host paths differ from the confirmed manifest.")
                permission = json.loads(read_bytes(package, "permission.json"))
                reverse = args.mode == "rollback"
                expected = {"manifest": args.sha256, "mode": args.mode}
                cleanup_paths = None
                if reverse and "rollback_directories" in permission:
                    cleanup_paths = permission["rollback_directories"]
                    if (not isinstance(cleanup_paths, list) or not all(isinstance(item, str) for item in cleanup_paths)
                            or not set(cleanup_paths) <= set(binding["directories"])):
                        raise ExecutionError("Invalid rollback directory scope.")
                    expected["rollback_directories"] = cleanup_paths
                if permission != expected:
                    raise ExecutionError("This action has not been released by Bibliothekar.")
                execute(package, args.sha256, binding, args.source, args.archive, reverse=reverse,
                        rollback_directories=cleanup_paths)
    except (OSError, DatasetError, ExecutionError, KeyError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
