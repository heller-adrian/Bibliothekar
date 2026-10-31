"""Version-bound pre5 publisher guards. No GitHub/GHCR writes in tests."""
import json,os,unittest
from pathlib import Path
from unittest.mock import patch
import publish as p
import oci
from graph_fixture import Graph

class Pre5PublisherGates(unittest.TestCase):
    def test_source_requires_completed_exact_acceptance(self):
        if p.APPROVAL['status']=='LINUX_ACCEPTED_NOT_RELEASED':p.source_audit()
        else:
            with self.assertRaisesRegex(AssertionError,'Acceptance is not complete'):p.source_audit()
    def test_version_and_all_previous_releases_are_bound(self):
        self.assertEqual(p.VERSION,'1.0.0-pre.5')
        self.assertEqual(p.BUILD,p.HOTFIX)
        self.assertEqual(set(p.PROTECTED),{'v1.0.0-pre','v1.0.0-pre.1','v1.0.0-pre.2','v1.0.0-pre.3','v1.0.0-pre.4'})
        self.assertEqual(p.PROTECTED['v1.0.0-pre.4'][0],'adcc2aa9a444042440ff764be10fe1e42191904d')
    def test_only_exact_push_first_attempt_and_safe_runner(self):
        good={'GITHUB_REPOSITORY':'heller-adrian/Bibliothekar','GITHUB_REF':'refs/heads/'+p.BRANCH,
              'GITHUB_EVENT_NAME':'push','APPROVE_PUBLISH':'PUBLISH '+p.TAG,
              'BUILD_SHA':p.BUILD,'IMAGE':p.IMAGE,'VERSION':p.VERSION,'TAG':p.TAG,
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
            with self.subTest(occupied=occupied),patch.object(p.c,'github',side_effect=remote),patch.object(p.c,'registry_manifest',return_value=(b'exists' if occupied=='image' else None,{})),self.assertRaises(AssertionError):p.free()
    def test_manifest_graph_strict(self):
        for indexed in (True,False):
            g=Graph().build(index=indexed);proof,config,_=g.verify()
            self.assertEqual(proof['application_manifest'],g.appdesc['digest'])
            ref='registry@'+g.digest
            info={'Id':proof['application_manifest'],'RepoDigests':[ref],'Os':'linux','Architecture':'amd64',
                  'Config':config['config'],'RootFS':{'Type':'layers','Layers':config['rootfs']['diff_ids']}}
            self.assertEqual(oci.verify_docker(info,proof,config,ref)['docker_image_id'],proof['application_manifest'])
        for fault in ('missing-platform','wrong-platform','duplicate-platform','duplicate-descriptor','attestation-target','blob-tamper','manifest-tamper','subject','missing-app','descriptor-size','descriptor-digest','descriptor-media','unknown-media','nested-index','urls','inline','negative-size','executable-attestation','unknown-reference','empty-index'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,KeyError)):
                graph=Graph();graph.fault=fault;graph.build();graph.verify()
    def test_invalid_release_digest_is_rejected_without_registry_request(self):
        with patch.object(p.c,'registry_manifest',side_effect=AssertionError('unexpected registry read')):
            for value in ('latest','sha256:bad','sha256:'+'x'*63):
                with self.assertRaises(AssertionError):p.finish('/missing',value)
    def test_workflow_gates_when_final_acceptance_is_pinned(self):
        path=Path('.github/workflows/publish-pre5.yml')
        if not path.exists():
            self.assertNotEqual(p.APPROVAL['status'],'LINUX_ACCEPTED_NOT_RELEASED');return
        workflow=path.read_text()
        for text in ('runs-on: [self-hosted, Linux, X64, bibliothekar-safe]',
                     'branches: [codex/publish-1.0.0-pre.5]',
                     "paths: ['.github/workflows/publish-pre5.yml']",
                     '--prerelease --latest=false','persist-credentials: false'):
            self.assertIn(text,workflow)
        for text in ('docker system prune','git tag -f'):self.assertNotIn(text,workflow)
        self.assertLess(workflow.index('publish.py verify-image'),workflow.index('publish.py reserve'))
        self.assertLess(workflow.index('docker pull --platform'),workflow.index('gh release create'))

if __name__=='__main__':unittest.main()
