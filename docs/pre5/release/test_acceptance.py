"""Publisher evidence rejection tests; never touch GitHub or media."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import acceptance as a
import publish as p

class EvidenceGates(unittest.TestCase):
    def test_junit_requires_exact_unique_executed_passing_nodes(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'result.xml'
            valid='<testcase classname="tests.backend.example" name="test_ok"/>'
            path.write_text('<testsuites><testsuite>'+valid+'</testsuite></testsuites>')
            self.assertEqual(a.passing_xml(path,1,['tests/backend/example.py::test_ok']),1)
            for bad in [valid+valid,valid.replace('/>','><skipped/></testcase>'),
                        valid.replace('/>','><failure/></testcase>'),valid.replace('/>','><error/></testcase>'),
                        valid.replace('test_ok','test_wrong'),'']:
                path.write_text('<testsuites><testsuite>'+bad+'</testsuite></testsuites>')
                with self.assertRaises(AssertionError):a.passing_xml(path,1,['tests/backend/example.py::test_ok'])
    def test_backend_missing_partitions_cannot_attest_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root);(path/'summary.json').write_text(json.dumps({'status':'PASS','source':p.APPROVAL['backend_source'],
                'complete':True,'collected':2579,'selected_once':2579,'parts':[]}))
            with self.assertRaises(AssertionError):a.verify_backend(path,p.APPROVAL)
    def test_unreviewed_app_delta_is_rejected(self):
        with patch.object(a.c,'git',return_value='app/unreviewed.py'):
            with self.assertRaises(AssertionError):a.checked_delta('a','b',{})
    def test_roles_bind_real_successes_and_explicit_older_frontend_run(self):
        roles=p.APPROVAL['artifacts']
        self.assertEqual(roles['backend']['source'],'18c01fe6730eb4c102c9085eb648325eda2b6622')
        self.assertEqual(roles['final_targets']['source'],p.BUILD)
        self.assertEqual(roles['iphone']['source'],p.BUILD)
        self.assertEqual(roles['frontend']['run_conclusion'],'failure')
        self.assertEqual(roles['frontend']['job'],'frontend')
        self.assertEqual(p.APPROVAL['backend_nodes'],2579)
