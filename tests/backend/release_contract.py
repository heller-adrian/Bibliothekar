"""Packaging version is independent of the application values being tested."""
import json
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[2] / "qa/release"
METADATA = next(
    path for name in ("release-candidate.json", "stable-1.0.0.json", "pre.json")
    if (path := RELEASE_ROOT / name).is_file()
)
EXPECTED_RELEASE_VERSION = json.loads(METADATA.read_text())["version"]
STABLE_METADATA = RELEASE_ROOT / "stable-1.0.0.json"
EXPECTED_STABLE_VERSION = (
    json.loads(STABLE_METADATA.read_text())["version"] if STABLE_METADATA.is_file() else EXPECTED_RELEASE_VERSION
)
