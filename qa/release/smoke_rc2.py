"""Fresh RC2 container smoke; loopback only, synthetic password and datasets."""
import http.cookiejar
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from check_web_assets import check_pages

version = json.loads(Path('qa/release/rc2.json').read_text())['version']
base = 'http://127.0.0.1:18080'
output = Path(os.environ['RC2_EVIDENCE'])
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
for attempt in range(60):
    try:
        with client.open(base + '/healthz', timeout=5) as response:
            assert response.status == 200
        break
    except (OSError, AssertionError):
        if attempt == 59: raise
        time.sleep(1)
try:
    client.open(base + '/auth/status', timeout=5)
    raise AssertionError('Anonymous API access accepted')
except urllib.error.HTTPError as error:
    assert error.code == 401
request = urllib.request.Request(base + '/auth/login',
    data=json.dumps({'password':'synthetic-rc-build-smoke-password'}).encode(),
    headers={'Content-Type':'application/json','Origin':base})
with client.open(request, timeout=5) as response:
    assert response.status == 200 and json.load(response)['authenticated']
with client.open(base + '/auth/status', timeout=5) as response:
    assert response.status == 200
pages = {}
for name, path in {'import':'/', 'workspace':'/workspace', 'events':'/events',
                   'archive':'/transfer', 'metadata':'/metadata-correction', 'trash':'/trash'}.items():
    with client.open(base + path, timeout=20) as response:
        assert response.status == 200
        assert 'text/html' in response.headers['Content-Type']
        pages[name] = response.read().decode()
        assert '<html' in pages[name] and version in pages[name]
result = {'version': version, 'health': 'PASS', 'anonymous_rejected': 'PASS',
          'owner_login': 'PASS', 'authenticated_session': 'PASS',
          'delivered_ui': check_pages(pages, output/'delivered-assets')}
(output/'container-smoke.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
