"""Packaging version is independent of the application values being tested."""
import json
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[2] / "qa/release"
METADATA = next(
    path for name in ("release-candidate.json", "stable-1.0.0.json", "pre.json")
    if (path := RELEASE_ROOT / name).is_file()
)
RELEASE_METADATA = json.loads(METADATA.read_text())
EXPECTED_RELEASE_VERSION = RELEASE_METADATA["version"]
STABLE_METADATA = RELEASE_ROOT / "stable-1.0.0.json"
EXPECTED_STABLE_VERSION = (
    RELEASE_METADATA.get("stable_version") or
    (json.loads(STABLE_METADATA.read_text())["version"] if STABLE_METADATA.is_file() else EXPECTED_RELEASE_VERSION)
)
