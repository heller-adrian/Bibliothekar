"""BA-03: fail-closed owner login and CSRF protection for every web/API route.

Uses no privileged helper, SQLite user table or network dependency. The owner
password is configured via a secret file (recommended) or environment
variable. No default login exists. Explicit pytest-only bypass is never active
in a normal running server.
"""
from __future__ import annotations

from app.ui_i18n import I18N_UI_JS

from collections import defaultdict
from datetime import datetime
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from threading import RLock
import time
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

_SESSION_COOKIE = "bibliothekar_session"
_CSRF_COOKIE = "bibliothekar_csrf"
_SESSION_AGE = 60 * 60 * 24 * 14
_FAILURE_PERIOD = 15 * 60
_MAX_FAILURES = 8
_LOCK = RLock()
# Session data is intentionally transient: restarting the server invalidates
# login sessions, while the configured password persists through volume mounts.
_SESSIONS: dict[str, tuple[float, str, str]] = {}
_FAILURES: dict[str, list[float]] = defaultdict(list)


def _is_test_bypass() -> bool:
    return (
        os.environ.get("BIBLIOTHEKAR_AUTH_TEST_BYPASS") == "pytest-isolated"
        and bool(os.environ.get("PYTEST_CURRENT_TEST"))
    )


def _configured_password() -> str | None:
    file_value = str(os.environ.get("BIBLIOTHEKAR_ADMIN_PASSWORD_FILE") or "").strip()
    if file_value:
        path = Path(file_value)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            password = path.read_text(encoding="utf-8").rstrip("\r\n")
        except (OSError, UnicodeError):
            return None
    else:
        password = os.environ.get("BIBLIOTHEKAR_ADMIN_PASSWORD") or ""
    # Fail closed on incomplete configuration. Never log or display the secret.
    if len(password.encode("utf-8")) < 16 or len(password.encode("utf-8")) > 4096:
        return None
    return password


def _valid_origin(request: Request) -> bool:
    """Reject cross-site and malformed origins on state-changing requests."""
    site = str(request.headers.get("sec-fetch-site") or "").lower()
    if site in {"cross-site", "same-site"}:
        # Same-site is NOT same-origin (hostnames or ports may differ).
        return False
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin == "null":
        return False
    if not origin and not referer:
        # Some non-browser clients omit both. Those still require a valid
        # session and CSRF token, but browsers cannot synthesize that header
        # cross-origin without CORS preflight approval.
        return True
    value = origin or referer
    try:
        parsed = urlsplit(value)
        actual = urlsplit(str(request.base_url))
        return (
            parsed.scheme in {"http", "https"}
            and parsed.scheme == actual.scheme
            and parsed.netloc.lower() == actual.netloc.lower()
            and parsed.username is None and parsed.password is None
            and (not origin or parsed.path in {"", "/"})
        )
    except ValueError:
        return False


def _secure_cookie(request: Request) -> bool:
    # The reverse proxy must terminate TLS and configure its forwarded
    # scheme as trusted in uvicorn; alternatively set this explicitly.
    return (
        os.environ.get("BIBLIOTHEKAR_COOKIE_SECURE", "").lower() == "true"
        or request.url.scheme == "https"
    )


def _client_code() -> str:
    return r"""(function(){
"use strict";
if(window.__bibliothekarSecureFetch)return;
window.__bibliothekarSecureFetch=true;
const original=window.fetch.bind(window);
function cookie(name){
  for(const part of document.cookie.split(";")){
    const [key,...tail]=part.trim().split("=");
    if(key===name)return decodeURIComponent(tail.join("="));
  }
  return "";
}
window.fetch=function(input,init){
  const options=init||{};
  const method=String(options.method||(input instanceof Request?input.method:"GET")).toUpperCase();
  if(["POST","PUT","PATCH","DELETE"].includes(method)){
    const raw=typeof input==="string"?input:(input instanceof URL?input.href:input.url);
    const url=new URL(raw,window.location.href);
    if(url.origin===window.location.origin){
      const headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));
      const csrf=cookie("bibliothekar_csrf");
      if(csrf)headers.set("X-Bibliothekar-CSRF",csrf);
      return original(input,{...options,headers,credentials:"same-origin"});
    }
  }
  return original(input,init);
};
})();"""


def _login_html(*, unavailable: bool = False) -> str:
    notice = (
        "<p class='warning'>No administrator password has been configured. "
        "Create an <code>admin-password</code> file in the TrueNAS config directory "
        "with a strong password of at least 16 characters and restart the container.</p>"
        if unavailable else ""
    )
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Bibliothekar · Sign in</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,"Helvetica Neue",sans-serif}
*{box-sizing:border-box}body{margin:0;background:#0c1115;color:#f4f1e8;
min-height:100dvh;display:grid;place-items:center;padding:22px}
main{width:min(430px,100%);background:#171f25;border:1px solid #303b43;
padding:28px;border-radius:20px}h1{margin:0 0 6px;font-size:1.6rem}
p{color:#a8b1b9;line-height:1.5}
label{display:block;margin:24px 0 10px}
input{width:100%;border:1px solid #586774;border-radius:10px;
padding:14px;background:#0c1115;color:#fff;font-size:1rem}
button{border:0;border-radius:11px;padding:14px 20px;background:#1974c6;
color:#fff;font-weight:700;font-size:1rem;width:100%;margin-top:16px}
button:disabled{opacity:.5}.warning{color:#ffcc78}
#error{color:#ff9393;min-height:22px}
</style></head><body><main><h1>Bibliothekar</h1>
<p>Secure access to your camera library</p>""" + notice + """
<form id="login"><label for="password">Administrator password</label>
<input id="password" type="password" autocomplete="current-password"
required minlength="16" autofocus>
<button type="submit">Sign in</button><p id="error" role="alert"></p></form></main>
<script>
document.getElementById("login").addEventListener("submit",async(e)=>{
 e.preventDefault();
 const button=e.target.querySelector("button");
 const error=document.getElementById("error");error.textContent="";
 button.disabled=true;
 try{
  const result=await fetch("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({password:document.getElementById("password").value}),
   credentials:"same-origin",cache:"no-store"});
  if(!result.ok)throw Error(result.status===429?"Too many attempts. Please try again later.":
    "Sign-in failed. Check your password and configuration.");
  const next=new URLSearchParams(location.search).get("next")||"/";
  const target=new URL(next,location.origin);
  location.replace(target.origin===location.origin&&target.pathname.startsWith("/")?
    target.pathname+target.search+target.hash:"/");
 }catch(exc){error.textContent=exc.message;button.disabled=false;}
});
</script></body></html>"""
    return html.replace("</body>", f"<script>{I18N_UI_JS}</script></body>")


def _security_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response


def _session_from_request(request: Request, password: str) -> tuple[str, str] | None:
    token = request.cookies.get(_SESSION_COOKIE) or ""
    if len(token) < 40:
        return None
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()
    with _LOCK:
        item = _SESSIONS.get(key)
        if item is None:
            return None
        expires, csrf, fingerprint = item
        if now > expires or not hmac.compare_digest(
            fingerprint, hashlib.sha256(password.encode("utf-8")).hexdigest()
        ):
            _SESSIONS.pop(key, None)
            return None
        return key, csrf


def _issue_session(request: Request, password: str) -> Response:
    raw_token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    now = time.time()
    key = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with _LOCK:
        expired = [k for k, (expiry, _, _) in _SESSIONS.items() if expiry <= now]
        for item in expired:
            _SESSIONS.pop(item, None)
        _SESSIONS[key] = (
            now + _SESSION_AGE, csrf,
            hashlib.sha256(password.encode("utf-8")).hexdigest(),
        )
    response = _security_headers(JSONResponse({"authenticated": True}))
    secure = _secure_cookie(request)
    response.set_cookie(
        _SESSION_COOKIE, raw_token, max_age=_SESSION_AGE,
        httponly=True, secure=secure, samesite="strict", path="/",
    )
    response.set_cookie(
        _CSRF_COOKIE, csrf, max_age=_SESSION_AGE,
        httponly=False, secure=secure, samesite="strict", path="/",
    )
    return response


async def protect_request(request: Request, call_next):
    """Called OUTERMOST, before any existing library-context middleware."""
    path = request.url.path
    method = request.method.upper()
    if _is_test_bypass():
        return await call_next(request)

    # Health probes contain no user data and need to work without login.
    if path == "/healthz":
        return await call_next(request)
    if path == "/auth/client.js" and method == "GET":
        return _security_headers(Response(
            _client_code(), media_type="application/javascript; charset=utf-8"
        ))
    if path in {"/manifest.webmanifest", "/assets/bibliothekar-logo-v2.svg"} and method == "GET":
        return await call_next(request)

    configured = _configured_password()
    if path == "/auth/login" and method == "POST":
        if not configured:
            return _security_headers(JSONResponse(
                {"detail": "Administratorpasswort ist nicht eingerichtet."},
                status_code=503,
            ))
        if not _valid_origin(request):
            return _security_headers(JSONResponse({"detail": "Ungültiger Ursprung."}, status_code=403))
        address = request.client.host if request.client else "unknown"
        now = time.time()
        with _LOCK:
            attempts = [t for t in _FAILURES[address] if now - t < _FAILURE_PERIOD]
            _FAILURES[address] = attempts
            blocked = len(attempts) >= _MAX_FAILURES
        if blocked:
            return _security_headers(JSONResponse({"detail": "Zu viele Anmeldeversuche."}, status_code=429))
        try:
            if int(request.headers.get("content-length") or "0") > 16384:
                return _security_headers(JSONResponse(
                    {"detail": "Anmeldeanfrage ist zu groß."}, status_code=413,
                ))
            payload = await request.json()
            candidate = str(payload.get("password") or "") if isinstance(payload, dict) else ""
        except (ValueError, TypeError):
            candidate = ""
        # HMAC key comparison is constant-time and does not reveal the
        # actual secret even if candidates differ in length.
        if len(candidate.encode("utf-8")) > 4096:
            return _security_headers(JSONResponse(
                {"detail": "Anmeldeanfrage ist zu groß."}, status_code=413,
            ))
        digest = hashlib.sha256(candidate.encode("utf-8")).digest()
        expected = hashlib.sha256(configured.encode("utf-8")).digest()
        if not hmac.compare_digest(digest, expected):
            with _LOCK:
                _FAILURES[address].append(now)
            return _security_headers(JSONResponse({"detail": "Anmeldung fehlgeschlagen."}, status_code=401))
        with _LOCK:
            _FAILURES.pop(address, None)
        return _issue_session(request, configured)

    if method == "GET" and path in {"/auth/login", "/login"}:
        return _security_headers(HTMLResponse(_login_html(unavailable=not bool(configured))))
    if not configured:
        if method == "GET" and not path.startswith("/api/"):
            return _security_headers(HTMLResponse(_login_html(unavailable=True), status_code=503))
        return _security_headers(JSONResponse(
            {"detail": "Bibliothekar ist gesperrt: Administratorpasswort fehlt."},
            status_code=503,
        ))

    active = _session_from_request(request, configured)
    if active is None:
        if method in {"GET", "HEAD"} and not path.startswith("/api/") and not path.startswith("/auth/"):
            from urllib.parse import quote
            next_url = request.url.path
            if request.url.query:
                next_url += "?" + request.url.query
            return _security_headers(Response(
                status_code=303,
                headers={"Location": "/login?next=" + quote(next_url, safe="")},
            ))
        return _security_headers(JSONResponse({"detail": "Anmeldung erforderlich."}, status_code=401))

    key, csrf = active
    if path == "/auth/logout" and method == "POST":
        if not _valid_origin(request) or not hmac.compare_digest(
            request.headers.get("x-bibliothekar-csrf") or "", csrf
        ):
            return _security_headers(JSONResponse({"detail": "CSRF-Nachweis fehlt."}, status_code=403))
        with _LOCK:
            _SESSIONS.pop(key, None)
        response = _security_headers(JSONResponse({"authenticated": False}))
        response.delete_cookie(_SESSION_COOKIE, path="/")
        response.delete_cookie(_CSRF_COOKIE, path="/")
        return response

    if path == "/auth/status":
        return _security_headers(JSONResponse({"authenticated": True}))
    if method not in {"GET", "HEAD", "OPTIONS"}:
        provided = request.headers.get("x-bibliothekar-csrf") or ""
        if not _valid_origin(request) or not hmac.compare_digest(provided, csrf):
            return _security_headers(JSONResponse(
                {"detail": "Ungültige Herkunft oder fehlender CSRF-Nachweis."},
                status_code=403,
            ))
    response = await call_next(request)
    if path.startswith("/api/") or path in {"/", "/events", "/transfer"}:
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response
