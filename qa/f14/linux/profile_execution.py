"""Optional bounded profiling of named slow integration tests, including FAIL.

No deadlines, application guards or assertions are replaced. Profile data is
emitted even when a test's existing deadline interrupts an authorizer callback.
"""
import cProfile
import hashlib
import io
import os
from pathlib import Path
import pstats
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    selected=any(part in item.nodeid for part in os.environ['AUDIT_PROFILE_MATCH'].split('|'))
    profile=cProfile.Profile() if selected else None
    if profile:profile.enable()
    try:yield
    finally:
        if profile:
            profile.disable()
            stem=Path(os.environ['AUDIT_OUTPUT'])/('profile-'+hashlib.sha256(item.nodeid.encode()).hexdigest()[:12])
            profile.dump_stats(str(stem)+'.pstats')
            report=io.StringIO();report.write(item.nodeid+'\n')
            stats=pstats.Stats(profile,stream=report)
            stats.sort_stats('cumulative').print_stats(80)
            stats.sort_stats('tottime').print_stats(80)
            stem.with_suffix('.txt').write_text(report.getvalue())
