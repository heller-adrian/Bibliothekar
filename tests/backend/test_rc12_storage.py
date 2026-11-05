"""RC12 architecture acceptance in separate processes; no external services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('case',['fresh','db-header','registry-header','broad','technical','restore','replace','inode','pending','pending-ready','replaced-db','emptied-registry','registration-flag',
 'missing-db','missing-state','missing-registry','second-instance','missing-mount','legacy-lock','foreign','symlink'])
def test_rc12_lifecycle(tmp_path,case):
    env={k:v for k,v in os.environ.items() if not k.startswith(('KAMERA_','BIBLIOTHEKAR_'))}
    env['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('rc12_worker.py')),str(tmp_path),case],
                          env=env,capture_output=True,text=True,timeout=100)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout.splitlines()[-1])['status']=='PASS'


def test_two_global_states_and_no_implicit_reset():
    from app.storage_status import describe
    for observation in ({'ready':True},{'can_initialize':True},
        {'can_initialize':True,'initialization_evidence':'resumable_empty_structure'},
        {'issues':[{'code':'missing','path':'/test'}]},
        {'issues':[{'code':'history_unknown','path':'/test'}]}):
        result=describe(observation)
        assert result['state']==('READY' if observation.get('ready') else 'UNAVAILABLE')
        assert result['recovery']['authenticated'] and not result['recovery']['automatic_reset']
