"""Explicitly opt into the isolated pytest HTTP authorization bypass.

The deployed server NEVER enables this flag; security.py additionally requires
PYTEST_CURRENT_TEST, which is supplied only during a running pytest test.
BA-03 security-specific tests disable this flag and exercise the real guard.
"""
import os
from threading import Event, Thread
import pytest

os.environ.setdefault("BIBLIOTHEKAR_AUTH_TEST_BYPASS", "pytest-isolated")

# Historical regression fixtures intentionally create German-named directories.
# Retain those exact old snapshots; new 0.50.2 tests explicitly unset this
# opt-in and exercise English-first physical paths independently.
os.environ.setdefault("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", "de")


@pytest.fixture(autouse=True)
def isolated_web_runtime(monkeypatch):
    """Each synthetic app fixture owns its runtime, never the previous test's.

    Direct startup tests can start actual in-process workers and retain startup
    diagnostics. Stop those workers before their monkeypatched paths are undone.
    External recovery processes and deployed container code are unaffected.
    """
    from app import main

    thread_names = ('WORKER_THREAD', 'CANCEL_WORKER_THREAD', 'RELEASE_WORKER_THREAD')
    event_names = ('WORKER_STOP', 'CANCEL_WORKER_STOP', 'CANCEL_WORKER_WAKE',
                   'RELEASE_WORKER_STOP', 'RELEASE_WORKER_WAKE')

    def stop_workers():
        for name in event_names:
            getattr(main, name).set()
        for name in thread_names:
            thread = getattr(main, name)
            if isinstance(thread, Thread) and thread.is_alive():
                thread.join(timeout=10)
                assert not thread.is_alive(), 'Test leaked active runtime worker: '+name

    if any(isinstance(getattr(main, name), Thread) and getattr(main, name).is_alive()
           for name in thread_names):
        stop_workers()
    for name in thread_names:
        monkeypatch.setattr(main, name, None)
    for name in event_names:
        monkeypatch.setattr(main, name, Event())
    for name in ('DATABASE_INITIALIZATION', 'DATABASE_INITIALIZATION_ERROR',
                 'WORKSPACE_LAYOUT_INITIALIZATION', 'WORKSPACE_LAYOUT_ERROR',
                 'LIBRARY_REGISTRY_INITIALIZATION', 'LIBRARY_REGISTRY_ERROR'):
        monkeypatch.setattr(main, name, None)
    monkeypatch.setattr(main, '_STORAGE_STARTUP_PAUSED', False)
    monkeypatch.setattr(main, '_LIBRARY_SCHEMA_READY', set())
    monkeypatch.setattr(main, '_CENTRAL_RECONCILE_LAST', 0.0)
    monkeypatch.setattr(main, '_CENTRAL_RECONCILE_RESULT', {})
    monkeypatch.setattr(main, 'MAIN_LIBRARY_CONTEXT', main.build_main_library_context())
    try:
        yield
    finally:
        stop_workers()


@pytest.fixture
def isolated_registered_metadata_config(tmp_path,monkeypatch):
    """Give a registered synthetic workspace a real private config path."""
    config=tmp_path/'config'/'settings.json'
    config.parent.mkdir(parents=True,exist_ok=True)
    config.write_text('{}\n',encoding='utf-8')
    monkeypatch.setenv('KAMERA_CONFIG',str(config))
    return config
