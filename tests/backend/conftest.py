"""Explicitly opt into the isolated pytest HTTP authorization bypass.

The deployed server NEVER enables this flag; security.py additionally requires
PYTEST_CURRENT_TEST, which is supplied only during a running pytest test.
BA-03 security-specific tests disable this flag and exercise the real guard.
"""
import os

os.environ.setdefault("BIBLIOTHEKAR_AUTH_TEST_BYPASS", "pytest-isolated")
