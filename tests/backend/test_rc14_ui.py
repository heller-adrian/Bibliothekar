"""The shared UI catalogue must initialize with ECMAScript Unicode regexes."""
import json,shutil,subprocess
from app.ui_rc14 import PATTERNS,TRANSLATIONS,ERRORS,error_text


def test_all_new_patterns_are_valid_javascript_unicode_regexes():
    node=shutil.which('node')
    assert node, 'Node is required by the frontend acceptance gate'
    result=subprocess.run([node,'-e','for(const [s] of JSON.parse(process.argv[1]))new RegExp(s,"u");',json.dumps(PATTERNS)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_recovery_and_retirement_errors_have_translated_explanations():
    for code,message in ERRORS.items():
        assert message in TRANSLATIONS
        assert error_text(code+': /workspace/Business')==message+': /workspace/Business'
