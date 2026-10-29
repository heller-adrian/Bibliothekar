"""Release-only tests; synthetic inputs, no Docker/network/publication writes."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pre_publish',HERE/'publish.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class ReleaseGates(unittest.TestCase):
    def test_source_matches_approved_code(self):
        p.audit_source()

    def test_no_publication_context_by_default(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(AssertionError):p.publication_context()

    def test_context_requires_manual_approval_and_correct_branch_runner(self):
        valid={'GITHUB_REPOSITORY':p.REPO,'GITHUB_REF':'refs/heads/'+p.BRANCH,
               'GITHUB_EVENT_NAME':'workflow_dispatch','APPROVE_PUBLISH':'PUBLISH '+p.TAG,
               'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64','GITHUB_RUN_ATTEMPT':'1'}
        with patch.dict(os.environ,valid,clear=True):p.publication_context()
        for key in valid:
            with self.subTest(key=key),patch.dict(os.environ,dict(valid,**{key:'wrong'}),clear=True):
                with self.assertRaises(AssertionError):p.publication_context()

    def test_artifact_metadata_requires_every_frozen_digest_and_source(self):
        approved=json.loads(p.git('show',p.DOC+':docs/pre/CI-EVIDENCE.json'))
        meta={'total_count':11,'artifacts':[dict(a,id=i,size_in_bytes=10,expired=False,
              workflow_run={'id':p.RUN,'head_sha':p.SHA}) for i,a in enumerate(approved['artifacts'])]}
        self.assertEqual(len(p.verify_artifact_metadata(meta)),11)
        for fault in ('digest','expired','sha','missing','duplicate','count'):
            data=copy.deepcopy(meta)
            if fault=='digest':data['artifacts'][0]['digest']='sha256:'+'0'*64
            elif fault=='expired':data['artifacts'][0]['expired']=True
            elif fault=='sha':data['artifacts'][0]['workflow_run']['head_sha']='0'*40
            elif fault=='missing':data['artifacts'].pop()
            elif fault=='duplicate':data['artifacts'][0]=data['artifacts'][1]
            else:data['total_count']=12
            with self.subTest(fault=fault),self.assertRaises(AssertionError):p.verify_artifact_metadata(data)

    def zip_bytes(self,name,symlink=False):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            item=zipfile.ZipInfo(name)
            item.external_attr=((stat.S_IFLNK|0o777) if symlink else (stat.S_IFREG|0o600))<<16
            z.writestr(item,b'data')
        return buf.getvalue()

    def test_zip_paths_and_symlinks_cannot_escape(self):
        with tempfile.TemporaryDirectory() as d:
            for i,name in enumerate(('../escape','/absolute','a/../../escape','a\\b','a/./b')):
                with self.subTest(name=name),self.assertRaises(AssertionError):p.safe_extract(self.zip_bytes(name),Path(d)/str(i))
            with self.assertRaises(AssertionError):p.safe_extract(self.zip_bytes('link',True),Path(d)/'link')
            p.safe_extract(self.zip_bytes('safe/file.json'),Path(d)/'ok')
            self.assertEqual((Path(d)/'ok/safe/file.json').read_bytes(),b'data')

    def test_redirect_drops_credentials_and_refuses_plain_http(self):
        req=p.request.Request('https://api.github.com/private',headers={'Authorization':'Bearer private-test'})
        redirected=p.StripAuthRedirect().redirect_request(req,None,302,'',{},'https://storage.example/artifact')
        self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(AssertionError):p.StripAuthRedirect().redirect_request(req,None,302,'',{},'http://storage.example/artifact')

    def test_image_gate_rejects_extra_missing_changed_and_wrong_revision(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'app').mkdir();(root/'app/a.py').write_bytes(b'approved');assets=root/'assets';assets.mkdir()
            expected={'app/a.py':{'sha256':hashlib.sha256(b'approved').hexdigest(),'mode':stat.S_IMODE((root/'app/a.py').stat().st_mode)}}
            info={'Config':{'Labels':{'org.opencontainers.image.revision':p.SHA}},'Os':'linux','Architecture':'amd64'}
            for fault in (None,'extra','missing','hash','mode','revision','arch'):
                actual=copy.deepcopy(expected);image=copy.deepcopy(info)
                if fault=='extra':actual['app/foreign.py']=actual['app/a.py']
                elif fault=='missing':actual={}
                elif fault=='hash':actual['app/a.py']['sha256']='0'*64
                elif fault=='mode':actual['app/a.py']['mode']=0o777
                elif fault=='revision':image['Config']['Labels']['org.opencontainers.image.revision']='0'*40
                elif fault=='arch':image['Architecture']='arm64'
                def fake(*args):return json.dumps([image] if args[1:3]==('image','inspect') else actual)
                with self.subTest(fault=fault),patch.object(p,'run',side_effect=fake):
                    if fault:
                        with self.assertRaises(AssertionError):p.verify_image('synthetic',root,assets)
                    else:p.verify_image('synthetic',root,assets)

    def test_occupied_tag_or_release_never_passes(self):
        for occupied in ('git/ref/tags/','releases/tags/'):
            with patch.object(p,'github',side_effect=lambda route,**kw: {'occupied':True} if occupied in route else None):
                with self.assertRaises(AssertionError):p.release_free()

    def test_manifest_digest_format_rejected_before_network(self):
        with patch.object(p,'registry_manifest',side_effect=RuntimeError('must not contact registry')):
            for digest in ('latest','sha256:abc','sha256:'+'Z'*64):
                with self.assertRaises(AssertionError):p.finish('/nonexistent',digest)

    def test_stage_is_accepted_source_and_checksums_detect_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p.stage(d);assets=Path(d)/'release-assets';p.checksums(assets)
            archive=assets/('bibliothekar-'+p.VERSION+'-tested-source.tar.gz')
            import tarfile
            with tarfile.open(archive) as t:
                actual=t.extractfile('bibliothekar-'+p.VERSION+'/app/__init__.py').read()
            import subprocess
            expected=subprocess.check_output(['git','show',p.SHA+':app/__init__.py'])
            self.assertEqual(actual,expected)
            for line in (assets/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split('  ',1);self.assertEqual(hashlib.sha256((assets/name).read_bytes()).hexdigest(),digest)

    def test_digest_pull_manifest_and_visibility_gate(self):
        for fault in (None,'digest','header','config','visibility','repo','index'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as d:
                root=Path(d);p.stage(root);assets=root/'release-assets'
                built='sha256:'+'b'*64;(root/'built-image-id').write_text(built+'\n')
                previous={'name':'bibliothekar','package_type':'container','visibility':'private'}
                p.dump(assets/'existing-package.json',previous)
                manifest={'mediaType':'application/vnd.oci.image.manifest.v1+json','config':{'digest':built}}
                if fault=='config':manifest['config']['digest']='sha256:'+'c'*64
                if fault=='index':manifest['mediaType']='application/vnd.oci.image.index.v1+json'
                raw=json.dumps(manifest).encode();digest='sha256:'+hashlib.sha256(raw).hexdigest()
                if fault=='digest':digest='sha256:'+'0'*64
                ref=p.IMAGE.rsplit(':',1)[0]+'@'+digest
                info={'Id':built,'RepoDigests':[ref]}
                headers={'Docker-Content-Digest':digest if fault!='header' else 'sha256:'+'f'*64}
                pkg=dict(previous,visibility='public') if fault=='visibility' else previous
                with patch.object(p,'registry_manifest',return_value=(raw,headers)),patch.object(p,'run',return_value=json.dumps([info])),patch.object(p,'package',return_value=pkg),patch.object(p,'github',return_value={'private':fault!='repo'}):
                    if fault:
                        with self.assertRaises(AssertionError):p.finish(root,digest)
                    else:
                        p.finish(root,digest)
                        self.assertIn(ref,(assets/'compose.pre.yaml').read_text())
                        self.assertNotIn('Kandidat ohne Veröffentlichung',(assets/'UPGRADE-RC14.md').read_text())
                        self.assertIn('/releases/download/v1.0.0-pre/',(assets/'RELEASE-NOTES.md').read_text())

    def test_registry_only_explicit_missing_manifest_is_free(self):
        from urllib.error import HTTPError
        env={'GITHUB_ACTOR':'test','GH_TOKEN':'secret-test'}
        for status,code in ((404,'MANIFEST_UNKNOWN'),(404,'NAME_UNKNOWN'),(403,'DENIED'),(401,'UNAUTHORIZED'),(500,'UNKNOWN')):
            body=io.BytesIO(json.dumps({'errors':[{'code':code}]}).encode())
            exc=HTTPError('https://ghcr.io/v2/test',status,'synthetic',{},body)
            with self.subTest(status=status,code=code),patch.dict(os.environ,env),patch.object(p,'http',return_value=(b'{"token":"opaque"}',{})),patch.object(p.request,'build_opener') as opener:
                opener.return_value.open.side_effect=exc
                if (status,code)==(404,'MANIFEST_UNKNOWN'):
                    self.assertIsNone(p.registry_manifest(p.VERSION,missing=True)[0])
                else:
                    with self.assertRaises(RuntimeError) as error:p.registry_manifest(p.VERSION,missing=True)
                    self.assertNotIn('secret-test',str(error.exception))

    def test_workflow_is_manual_self_hosted_and_never_latest(self):
        source=Path('.github/workflows/publish-pre.yml').read_text()
        self.assertIn('runs-on: [self-hosted, Linux, X64, bibliothekar-safe]',source)
        self.assertIn('  workflow_dispatch:',source)
        self.assertNotIn('\n  push:',source);self.assertNotIn('\n  workflow_call:',source)
        self.assertIn('--prerelease --latest=false',source)
        self.assertNotIn('docker system prune',source);self.assertNotIn('sudo ',source)
        self.assertLess(source.index('publish.py verify-image'),source.index('publish.py reserve-tag'))
        self.assertLess(source.index('docker pull "$REF"'),source.index('gh release create'))
        self.assertIn('persist-credentials: false',source)

if __name__=='__main__':unittest.main()
