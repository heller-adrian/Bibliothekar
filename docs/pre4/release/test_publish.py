"""One-shot pre4 publisher offline guard tests. No writes to GitHub or GHCR."""
import json,os,unittest
from pathlib import Path
from unittest.mock import patch
import publish as p
import oci
from graph_fixture import Graph

class Pre4PublisherGates(unittest.TestCase):
    def test_source_exactly_version_only_and_accepted_documentation(self):
        p.source_audit()
    def test_current_head_has_release_gates_and_is_not_qa_branch(self):
        self.assertEqual(p.VERSION,'1.0.0-pre.4')
        self.assertEqual(p.HOTFIX,'cd074b76e208fc05932d1afa172eb18b7fc0ddda')
        self.assertEqual(p.BUILD,'adcc2aa9a444042440ff764be10fe1e42191904d')
        self.assertEqual(p.QA,41049302266)
    def test_only_exact_push_first_attempt_and_safe_runner(self):
        good={'GITHUB_REPOSITORY':'heller-adrian/Bibliothekar','GITHUB_REF':'refs/heads/'+p.BRANCH,
              'GITHUB_EVENT_NAME':'push','APPROVE_PUBLISH':'PUBLISH '+p.TAG,
              'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64',
              'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}
        with patch.object(p.c,'git',return_value='a'*40),patch.dict(os.environ,good,clear=True):p.context()
        for field in good:
            with self.subTest(field=field),patch.object(p.c,'git',return_value='a'*40),patch.dict(os.environ,dict(good,**{field:'wrong'}),clear=True),self.assertRaises(AssertionError):p.context()
    def test_occupied_tag_or_release_or_registry_cannot_publish(self):
        for occupied in ('tag','release','image'):
            def remote(path,**kw):
                if occupied=='tag' and '/git/ref/' in path:return {'occupied':True}
                if occupied=='release' and '/releases/' in path:return {'occupied':True}
                return None
            with self.subTest(occupied=occupied),patch.object(p.c,'github',side_effect=remote),patch.object(p.c,'registry_manifest',return_value=(b'exists' if occupied=='image' else None,{})),self.assertRaises(AssertionError):
                p.free()
    def test_manifest_graph_strict(self):
        for indexed in (True,False):
            g=Graph().build(index=indexed);proof,config,_=g.verify()
            self.assertEqual(proof['application_manifest'],g.appdesc['digest'])
            ref='registry@'+g.digest
            info={'Id':proof['application_manifest'],'RepoDigests':[ref],'Os':'linux','Architecture':'amd64',
                  'Config':config['config'],'RootFS':{'Type':'layers','Layers':config['rootfs']['diff_ids']}}
            self.assertEqual(oci.verify_docker(info,proof,config,ref)['docker_image_id'],proof['application_manifest'])
        for fault in ('missing-platform','wrong-platform','duplicate-platform','duplicate-descriptor','attestation-target','blob-tamper','manifest-tamper','subject'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,KeyError)):
                graph=Graph();graph.fault=fault;graph.build();graph.verify()
    def test_invalid_release_digest_is_rejected_without_registry_request(self):
        with patch.object(p.c,'registry_manifest',side_effect=AssertionError('unexpected registry read')):
            for value in ('latest','sha256:bad','sha256:'+'x'*63):
                with self.assertRaises(AssertionError):p.finish('/missing',value)
    def test_protected_tags_and_manual_stable_images_are_not_modified(self):
        self.assertEqual(set(p.PROTECTED),{'v1.0.0-pre','v1.0.0-pre.1','v1.0.0-pre.2','v1.0.0-pre.3'})
        self.assertTrue(p.LATEST.startswith('sha256:'))
        workflow=Path('.github/workflows/publish-pre4.yml').read_text()
        self.assertIn('runs-on: [self-hosted, Linux, X64, bibliothekar-safe]',workflow)
        self.assertIn('branches: [codex/publish-1.0.0-pre.4]',workflow)
        self.assertIn('paths: [\'.github/workflows/publish-pre4.yml\']',workflow)
        self.assertIn('--prerelease --latest=false',workflow)
        self.assertIn('persist-credentials: false',workflow)
        self.assertNotIn('docker system prune',workflow)
        self.assertNotIn('git tag -f',workflow)
        self.assertLess(workflow.index('publish.py verify-image'),workflow.index('publish.py reserve'))
        self.assertLess(workflow.index('docker pull --platform'),workflow.index('gh release create'))

if __name__=='__main__':unittest.main()
