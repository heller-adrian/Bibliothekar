"""Opt-in local browser fixture: pytest -s tests/backend/rc2_ui_review.py.

All media, configuration, registry and HTTP data live in pytest's temp folder.
Dataset and EXIF proofs are synthetic; this is not ZFS release qualification.
The server binds loopback only and stops on POST /__stop-review.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Thread

from fastapi.testclient import TestClient

from app import main
from tests.backend.test_rc2_archive_finish_recovery import deletion
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


def test_browser_review(deletion, synthetic_dataset, tmp_path, tmp_path_factory, monkeypatch):
    db, workspace, archive, _, _, _ = deletion
    # Use the regular wizard/API with an isolated new source and known metadata.
    # The previously confirmed archive deletion is not exercised by this fixture.
    from app.database import database_connection
    with database_connection(db) as connection:
        connection.execute("DELETE FROM event_change_requests")
    source = tmp_path_factory.mktemp('rc2-ui-source').resolve()
    from datetime import date, timedelta
    for index in range(20):
        day = date(2026, 7, 15) + timedelta(days=index)
        folder = source / day.isoformat()
        folder.mkdir()
        for member in range(3):
            (folder / f'synthetic-{member}.JPG').write_bytes(day.strftime('%Y:%m:%d').encode() + b' 12:00:00 synthetic UI bytes')
    monkeypatch.setattr(main, 'NAS_SOURCE_ROOT', source)
    monkeypatch.setattr('app.legacy_adoption_inventory.read_bound_metadata',
                        lambda descriptors, _cancel: {fd: {'EXIF:ExifIFD:DateTimeOriginal': os.pread(fd, 19, 0).decode()} for fd in descriptors})
    client = TestClient(main.app)
    created = client.post('/api/legacy-adoption/jobs', json={'root': 'nas'})
    assert created.status_code == 201, created.text
    job = created.json()['id']
    scanned = client.post('/api/legacy-adoption/jobs/' + job + '/scan')
    assert scanned.status_code == 202, scanned.text
    assert client.get('/api/legacy-adoption/jobs/' + job).json()['state'] == 'inventoried'

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
            if self.path.startswith('/legacy-adoption'):
                import importlib
                from app import legacy_adoption_i18n, ui_i18n, ui_shell, legacy_adoption_ui
                for module in (ui_i18n, legacy_adoption_i18n, ui_shell, legacy_adoption_ui):
                    importlib.reload(module)
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
    url = f'http://127.0.0.1:{server.server_port}/legacy-adoption?library=main&job={job}&step=plan'
    Path('/private/tmp/bibliothekar-rc2-ui-review.json').write_text(json.dumps({'url': url, 'port': server.server_port,
                                                                           'job': job, 'fixture_root': str(tmp_path)}))
    print('SYNTHETIC_BROWSER_REVIEW_READY', url, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
