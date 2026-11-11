"""Read Docker mount metadata on the NAS and record a qualified host proof."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import subprocess
import sys
from types import ModuleType


def host_path(path, mounts):
    path = PurePosixPath(path)
    candidates = []
    for mount in mounts:
        destination = PurePosixPath(mount["Destination"])
        if path.is_relative_to(destination):
            source = mount.get("Source")
            native = None
            if mount["Type"] in {"bind", "volume"} and source and source.startswith("/"):
                native = str(PurePosixPath(source) / path.relative_to(destination))
            candidates.append((len(destination.parts), native))
    if not candidates:
        return None
    depth = max(length for length, _ in candidates)
    matches = {native for length, native in candidates if length == depth}
    return matches.pop() if len(matches) == 1 else None


def mount_groups():
    ids = subprocess.check_output(["docker", "ps", "--quiet", "--no-trunc"], text=True, timeout=15).split()
    if not ids or not all(re.fullmatch(r"[a-f0-9]{64}", value) for value in ids):
        raise ValueError("No running Docker container was found.")
    lines = subprocess.check_output(
        ["docker", "inspect", "--type", "container", "--format", "{{json .Mounts}}", *ids],
        text=True, timeout=15,
    ).splitlines()
    return [json.loads(line) or [] for line in lines]


def discover(container, identity, groups):
    candidates = set()
    for mounts in groups:
        package = host_path(container["package"], mounts)
        if package is None:
            continue
        try:
            info = os.stat(package, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if [info.st_dev, info.st_ino] != identity or not stat.S_ISDIR(info.st_mode):
            continue
        candidates.add((package, host_path(container["source"], mounts), host_path(container["archive"], mounts)))
    if len(candidates) != 1 or None in next(iter(candidates)):
        raise ValueError("The Docker mounts do not identify one complete host mapping for this package.")
    return dict(zip(("package", "source", "archive"), candidates.pop()))


def open_package(stack, path, identity):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root = os.open("/", flags)
    stack.callback(os.close, root)
    for part in PurePosixPath(path).parts[1:]:
        if part == "..":
            raise ValueError("Unsafe package path.")
        root = os.open(part, flags, dir_fd=root)
        stack.callback(os.close, root)
    info = os.fstat(root)
    if [info.st_dev, info.st_ino] != identity:
        raise ValueError("The package directory has changed.")
    return root


def load_runner(package, checksums):
    for name, digest in checksums.items():
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=package)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("The package script is not a regular file.")
            code = handle.read(256 * 1024)
        if hashlib.sha256(code).hexdigest() != digest:
            raise ValueError("The package script does not match Bibliothekar's check command.")
        module = ModuleType(name.removesuffix(".py"))
        sys.modules[module.__name__] = module
        exec(compile(code, name, "exec"), module.__dict__)
    return sys.modules["legacy_adoption_host"]


def main(config, groups=None):
    expected = config["identity"]
    paths = discover(config["container"], expected, mount_groups() if groups is None else groups)
    with ExitStack() as stack:
        package = open_package(stack, paths["package"], expected)
        host = load_runner(package, config["scripts"])
        with host.package_lock(package):
            content = host.read_bytes(package, "probe.json")
            if hashlib.sha256(content).hexdigest() != config["probe"]:
                raise ValueError("This check command belongs to an older plan.")
            binding = json.loads(content)
            if binding["container"] != config["container"] or binding["host"] is not None:
                raise ValueError("The prepared package does not match the selected paths.")
            source = stack.enter_context(host.directory(paths["source"], binding["source_inode"]))
            archive = stack.enter_context(host.directory(paths["archive"], binding["archive_inode"]))
            host.probe_roots(paths["source"], paths["archive"], binding, source, archive)
            host.write_atomic(package, "host-proof.json", host.json_bytes({"probe": config["probe"], **paths}))


if __name__ == "__main__":
    try:
        main(json.loads(sys.argv[1]))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        sys.exit(f"Host check failed: {error}\nCheck the Docker mounts and shell access, or use the manual host mapping in Bibliothekar.")
    print("Host paths and ZFS dataset verified. Return to Bibliothekar and read the proof.")
