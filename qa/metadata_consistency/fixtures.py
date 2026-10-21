"""Complete historical synthetic secondary workspaces before operation, never recovery."""
from pathlib import Path
import json,subprocess
import pytest
from qa.f16_f20.fixtures import complete_historical_storage,phase4_owner_fixture

@pytest.fixture(autouse=True)
def complete_metadata_workspace(monkeypatch):
    actual=subprocess.Popen
    def launch(command,*args,**kwargs):
        child=actual(command,*args,**kwargs)
        if isinstance(command,(list,tuple)) and len(command)>=6 and Path(str(command[1])).name=='worker.py' and command[3]=='seed' and command[4] in {'library_metadata','metadata_projection','reintegrate'}:
            assert child.wait(timeout=45)==0
            case=Path(command[2]);data=json.loads((case/'case.json').read_text());ws=Path(data['workspace'])
            assert ws==case/'fixture/workspace' and ws.is_dir()
            created=[]
            for name in ('SD Card Backups','Library Workspaces','Metadata Correction','Trash'):
                p=ws/name
                if not p.exists():p.mkdir();created.append(str(p))
            (Path(command[5])/'fixture-completion.json').write_text(json.dumps({'phase':'after seed, before operation','created':created}))
        return child
    monkeypatch.setattr(subprocess,'Popen',launch)
