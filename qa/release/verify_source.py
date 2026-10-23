"""Release-only invariant: accepted application logic remains byte-identical."""
from pathlib import Path
import hashlib
import json
import subprocess

BASE = 'ac2e7b8df4b8f7bb3a1582b7cb46d250250cd6ed'
VERSION = '1.0.0-rc.1'
root = Path(__file__).resolve().parents[2]
files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, 'app'], cwd=root, text=True).splitlines()
for name in files:
    old = subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=root)
    if name in {'app/__init__.py', 'app/main.py'}:
        old = old.replace(b'0.56.2', VERSION.encode())
    assert (root / name).read_bytes() == old, 'Unapproved application change: ' + name
assert sorted(str(p.relative_to(root)) for p in (root / 'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts) == sorted(files)
print(json.dumps({'accepted_base': BASE, 'accepted_tree': 'cd73ec3cd9a6a068682cffb00183d886807e823b',
                  'release_version': VERSION, 'application_files': len(files),
                  'result': 'Only version substitutions; all other app bytes identical'}))
