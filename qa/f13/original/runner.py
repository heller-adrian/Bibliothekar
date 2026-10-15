from guards import *
import pytest

class EvidencePlugin:
    def __init__(self):self.rows=[]
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:
            self.rows.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,
                              'duration_seconds':report.duration,
                              'failure':str(report.longrepr) if report.failed else None})
    def pytest_sessionfinish(self,session,exitstatus):
        label=os.environ['AUDIT_LABEL']
        (output/(label+'-results.json')).write_text(json.dumps({'exitstatus':exitstatus,'tests':self.rows},indent=2))

raise SystemExit(pytest.main(sys.argv[1:],plugins=[EvidencePlugin()]))
