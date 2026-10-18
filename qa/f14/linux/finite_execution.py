"""Bound tests without altering product guards or assertions; Unix audit runner."""
import os,signal,subprocess,json
from pathlib import Path
import pytest
class AuditTestTimeout(BaseException):pass
children=[];timeouts=[]
@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    original=subprocess.Popen
    def tracked(*a,**kw):
        process=original(*a,**kw);children.append(process);return process
    subprocess.Popen=tracked
@pytest.hookimpl(hookwrapper=True,tryfirst=True)
def pytest_runtest_protocol(item,nextitem):
    start=len(children)
    def alarm(*args):
        timeouts.append(item.nodeid)
        raise AuditTestTimeout('Isolated test exceeded 90 seconds: '+item.nodeid)
    previous=signal.signal(signal.SIGALRM,alarm);signal.alarm(90)
    try:yield
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
        for p in children[start:]:
            try:
                if p.poll() is None:
                    if os.getpgid(p.pid)==p.pid:os.killpg(p.pid,signal.SIGKILL)
                    else:p.kill()
                    p.wait(timeout=5)
            except (ProcessLookupError,AttributeError):pass
        (Path(os.environ['AUDIT_OUTPUT'])/'execution-deadlines.json').write_text(json.dumps({'per_test_seconds':90,'timeouts':timeouts,'cleanup':'Tracked child processes remaining at test end are stopped; sessions killed as groups'},indent=2))
