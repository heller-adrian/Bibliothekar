"""Run the byte-identical original F13 test, retaining its failure unchanged."""
import os
from pathlib import Path
import subprocess
import sys
def run(selections=None):
    root = Path(__file__).resolve().parents[2]
    scratch = Path(os.environ['F13_QA_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ['workspace','database','logs','archive','card','removable','nas','devices']:
        (scratch/name).mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(root)+os.pathsep+str(Path(__file__).parent/'original')+os.pathsep+str(Path(__file__).parent),
               AUDIT_SOURCE=str(root), AUDIT_SCRATCH=str(scratch), AUDIT_OUTPUT=str(scratch), AUDIT_LABEL='original',
               KAMERA_CONFIG=str(scratch/'settings.json'),KAMERA_DATABASE_DIR=str(scratch/'database'),
               KAMERA_REGISTRY_DATABASE=str(scratch/'database/registry.sqlite3'), KAMERA_WORKSPACE=str(scratch/'workspace'),
               KAMERA_LOG_DIR=str(scratch/'logs'),KAMERA_ARCHIVE_ROOT=str(scratch/'archive'),KAMERA_IMPORT_ROOT=str(scratch/'card'),
               KAMERA_SOURCE_HELPER_ENABLED='false',BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',
               BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-f13-ci-password',BIBLIOTHEKAR_AUTH_TEST_BYPASS='pytest-isolated')
    cmd=[sys.executable,str(Path(__file__).parent/'original/runner.py'),'-q','-p','no:cacheprovider','-p','f13_mode','--import-mode=importlib',
         '--basetemp',str(scratch/'tmp'),'--junitxml',str(scratch/'original.xml'),
         *(selections or [str(Path(__file__).parent/'original/test_interleavings.py')+'::test_archive_change_before_unlink'])]
    return subprocess.run(cmd,env=env,cwd=root,timeout=180).returncode

if __name__ == '__main__':
    raise SystemExit(run())
