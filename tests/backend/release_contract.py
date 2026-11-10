"""Packaging version is independent of the application values being tested."""
import json
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[2] / "qa/release"
METADATA = next(
    path for name in ("release-candidate.json", "stable-1.0.0.json", "pre.json")
    if (path := RELEASE_ROOT / name).is_file()
)
EXPECTED_RELEASE_VERSION = json.loads(METADATA.read_text())["version"]
