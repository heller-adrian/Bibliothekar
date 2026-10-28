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
    # This integration case runs three separate real app lifecycles. Each
    # lifecycle already has a 45-second subprocess deadline, plus three
    # 15-second probes. The old 90-second aggregate bound was contradictory.
    deadline = 240 if item.nodeid.endswith('test_f14_true_sigkill_preserves_reservation_and_blocks_changes[reserve]') else 90
    # This NEW size fixture verifies 3,892 files/inodes through the full audited
    # descriptor path several times. Its small six-file counterpart retains
    # the 90-second bound; existing recovery/security deadlines are unchanged.
    if item.nodeid.endswith('test_rc13_staged_zero_published_resume_preserves_origin[3892]'):
        deadline=300
    def alarm(*args):
        timeouts.append(item.nodeid)
        raise AuditTestTimeout(f'Isolated test exceeded {deadline} seconds: '+item.nodeid)
    previous=signal.signal(signal.SIGALRM,alarm);signal.alarm(deadline)
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
        (Path(os.environ['AUDIT_OUTPUT'])/'execution-deadlines.json').write_text(json.dumps({'per_test_seconds':90,'three_lifecycle_reserve_seconds':240,'rc14_3892_files_seconds':300,'timeouts':timeouts,'cleanup':'Tracked child processes remaining at test end are stopped; sessions killed as groups'},indent=2))
