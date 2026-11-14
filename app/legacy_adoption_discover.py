"""Resolve one prepared adoption from native Linux mounts and write its host proof."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import PurePosixPath
import stat
import sys
from types import ModuleType


# The privileged launcher runs only the helper bytes pinned by Bibliothekar.
_LOADER = '''import hashlib,os,stat,sys
from pathlib import Path
def run(p,dev,ino,checksum,mode,args):
 try:
  s=p.lstat()
  if str(s.st_ino)!=ino or f"{os.major(s.st_dev)}:{os.minor(s.st_dev)}"!=dev or not stat.S_ISDIR(s.st_mode):return
  with os.fdopen(os.open(p/"legacy_adoption_discover.py",os.O_NOFOLLOW|os.O_NONBLOCK),"rb") as f:
   if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):return
   code=f.read(16384)
 except OSError:return
 if hashlib.sha256(code).hexdigest()==checksum:
  scope={"__name__":"legacy_adoption_discover"}
  exec(code,scope)
  sys.exit(scope[mode](str(p),[s.st_dev,s.st_ino],*args))
'''
_DISCOVER = '''import json,subprocess
root,dev,ino,checksum,probe=sys.argv[1:]
try:mounts=json.loads(subprocess.check_output(["findmnt","-Jlo","TARGET,FSROOT,MAJ:MIN"],timeout=15))["filesystems"]
except (OSError,ValueError,subprocess.SubprocessError):sys.exit("Host check failed: run this command in the TrueNAS host shell with findmnt available.")
mounts=[m for m in mounts if m["maj:min"]==dev and m["fsroot"] and m["target"]]
for m in sorted(mounts,key=lambda m:len(Path(m["fsroot"]).parts)):
 if Path(root).is_relative_to(m["fsroot"]):
  run(Path(m["target"])/Path(root).relative_to(m["fsroot"]),dev,ino,checksum,"check",[probe])
'''
_DIRECT = '''path,dev,ino,checksum,*args=sys.argv[1:]
run(Path(path),dev,ino,checksum,"execute",args)
'''
_NO_PACKAGE = 'sys.exit("Approved AppData package not found or changed. Check the command in Bibliothekar and run it on the TrueNAS host.")'


def bootstrap(*, automatic=True):
    program = _LOADER + (_DISCOVER if automatic else _DIRECT) + _NO_PACKAGE
    return f"exec({program!r})"


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


def resolve_media(host, binding, mounts):
    proof = binding["dataset"]
    source = PurePosixPath(proof["source_directory"])
    archive = PurePosixPath(proof["archive_directory"])
    last_error = None
    for mount in sorted(mounts, key=lambda item: (len(item.root.parts), len(item.target.parts), item.target)):
        if (mount.filesystem, mount.source, mount.device) != ("zfs", proof["dataset"], proof["device"]):
            continue
        if not (source.is_relative_to(mount.root) and archive.is_relative_to(mount.root)):
            continue
        source_path = str(mount.target / source.relative_to(mount.root))
        archive_path = str(mount.target / archive.relative_to(mount.root))
        try:
            with host.directory(source_path, binding["source_inode"]) as src, \
                    host.directory(archive_path, binding["archive_inode"]) as dst:
                host.probe_roots(source_path, archive_path, binding, src, dst)
                return source_path, archive_path
        except (OSError, host.DatasetError, host.ExecutionError) as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise ValueError("No native ZFS mount contains both approved folders. Check the archive and source mounts.")


def verify(package_path, identity, digest, checksums):
    with ExitStack() as stack:
        package = open_package(stack, package_path, identity)
        host = load_runner(package, checksums)
        dataset = sys.modules["legacy_adoption_dataset"]
        with host.package_lock(package):
            content = host.read_bytes(package, "probe.json")
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("This check command belongs to an older plan.")
            binding = json.loads(content)
            if binding["host"] is not None or not binding.get("package_mount"):
                raise ValueError("This package was not prepared for automatic host discovery.")
            try:
                source, archive = resolve_media(host, binding, dataset.mount_table().values())
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
                host.write_atomic(package, "host-check-error.json", host.json_bytes({
                    "probe": digest, "detail": str(error),
                }))
                raise
            host.write_atomic(package, "host-proof.json", host.json_bytes({
                "probe": digest, "package": package_path, "source": source, "archive": archive,
            }))
            try:
                os.unlink("host-check-error.json", dir_fd=package)
            except FileNotFoundError:
                pass
            else:
                os.fsync(package)


def check(package_path, identity, digest):
    try:
        verify(package_path, identity, digest, RUNNER_CHECKSUMS)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print(f"Host check failed: {error}", file=sys.stderr)
        return 1
    print("Host paths and ZFS dataset verified. Return to Bibliothekar and read the proof.")
    return 0


def execute(package_path, identity, mode, digest, source, archive):
    try:
        with ExitStack() as stack:
            package = open_package(stack, package_path, identity)
            host = load_runner(package, RUNNER_CHECKSUMS)
        result = host.main([
            mode, "--package", package_path, "--source", source, "--archive", archive, "--sha256", digest,
            "--package-device", str(identity[0]), "--package-inode", str(identity[1]),
        ])
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print(f"Adoption command failed: {error}", file=sys.stderr)
        return 1
    if result == 0:
        print({"probe": "Host paths and ZFS dataset verified. Return to Bibliothekar and read the proof.",
               "apply": "File operations complete. Return to Bibliothekar to verify the archive.",
               "rollback": "Rollback operations complete. Return to Bibliothekar to verify the rollback."}[mode])
    return result
