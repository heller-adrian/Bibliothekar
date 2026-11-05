"""Run unchanged audit code; retain raw failures, including historical location assertions."""
import os
from pathlib import Path
import subprocess
import sys


def run(mode="f11"):
    root = Path(__file__).resolve().parents[2]
    source = Path(os.environ.get('F11_QA_SOURCE_ROOT', root)).resolve()
    tools = Path(__file__).parent / 'original'
    scratch = Path(os.environ['F11_QA_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ['workspace', 'database', 'logs', 'archive', 'card', 'removable', 'nas', 'devices']:
        (scratch / name).mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(source)+os.pathsep+str(tools),
               AUDIT_SOURCE=str(source), AUDIT_SCRATCH=str(scratch), AUDIT_OUTPUT=str(scratch), AUDIT_LABEL='f11-original',
               KAMERA_CONFIG=str(scratch/'settings.json'), KAMERA_DATABASE_DIR=str(scratch/'database'),
               KAMERA_REGISTRY_DATABASE=str(scratch/'database/registry.sqlite3'), KAMERA_WORKSPACE=str(scratch/'workspace'),
               KAMERA_LOG_DIR=str(scratch/'logs'), KAMERA_ARCHIVE_ROOT=str(scratch/'archive'), KAMERA_IMPORT_ROOT=str(scratch/'card'),
               KAMERA_SOURCE_HELPER_ENABLED='false', BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',
               BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-f11-qa-password', BIBLIOTHEKAR_AUTH_TEST_BYPASS='pytest-isolated')
    selected = {
        'f11': [str(tools/'test_interleavings.py')+'::test_full_empty_reservation_race',str(tools/'test_interleavings.py')+'::test_reserved_rejected'],
        'neighbors': [str(tools/'test_same_process_trash.py')+'::test_same_process_restore_inventory_vs_delete',str(tools/'test_publication.py')+'::test_restore_atomic_destination_collision'],
        'f24': [str(tools/'test_boundaries.py')+'::test_trash_component_swap'],
    }[mode]
    if mode=='f24':env.pop('BIBLIOTHEKAR_AUTH_TEST_BYPASS',None)
    return subprocess.run([sys.executable, str(tools/'runner.py'), '-q', '-p', 'no:cacheprovider', '--import-mode=importlib',
                           '--basetemp', str(scratch/'tmp'), '--junitxml', str(scratch/'results.xml'), *selected],
                          env=env, cwd=source, timeout=180).returncode


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1] if len(sys.argv)>1 else 'f11'))
