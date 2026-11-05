"""HTTP smoke test against the disposable runner container, never a NAS."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.request

base = 'http://127.0.0.1:18080'
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
for attempt in range(60):
    try:
        response = client.open(base + '/healthz', timeout=5)
        assert response.status == 200
        break
    except (OSError, AssertionError):
        if attempt == 59:
            raise
        time.sleep(1)
try:
    client.open(base + '/auth/status', timeout=5)
    raise AssertionError('Anonymous API access must be rejected')
except urllib.error.HTTPError as error:
    assert error.code == 401
body = json.dumps({'password': 'synthetic-rc-build-smoke-password'}).encode()
request = urllib.request.Request(base + '/auth/login', data=body,
                                headers={'Content-Type': 'application/json', 'Origin': base})
with client.open(request, timeout=5) as response:
    assert response.status == 200
    assert json.load(response)['authenticated'] is True
with client.open(base + '/auth/status', timeout=5) as response:
    assert response.status == 200
    json.load(response)
print('PASS: fresh container health, anonymous rejection, owner login, authenticated API')
