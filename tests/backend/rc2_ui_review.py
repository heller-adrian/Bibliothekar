"""Opt-in local browser fixture: pytest -s tests/backend/rc2_ui_review.py.

All media, configuration, registry and HTTP data live in pytest's temp folder.
Dataset and EXIF proofs are synthetic; this is not ZFS release qualification.
The server binds loopback only and stops on POST /__stop-review.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
from pathlib import Path
from threading import Thread

from fastapi.testclient import TestClient

from app import main
from tests.backend.test_legacy_adoption_integration import fresh_main
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


def test_browser_review(fresh_main, synthetic_dataset, tmp_path, tmp_path_factory, monkeypatch):
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None
    appdata = tmp_path / "script-appdata"
    appdata.mkdir()
    monkeypatch.setattr("app.legacy_adoption_package.appdata_root", lambda: appdata)
    if sys.platform == "darwin":
        monkeypatch.setattr("app.legacy_adoption_host.mount_id", lambda _: 1)
    source = tmp_path_factory.mktemp('rc2-ui-source').resolve()
    from datetime import date, timedelta
    for index in range(20):
        day = date(2026, 7, 15) + timedelta(days=index)
        folder = source / ('camera-' + str(index % 3)) / ('import-' + str(index))
        folder.mkdir(parents=True)
        for member in range(3):
            (folder / f'synthetic-{member}.JPG').write_bytes(day.strftime('%Y:%m:%d').encode() + f' 12:00:00 synthetic UI bytes {member}'.encode())
    monkeypatch.setattr(main, 'NAS_SOURCE_ROOT', source)
    monkeypatch.setattr('app.legacy_adoption_inventory.read_bound_metadata',
                        lambda descriptors, _cancel: {fd: {'EXIF:ExifIFD:DateTimeOriginal': os.pread(fd, 19, 0).decode()} for fd in descriptors})
    client = TestClient(main.app)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.forward()

        def do_POST(self):
            if self.path == '/__stop-review':
                self.send_response(200)
                self.end_headers()
                Thread(target=server.shutdown, daemon=True).start()
            else:
                self.forward()

        def do_PUT(self):
            self.forward()

        def do_DELETE(self):
            self.forward()

        def forward(self):
            if self.path == '/auth/client.js':
                from app.security import _client_code
                script = _client_code().encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(script)))
                self.end_headers()
                self.wfile.write(script)
                return
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            headers = {key: value for key, value in self.headers.items() if key.lower() not in {'host', 'connection', 'content-length'}}
            response = client.request(self.command, self.path, content=body or None, headers=headers,
                                      follow_redirects=False)
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() not in {'content-length', 'transfer-encoding', 'connection', 'content-encoding'}:
                    self.send_header(key, value)
            self.send_header('Content-Length', str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = f'http://127.0.0.1:{server.server_port}/'
    Path('/private/tmp/bibliothekar-rc2-ui-review.json').write_text(json.dumps({
        'url': url, 'port': server.server_port, 'archive': str(fresh_main[3]), 'fixture_root': str(tmp_path),
    }))
    print('SYNTHETIC_BROWSER_REVIEW_READY', url, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
