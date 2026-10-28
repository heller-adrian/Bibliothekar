"""Packaging version is independent of the application values being tested."""
import json
from pathlib import Path

EXPECTED_RELEASE_VERSION = json.loads(
    (Path(__file__).resolve().parents[2] / 'qa/release/rc13.json').read_text()
)['version']
