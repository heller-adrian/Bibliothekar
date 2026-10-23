"""Focused output encoding and real streamed login-size regressions."""
import asyncio
from html.parser import HTMLParser
import json
import subprocess

import pytest
from starlette.requests import Request

from app import security
from app.transfer_ui import TRANSFER_HTML


@pytest.mark.parametrize("label", [
    '<b data-audit="harmless">Synthetic & text</b>',
    '<script>window.syntheticAuditMarker=1</script>',
    '\"><img src=x onerror="window.syntheticAuditMarker=1">',
    "ordinary title / Ä & ' quoted",
])
def test_f25_task_text_is_preserved_without_markup(label):
    begin = TRANSFER_HTML.index('async function refreshGlobalTasks()')
    end = TRANSFER_HTML.index('\n    document.getElementById("global-task-fab")', begin)
    script = r'''
const vm=require('vm'),fs=require('fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const panel={innerHTML:''},el={classList:{add(){},toggle(){}},textContent:''};
const ctx={document:{getElementById:id=>id==='global-task-panel'?panel:el},
 fetch:async()=>({json:async()=>({tasks:[input.task],count:1})})};
(async()=>{await vm.runInNewContext(input.code+';refreshGlobalTasks()',ctx);
process.stdout.write(panel.innerHTML)})().catch(e=>{throw e});
'''
    result = subprocess.run(['node', '-e', script], input=json.dumps({
        'code': TRANSFER_HTML[begin:end],
        'task': {'title': label, 'detail': label, 'href': '/events?x=1&y="q"'},
    }), capture_output=True, text=True, timeout=5, check=True)

    class Fragment(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.tags, self.text, self.links = [], [], []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            if tag == 'a':
                self.links.append(dict(attrs))

        def handle_data(self, data):
            self.text.append(data)

    parsed = Fragment()
    parsed.feed(result.stdout)
    assert parsed.tags == ['strong', 'a', 'strong', 'span']
    assert ''.join(parsed.text) == 'Offene Aufgaben · 1' + label + label
    assert parsed.links == [{'class': 'global-task-item', 'href': '/events?x=1&y="q"'}]


@pytest.mark.parametrize('size,chunk_size,length,expected', [
    (100, 100, None, 200),
    (100, 7, None, 200),
    (16384, 1024, None, 200),
    (16384, 333, '1', 200),
    (16385, 1024, None, 413),
    (17052, 8000, None, 413),
    (20000, 20000, '0', 413),
    (20000, 1024, '1', 413),
    (100, 100, '20000', 413),
])
def test_f28_received_login_bytes_are_bounded(monkeypatch, size, chunk_size, length, expected):
    secret = 'synthetic-owner-password-123456'
    monkeypatch.delenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS', raising=False)
    monkeypatch.delenv('BIBLIOTHEKAR_ADMIN_PASSWORD_FILE', raising=False)
    monkeypatch.setenv('BIBLIOTHEKAR_ADMIN_PASSWORD', secret)
    security._SESSIONS.clear()
    security._FAILURES.clear()
    assert not security._is_test_bypass()
    body = json.dumps({'password': secret}).encode()
    body += b' ' * (size - len(body))
    chunks = [body[n:n + chunk_size] for n in range(0, len(body), chunk_size)]
    headers = [(b'host', b'testserver'), (b'origin', b'http://testserver'),
               (b'content-type', b'application/json')]
    if length is not None:
        headers.append((b'content-length', length.encode()))
    else:
        headers.append((b'transfer-encoding', b'chunked'))
    delivered = []

    async def receive():
        index = len(delivered)
        assert index < len(chunks), 'must not consume beyond the rejected stream'
        delivered.append(chunks[index])
        return {'type': 'http.request', 'body': chunks[index],
                'more_body': index + 1 < len(chunks)}

    async def forbidden_dispatch(request):
        raise AssertionError('login must never dispatch a mutating handler')

    request = Request({'type': 'http', 'method': 'POST', 'path': '/auth/login',
                       'scheme': 'http', 'query_string': b'', 'headers': headers,
                       'server': ('testserver', 80), 'client': ('synthetic', 1234)}, receive)
    response = asyncio.run(security.protect_request(request, forbidden_dispatch))
    assert response.status_code == expected
    if expected == 200:
        assert json.loads(response.body)['authenticated'] is True
        assert 'bibliothekar_session=' in response.headers['set-cookie']
        assert b''.join(delivered) == body
    else:
        assert not security._SESSIONS
        assert 'set-cookie' not in response.headers
        if length == '20000':
            assert delivered == []
        else:
            assert sum(map(len, delivered[:-1])) <= 16384
            assert sum(map(len, delivered)) > 16384
            assert len(delivered) == min(len(chunks), 16384 // chunk_size + 1)
    security._SESSIONS.clear()
    security._FAILURES.clear()
