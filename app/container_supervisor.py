from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable


WEB_UID = int(os.environ.get("KAMERA_WEB_UID", "568"))
WEB_GID = int(os.environ.get("KAMERA_WEB_GID", "568"))
HELPER_ENABLED = os.environ.get("KAMERA_SOURCE_HELPER_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def web_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]


def helper_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.source_helper:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8090",
    ]


def _drop_web_privileges() -> None:
    if os.geteuid() != 0:
        return
    os.setgroups([])
    os.setgid(WEB_GID)
    os.setuid(WEB_UID)


def _web_preexec() -> Callable[[], None] | None:
    return _drop_web_privileges if os.geteuid() == 0 else None


def _terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()


def run() -> int:
    if HELPER_ENABLED and os.geteuid() != 0:
        print(
            "KAMERA_SOURCE_HELPER_ENABLED=true benoetigt einen als root gestarteten Container.",
            file=sys.stderr,
            flush=True,
        )
        return 64

    helper: subprocess.Popen[bytes] | None = None
    web: subprocess.Popen[bytes] | None = None
    stopping = False

    def stop(_signum: int, _frame) -> None:
        nonlocal stopping
        stopping = True
        _terminate(web)
        _terminate(helper)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        if HELPER_ENABLED:
            helper = subprocess.Popen(helper_command())

        web = subprocess.Popen(
            web_command(),
            preexec_fn=_web_preexec(),
        )

        while True:
            web_rc = web.poll()
            helper_rc = helper.poll() if helper is not None else None

            if web_rc is not None:
                _terminate(helper)
                return int(web_rc)

            if helper is not None and helper_rc is not None:
                print(
                    f"Der Quellen-Helper wurde unerwartet beendet (Exit {helper_rc}).",
                    file=sys.stderr,
                    flush=True,
                )
                _terminate(web)
                return int(helper_rc or 1)

            if stopping:
                return 0

            time.sleep(0.25)
    finally:
        _terminate(web)
        _terminate(helper)
        for process in (web, helper):
            if process is None:
                continue
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(run())
