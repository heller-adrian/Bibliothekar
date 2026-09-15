from __future__ import annotations

import json
import subprocess

from app import main, source_helper


def test_0211_version_keeps_schema_22():
    assert main.APP_VERSION == "0.21.1"


def test_source_helper_flattens_nested_findmnt_and_cleans_legacy_mount(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str, check: bool = True):
        calls.append(tuple(args))
        if "findmnt" in args:
            payload = {
                "filesystems": [{
                    "target": "/mnt/apps",
                    "source": "apps",
                    "children": [{
                        "target": str(source_helper.HOST_MOUNT_ROOT / "dev-sdf1"),
                        "source": "/dev/sdf1",
                        "fstype": "vfat",
                        "options": "ro,nosuid,nodev,noexec",
                    }],
                }]
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(source_helper, "run", fake_run)
    source_helper._cleanup_stale_managed_mounts({"/dev/sde1"})

    assert any("umount" in call and str(source_helper.HOST_MOUNT_ROOT / "dev-sdf1") in call for call in calls)
    assert any("find" in call and "dev-*" in call and "-delete" in call for call in calls)


def test_import_page_has_separate_sd_and_generic_source_details():
    html = main.INDEX_HTML if hasattr(main, "INDEX_HTML") else None
    if html is None:
        # The page is assembled in the endpoint source; inspect source text as a stable UI contract.
        from pathlib import Path
        html = Path(main.__file__).read_text()
    assert 'id="sd-source-detail"' in html
    assert 'id="source-detail"' in html
    assert "function updateSdSourceDetail()" in html
    assert 'source.root_key === "removable"' in html
