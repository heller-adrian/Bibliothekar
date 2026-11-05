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
            from app.managed_directory_names import directory_name
            metadata=workspace/'Metadatenkorrektur'
            for kind in ('metadata_general','metadata_multiple'):
                (metadata/directory_name(metadata,kind)).mkdir(exist_ok=True)
            # The original worker creates a legacy work folder before its
            # layout check. Supply its declared empty schemas before seed;
            # do not bypass the missing-catalogue protection in production.
            from app.database import initialize_database
            from app.library_registry import initialize_library_registry
            initialize_database(Path(command[2])/'kamera.sqlite3')
            initialize_library_registry(Path(command[2])/'registry.sqlite3')
        return actual(command,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',launch)
