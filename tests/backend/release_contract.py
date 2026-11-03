"""Packaging version is independent of the application values being tested."""
import json
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[2] / "qa/release"
STABLE_METADATA = RELEASE_ROOT / "stable-1.0.0.json"
EXPECTED_RELEASE_VERSION = json.loads(
    (STABLE_METADATA if STABLE_METADATA.is_file() else RELEASE_ROOT / "pre.json").read_text()
)["version"]
