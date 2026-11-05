"""Loopback-only Chromium tunnel into a fully internal Docker QA network.

Docker --internal does not guarantee a published host port even when -p is
specified. Serve an AF_UNIX socket inside the *isolated* QA container and
forward it from an ephemeral 127.0.0.1-only host port. No external networking,
product code or application authentication is changed.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import select
import socket
import socketserver
import threading
import time


_SOCKET_NAME = ".pre4-chromium-tunnel.sock"

# Only executed as UID 568 in the synthetic, temporary QA container.
_CONTAINER_SIDE = r'''
import os, select, socket, socketserver
PATH = "/workspace/.pre4-chromium-tunnel.sock"

def relay(left, right):
    sockets = (left, right)
    while True:
        readable, _, _ = select.select(sockets, [], [], 60)
        if not readable:
            return
        for src in readable:
            data = src.recv(65536)
            if not data:
                return
            dst = right if src is left else left
            dst.sendall(data)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.create_connection(("127.0.0.1", 8080), timeout=15) as upstream:
            try:
                relay(self.request, upstream)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

with Server(PATH, Handler) as server:
    os.chmod(PATH, 0o666)  # QA_WORK directory above this socket is mode 0700.
    server.serve_forever(poll_interval=0.1)
'''


def _relay(left, right):
    sockets = (left, right)
    while True:
        readable, _, _ = select.select(sockets, [], [], 60)
        if not readable:
            return
        for src in readable:
            data = src.recv(65536)
            if not data:
                return
            dst = right if src is left else left
            dst.sendall(data)


class _HostHandler(socketserver.BaseRequestHandler):
    def handle(self):
        upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            upstream.connect(self.server.unix_path)
            _relay(self.request, upstream)
        except (BrokenPipeError, ConnectionResetError, OSError) as error:
            # Browser tests will also fail; retain useful diagnostics.
            print("QA Chromium tunnel:", type(error).__name__, str(error), flush=True)
        finally:
            upstream.close()


class _LoopbackServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


@contextmanager
def chromium_loopback_tunnel(docker, container, fixture_workspace):
    """Loopback-only browser bridge. Linux AF_UNIX names max out near 108 bytes.

    GitHub Runner temp paths are longer; the open directory descriptor gives
    us a short, same-inode /proc/self/fd path without modifying global cwd.
    """
    workspace = Path(fixture_workspace)
    socket_path = workspace / _SOCKET_NAME
    assert not socket_path.exists(), "Unexpected pre-existing QA bridge socket"
    directory_fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        short_socket_path = f"/proc/self/fd/{directory_fd}/{_SOCKET_NAME}"
        assert len(os.fsencode(short_socket_path)) < 100
        docker("exec", "-d", "--user", "568:568", container,
               "python", "-c", _CONTAINER_SIDE)
        ready = False
        for _ in range(100):
            if socket_path.is_socket():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                        probe.settimeout(1)
                        probe.connect(short_socket_path)
                    ready = True
                    break
                except (ConnectionRefusedError, FileNotFoundError):
                    pass
            time.sleep(0.1)
        assert ready, "Internal Unix socket for Chromium was not created by QA container"
        with _LoopbackServer(("127.0.0.1", 0), _HostHandler) as server:
            server.unix_path = short_socket_path
            thread = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                yield server.server_address[1]
            finally:
                server.shutdown()
                thread.join(timeout=10)
    finally:
        os.close(directory_fd)
