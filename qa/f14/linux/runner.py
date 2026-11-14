from guards import *
import pytest

class EvidencePlugin:
    def __init__(self):
        self.rows=[]
        self.label=os.environ['AUDIT_LABEL']
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:
            self.rows.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,
                              'duration_seconds':report.duration,
                              'failure':str(report.longrepr) if report.failed else None})
            label=self.label
            with (output/(label+'-incremental.jsonl')).open('a') as f:
                f.write(json.dumps(self.rows[-1])+'\n')
    def pytest_sessionfinish(self,session,exitstatus):
        label=self.label
        (output/(label+'-results.json')).write_text(json.dumps({'exitstatus':exitstatus,'tests':self.rows},indent=2))

raise SystemExit(pytest.main(sys.argv[1:],plugins=[EvidencePlugin()]))
