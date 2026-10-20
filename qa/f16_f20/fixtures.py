"""Explicit historical prerequisites; original files and assertions unchanged."""
import pytest
from qa.f14.linux.complete_historical_fixture import complete_historical_storage
@pytest.fixture(autouse=True)
def phase4_owner_fixture(monkeypatch):
    monkeypatch.setenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS','pytest-isolated')
