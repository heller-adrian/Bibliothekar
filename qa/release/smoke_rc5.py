"""Fresh RC5 container smoke; loopback only, synthetic password and datasets."""
import http.cookiejar
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from check_web_assets import check_pages

version = json.loads(Path('qa/release/rc5.json').read_text())['version']
base = 'http://127.0.0.1:18080'
output = Path(os.environ['RC5_EVIDENCE'])
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
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
# A new container deliberately has no registered library. Exercise the actual
# onboarding APIs with the real session/CSRF guard before expecting normal UI.
def json_request(path, *, payload=None, status=200):
    headers = {'Origin': base}
    if payload is not None:
        csrf = next(cookie.value for cookie in cookies if cookie.name == 'bibliothekar_csrf')
        headers.update({'Content-Type': 'application/json', 'X-Bibliothekar-CSRF': csrf})
    request = urllib.request.Request(base + path,
        data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    try:
        response = client.open(request, timeout=20)
    except urllib.error.HTTPError as error:
        (output/'onboarding-api-error.json').write_text(json.dumps({
            'path': path, 'status': error.code, 'body': error.read().decode()}))
        raise
    with response:
        body = json.load(response)
        (output/('api-' + path.strip('/').replace('/', '-') + ('-post' if payload is not None else '-get') + '.json')).write_text(json.dumps(body, indent=2))
        assert response.status == status, (path, response.status, body)
        return body

storage = json_request('/api/settings/storage-health')
assert storage['ready'], storage
assert json_request('/api/libraries')['libraries'] == []
with client.open(base + '/', timeout=20) as response:
    onboarding = response.read().decode()
    (output/'onboarding.html').write_text(onboarding)
    assert response.status == 200 and 'text/html' in response.headers['Content-Type']
    assert '<html' in onboarding
    assert 'id="create"' in onboarding and 'id="archive"' in onboarding
    assert '/api/libraries/check' in onboarding and '/api/libraries' in onboarding
onboarding_assets = check_pages({'onboarding': onboarding}, output/'onboarding-assets')
checked = json_request('/api/libraries/check', payload={
    'work_root': '', 'archive_root': '/main-library', 'default_library_id': 'rc5-smoke'})
assert checked['valid'] and checked['archive_read_only'], checked
assert checked['archive_root'] == '/main-library'
assert checked['work_root'] == '/workspace/Library Workspaces/rc5-smoke'
created = json_request('/api/libraries', status=201, payload={
    'display_name': 'RC5 Smoke', 'work_root': '', 'archive_root': '/main-library'})['library']
assert created['library_id'] == 'main' and created['is_registered'] and created['is_active'], created
assert created['display_name'] == 'RC5 Smoke'
assert created['work_root'] == checked['work_root'] and created['archive_root'] == checked['archive_root']
assert json_request('/api/libraries')['libraries'] == [created]
health = json_request('/api/health')
assert health['version'] == version and health['deployment_version'] == version, health
(output/'onboarding-result.json').write_text(json.dumps({
    'state': 'PASS', 'initial_registered_libraries': 0, 'library': created,
    'archive_read_only': checked['archive_read_only'], 'assets': onboarding_assets}, indent=2))
pages = {}
for name, path in {'import':'/', 'workspace':'/workspace', 'events':'/events',
                   'archive':'/transfer', 'metadata':'/metadata-correction', 'trash':'/trash'}.items():
    with client.open(base + path, timeout=20) as response:
        assert response.status == 200
        assert 'text/html' in response.headers['Content-Type']
        pages[name] = response.read().decode()
        (output/(name + '.html')).write_text(pages[name])
        assert '<html' in pages[name] and version in pages[name]
result = {'version': version, 'health': 'PASS', 'anonymous_rejected': 'PASS',
          'owner_login': 'PASS', 'authenticated_session': 'PASS',
          'onboarding': 'PASS', 'library_id': created['library_id'], 'api_version': health['version'],
          'delivered_ui': check_pages(pages, output/'delivered-assets')}
(output/'container-smoke.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
