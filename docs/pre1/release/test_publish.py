"""Targeted publisher tests only; no publication writes or app test matrix."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import oci
import core as c
import publish as p
from graph_fixture import Graph


class ReleaseGates(unittest.TestCase):
    def test_frozen_source_version_only_relation(self):p.source_audit()

    def test_context_only_accepts_pre1_branch_confirmation_and_first_attempt(self):
        good={'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF':'refs/heads/'+p.BRANCH,'GITHUB_EVENT_NAME':'workflow_dispatch',
            'APPROVE_PUBLISH':'PUBLISH '+p.TAG,'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64',
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}
        with patch.object(c,'git',return_value='a'*40):
            with patch.dict(os.environ,good,clear=True):p.context()
            for field in good:
                with self.subTest(field=field),patch.dict(os.environ,dict(good,**{field:'wrong'}),clear=True),self.assertRaises(AssertionError):p.context()

    def test_existing_tag_release_or_image_always_blocks(self):
        for occupied in ('tag','release','image'):
            def remote(path,**kw):return {'occupied':True} if ('git/ref' in path and occupied=='tag') or ('releases' in path and occupied=='release') else None
            with self.subTest(occupied=occupied),patch.object(c,'github',side_effect=remote),patch.object(c,'registry_manifest',return_value=(b'occupied' if occupied=='image' else None,{})),self.assertRaises(AssertionError):p.free()

    def test_oci_index_and_single_manifest(self):
        for indexed in (True,False):
            g=Graph().build(index=indexed);proof,config,_=g.verify()
            self.assertEqual(proof['revision'],p.BUILD)
            self.assertEqual(proof['application_manifest'],g.appdesc['digest'])
            ref='registry@'+g.digest
            info={'Id':proof['application_manifest'],'RepoDigests':[ref],'Os':'linux','Architecture':'amd64',
                'Config':config['config'],'RootFS':{'Type':'layers','Layers':config['rootfs']['diff_ids']}}
            self.assertEqual(oci.verify_docker(info,proof,config,ref)['docker_image_id'],proof['application_manifest'])
            info['Id']='sha256:'+'f'*64
            with self.assertRaises(AssertionError):oci.verify_docker(info,proof,config,ref)
        g=Graph();g.index['mediaType']=oci.DOCKER_INDEX;g.app['mediaType']=oci.DOCKER_MANIFEST;g.build(attest=False);g.verify()

    def test_oci_graph_negatives(self):
        for fault in ('missing-platform','wrong-platform','duplicate-platform','duplicate-descriptor','missing-app',
                      'descriptor-size','descriptor-digest','descriptor-media','unknown-media','nested-index','urls','inline',
                      'negative-size','attestation-target','executable-attestation','unknown-reference','empty-index','blob-tamper','manifest-tamper','subject'):
            with self.subTest(fault=fault):
                g=Graph();g.fault=fault;g.build()
                with self.assertRaises((AssertionError,KeyError)):g.verify()

    def test_bytewise_payload_and_labels(self):
        for fault in (None,'bytes','mode','extra','missing','revision','version','platform'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                root=Path(root);app=root/'source/app';app.mkdir(parents=True);(root/'release-assets').mkdir()
                path=app/'a.py';path.write_bytes(b'accepted source bytes')
                actual={'app/a.py':{'bytes':base64.b64encode(path.read_bytes()).decode(),'mode':stat.S_IMODE(path.stat().st_mode)}}
                info={'Os':'linux','Architecture':'amd64','Config':{'Labels':{'org.opencontainers.image.revision':p.BUILD,'org.opencontainers.image.version':p.VERSION}}}
                if fault=='bytes':actual['app/a.py']['bytes']=base64.b64encode(b'wrong bytes').decode()
                if fault=='mode':actual['app/a.py']['mode']=0o777
                if fault=='extra':actual['foreign.py']=copy.deepcopy(actual['app/a.py'])
                if fault=='missing':actual={}
                if fault in ('revision','version'):info['Config']['Labels']['org.opencontainers.image.'+fault]='wrong'
                if fault=='platform':info['Architecture']='arm64'
                def call(*args):return json.dumps([info] if args[1:3]==('image','inspect') else actual)
                with patch.object(c,'run',side_effect=call):
                    if fault:
                        with self.assertRaises(AssertionError):p.verify_image(root,'synthetic')
                    else:p.verify_image(root,'synthetic')

    def test_finish_invalid_digest_never_contacts_registry(self):
        with patch.object(c,'registry_manifest',side_effect=RuntimeError('unexpected network')):
            for value in ('latest','sha256:x','sha256:'+'X'*64):
                with self.assertRaises(AssertionError):p.finish('/missing',value)

    def test_workflow_fences(self):
        text=Path('.github/workflows/publish-pre1.yml').read_text()
        self.assertIn('runs-on: [self-hosted, Linux, X64, bibliothekar-safe]',text)
        self.assertIn('  workflow_dispatch:',text);self.assertNotIn('\n  push:',text)
        self.assertIn('PUBLISH v1.0.0-pre.1',text);self.assertIn('--prerelease --latest=false',text)
        self.assertLess(text.index('publish.py runtime'),text.index('publish.py reserve'))
        self.assertLess(text.index('docker pull --platform'),text.index('gh release create'))
        self.assertNotIn('docker system prune',text);self.assertNotIn('git tag -f',text)
        self.assertIn('persist-credentials: false',text)
        stub=Path('docs/pre1/release/REGISTER-WORKFLOW.yml').read_text()
        self.assertNotIn('packages: write',stub);self.assertIn('exit 1',stub)

    def test_downloaded_assets_reject_mutation_and_wrong_metadata(self):
        for fault in (None,'bytes','digest','missing','stable'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                root=Path(root);assets=root/'release-assets';assets.mkdir();down=root/'downloaded-release';down.mkdir()
                (assets/'IMAGE-DIGEST.txt').write_bytes(b'proof');(down/'IMAGE-DIGEST.txt').write_bytes(b'proof')
                r={'prerelease':True,'draft':False,'tag_name':p.TAG,'html_url':'https://example.test/release',
                    'assets':[{'name':'IMAGE-DIGEST.txt','size':5,'digest':oci.digest(b'proof')}]}
                if fault=='bytes':(down/'IMAGE-DIGEST.txt').write_bytes(b'changed')
                if fault=='digest':r['assets'][0]['digest']='sha256:'+'f'*64
                if fault=='missing':(down/'IMAGE-DIGEST.txt').unlink()
                def remote(path,**kwargs):return {'object':{'sha':p.BUILD}} if '/git/ref' in path else r
                with patch.object(p,'unchanged',side_effect=AssertionError('stable changed') if fault=='stable' else None),patch.object(c,'github',side_effect=remote),patch.object(c,'registry_manifest',return_value=(b'index',{'Docker-Content-Digest':oci.digest(b'index')})),patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(root/'summary')}):
                    if fault:
                        with self.assertRaises((AssertionError,FileNotFoundError)):p.post(root,oci.digest(b'index'))
                    else:p.post(root,oci.digest(b'index'))

if __name__=='__main__':unittest.main()
