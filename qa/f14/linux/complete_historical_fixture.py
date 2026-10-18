"""Provision the four explicitly known historical roots before seed only.

No production/recovery function or assertion is replaced. Original worker sources
remain byte-identical; startup and operation children receive no patched code.
"""
from pathlib import Path
import subprocess
import pytest

@pytest.fixture(autouse=True)
def complete_historical_storage(monkeypatch):
    actual=subprocess.Popen
    def launch(command,*args,**kwargs):
        if isinstance(command,(list,tuple)) and len(command)>=6 and Path(str(command[1])).name in {'worker.py','worker_concurrent.py'} and command[3]=='seed':
            workspace=Path(command[2])/'workspace'
            monkeypatch.setenv('KAMERA_WORKSPACE',str(workspace))
            monkeypatch.setenv('KAMERA_CONFIG',str(Path(command[2])/'settings.json'))
            monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(Path(command[2])/'registry.sqlite3'))
            workspace.mkdir(parents=True,exist_ok=True)
            for name in ['SD-Kartensicherungen','Arbeitsbereiche','Metadatenkorrektur','Papierkorb']:
                (workspace/name).mkdir(exist_ok=True)
        return actual(command,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',launch)
