"""Test-only explicit B comparison. Never imported by the application."""
import os

def pytest_configure(config):
    mode = os.environ.get('F13_QA_MODE', 'C')
    assert mode in {'B', 'C'}
    if mode == 'B':
        from app import ssd_archive_guard
        class RehashOnly:
            count = 0
            def watch(self, fd, children=None): pass
            def check(self): pass
            def close(self): pass
        ssd_archive_guard.InotifyWatcher = RehashOnly
