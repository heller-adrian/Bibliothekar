"""Run unchanged audit code; retain raw failures, including obsolete-hook failure."""
import os
from pathlib import Path
import subprocess
import sys


def run(semantic=False):
    root = Path(__file__).resolve().parents[2]
    source = Path(os.environ.get('F12_QA_SOURCE_ROOT', root)).resolve()
    tools = Path(__file__).parent / 'original'
    scratch = Path(os.environ['F12_QA_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ['workspace', 'database', 'logs', 'archive', 'card', 'removable', 'nas', 'devices']:
        (scratch / name).mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(source)+os.pathsep+str(tools),
               AUDIT_SOURCE=str(source), AUDIT_SCRATCH=str(scratch), AUDIT_OUTPUT=str(scratch), AUDIT_LABEL='f12-original',
               KAMERA_CONFIG=str(scratch/'settings.json'), KAMERA_DATABASE_DIR=str(scratch/'database'),
               KAMERA_REGISTRY_DATABASE=str(scratch/'database/registry.sqlite3'), KAMERA_WORKSPACE=str(scratch/'workspace'),
               KAMERA_LOG_DIR=str(scratch/'logs'), KAMERA_ARCHIVE_ROOT=str(scratch/'archive'), KAMERA_IMPORT_ROOT=str(scratch/'card'),
               KAMERA_SOURCE_HELPER_ENABLED='false', BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',
               BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-f12-qa-password', BIBLIOTHEKAR_AUTH_TEST_BYPASS='pytest-isolated')
    selected = str(Path(__file__).parent/'test_publication_interleaving.py') if semantic else str(tools/'test_interleavings.py')+'::test_import_target'
    return subprocess.run([sys.executable, str(tools/'runner.py'), '-q', '-p', 'no:cacheprovider', '--import-mode=importlib',
                           '--basetemp', str(scratch/'tmp'), '--junitxml', str(scratch/'results.xml'), selected],
                          env=env, cwd=source, timeout=180).returncode


if __name__ == '__main__':
    raise SystemExit(run('--semantic' in sys.argv))
