"""Candidate contracts: actual frontend catalogue and access defaults."""
import json,subprocess,shutil
from pathlib import Path
from app.ui_i18n import I18N_UI_JS
from app.ui_pre import PATTERNS,TRANSLATIONS


def test_candidate_regexes_compile_in_javascript():
    result=subprocess.run([shutil.which('node'),'-e','for(const [p] of JSON.parse(process.argv[1]))new RegExp(p,"u")',json.dumps(PATTERNS)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_helper_defaults_match_single_container_opt_in():
    import re
    source=re.sub(r"\s+", "", Path("app/main.py").read_text())
    assert '"KAMERA_SOURCE_HELPER_URL","http://127.0.0.1:8090"' in source
    assert 'KAMERA_SOURCE_HELPER_ENABLED=false' in Path('Dockerfile').read_text()
    assert 'KAMERA_SOURCE_HELPER_ENABLED", "false"' in Path('app/container_supervisor.py').read_text()
