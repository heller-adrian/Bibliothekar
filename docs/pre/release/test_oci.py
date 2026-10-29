"""Targeted OCI positive/negative tests; no registry writes, Docker or app tests."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import oci
import publish as p
import complete as c


def raw(obj):return json.dumps(obj,separators=(',',':')).encode()


class Graph:
    def __init__(self):
        self.config={'os':'linux','architecture':'amd64','config':{'Labels':{'org.opencontainers.image.revision':p.SHA}},
                     'rootfs':{'type':'layers','diff_ids':['sha256:'+'a'*64]}}
        self.app={'schemaVersion':2,'mediaType':oci.OCI_MANIFEST,'config':None,
                  'layers':[{'mediaType':'application/vnd.oci.image.layer.v1.tar+gzip','digest':'sha256:'+'b'*64,'size':100}]}
        self.statement={'_type':'https://in-toto.io/Statement/v0.1','predicateType':'https://slsa.dev/provenance/v0.2',
                        'subject':None,'predicate':{'buildType':'https://mobyproject.org/buildkit@v1'}}
        self.index={'schemaVersion':2,'mediaType':oci.OCI_INDEX,'manifests':None}
        self.fault=None

    def build(self,index=True,attest=True):
        self.manifests={};self.blobs={}
        def store(obj,media,table):
            b=raw(obj);sha=oci.digest(b);table[sha]=b
            return {'mediaType':media,'digest':sha,'size':len(b)}
        self.app['config']=store(self.config,'application/vnd.oci.image.config.v1+json',self.blobs)
        app=store(self.app,self.app['mediaType'],self.manifests)
        app['platform']={'os':'linux','architecture':'amd64'}
        self.appdesc=app
        self.statement['subject']=[{'name':'application','digest':{'sha256':app['digest'][7:]}}]
        if self.fault=='subject':self.statement['subject'][0]['digest']['sha256']='f'*64
        layer=store(self.statement,oci.IN_TOTO,self.blobs)
        layer['annotations']={'in-toto.io/predicate-type':self.statement['predicateType']}
        att_config=store({'os':'unknown','architecture':'unknown'},'application/vnd.oci.image.config.v1+json',self.blobs)
        att=store({'schemaVersion':2,'mediaType':oci.OCI_MANIFEST,'config':att_config,'layers':[layer]},oci.OCI_MANIFEST,self.manifests)
        att['platform']={'os':'unknown','architecture':'unknown'}
        att['annotations']={'vnd.docker.reference.type':'attestation-manifest','vnd.docker.reference.digest':app['digest']}
        self.attdesc=att
        entries=[app]+([att] if attest else [])
        if self.fault=='missing-platform':del app['platform']
        if self.fault=='wrong-platform':app['platform']['architecture']='arm64'
        if self.fault=='duplicate-platform':
            other=copy.deepcopy(app);other['digest']='sha256:'+'e'*64;entries.append(other)
        if self.fault=='duplicate-descriptor':entries.append(copy.deepcopy(app))
        if self.fault=='missing-app':entries=[att]
        if self.fault=='descriptor-size':app['size']+=1
        if self.fault=='descriptor-digest':app['digest']='sha256:'+'f'*64
        if self.fault=='descriptor-media':app['mediaType']=oci.DOCKER_MANIFEST
        if self.fault=='unknown-media':app['mediaType']='application/unknown'
        if self.fault=='nested-index':app['mediaType']=oci.OCI_INDEX
        if self.fault=='urls':app['urls']=['https://untrusted.example/']
        if self.fault=='inline':app['data']='e30='
        if self.fault=='negative-size':app['size']=-1
        if self.fault=='attestation-target':att['annotations']['vnd.docker.reference.digest']='sha256:'+'f'*64
        if self.fault=='executable-attestation':att['platform']={'os':'linux','architecture':'amd64'}
        if self.fault=='unknown-reference':app['annotations']={'vnd.docker.reference.type':'foreign'}
        if self.fault=='empty-index':entries=[]
        self.index['manifests']=entries
        if index:
            root=store(self.index,self.index['mediaType'],self.manifests)
        else:root=app
        self.digest=root['digest'];self.manifests[p.VERSION]=self.manifests[self.digest]
        if self.fault=='blob-tamper':self.blobs[self.app['config']['digest']]+=b' '
        if self.fault=='manifest-tamper':self.manifests[app['digest']]+=b' '
        return self

    def manifest(self,ref):
        b=self.manifests[ref]
        return b,{'Docker-Content-Digest':oci.digest(b),'Content-Type':json.loads(b)['mediaType']}
    def blob(self,ref):return self.blobs[ref],{}
    def verify(self,reference=None):return oci.verify_graph(reference or self.digest,self.manifest,self.blob,p.SHA)


class OCIReleaseGates(unittest.TestCase):
    def test_oci_index_and_attestation(self):
        g=Graph().build();proof,config,documents=g.verify()
        self.assertEqual(proof['index_digest'],g.digest)
        self.assertEqual(proof['application_manifest'],g.appdesc['digest'])
        self.assertEqual(proof['attestations'],[g.attdesc['digest']])
        self.assertEqual(config,g.config);self.assertEqual(len(documents),6)
        self.assertEqual(g.verify(p.VERSION)[0],proof)

    def test_docker_manifest_list_and_manifest(self):
        g=Graph();g.index['mediaType']=oci.DOCKER_INDEX;g.app['mediaType']=oci.DOCKER_MANIFEST
        g.build(attest=False);self.assertEqual(g.verify()[0]['root_media_type'],oci.DOCKER_INDEX)
        g=Graph().build(index=False);self.assertFalse(g.verify()[0]['attestations'])

    def test_invalid_graphs_are_rejected(self):
        faults=['missing-platform','wrong-platform','duplicate-platform','duplicate-descriptor','missing-app',
                'descriptor-size','descriptor-digest','descriptor-media','unknown-media','nested-index',
                'urls','inline','negative-size','attestation-target','executable-attestation','unknown-reference',
                'empty-index','blob-tamper','manifest-tamper','subject']
        for fault in faults:
            with self.subTest(fault=fault):
                g=Graph();g.fault=fault;g.build()
                with self.assertRaises((AssertionError,KeyError)):g.verify()

    def test_config_and_application_rejections(self):
        for fault in ('revision','platform','layers','artifact','subject','schema','type','provenance-type'):
            with self.subTest(fault=fault):
                g=Graph()
                if fault=='revision':g.config['config']['Labels']['org.opencontainers.image.revision']='0'*40
                if fault=='platform':g.config['architecture']='arm64'
                if fault=='layers':g.config['rootfs']['diff_ids']=[]
                if fault=='artifact':g.app['artifactType']='some/artifact'
                if fault=='subject':g.app['subject']={}
                if fault=='schema':g.app['schemaVersion']=1
                if fault=='type':g.app['mediaType']='application/unexpected'
                if fault=='provenance-type':g.statement['predicateType']='https://untrusted.example/'
                g.build()
                with self.assertRaises(AssertionError):g.verify()

    def test_header_and_digest_identity(self):
        g=Graph().build()
        for fault in ('header','http-type','tag-switch'):
            def fetch(ref):
                b,h=g.manifest(ref)
                if fault=='header':h['Docker-Content-Digest']='sha256:'+'f'*64
                if fault=='http-type':h['Content-Type']=oci.DOCKER_MANIFEST
                if fault=='tag-switch' and ref==g.digest:b+=b' ';h['Docker-Content-Digest']=oci.digest(b)
                return b,h
            with self.subTest(fault=fault),self.assertRaises(AssertionError):oci.verify_graph(g.digest,fetch,g.blob,p.SHA)
        with self.assertRaises(AssertionError):oci.decoded(b'{"a":1,"a":2}')

    def test_docker_ids_are_bound_to_exact_verified_graph_and_config(self):
        g=Graph().build();proof,config,_=g.verify();ref='example@'+g.digest
        info={'Id':proof['config_digest'],'RepoDigests':[ref],'Os':'linux','Architecture':'amd64',
              'Config':g.config['config'],'RootFS':{'Type':'layers','Layers':g.config['rootfs']['diff_ids']}}
        for identity in ('config_digest','application_manifest','index_digest'):
            info['Id']=proof[identity];self.assertEqual(oci.verify_docker(info,proof,config,ref)['docker_image_id'],proof[identity])
        for key,value in [('Id','sha256:'+'f'*64),('RepoDigests',[]),('Architecture','arm64'),
                          ('RootFS',{'Type':'layers','Layers':[]}),('Config',{'Labels':{}})]:
            wrong=copy.deepcopy(info);wrong[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):oci.verify_docker(wrong,proof,config,ref)

    def test_complete_guard_rejects_any_existing_identity_drift(self):
        def github(route,**kw):
            if '/git/ref/' in route:return {'object':{'type':'commit','sha':c.TAG_COMMIT,'url':'https://api.github.com/repos/'+p.REPO+'/git/commits/'+c.TAG_COMMIT}}
            if '/releases/' in route:return None
            return {'private':True,'full_name':p.REPO}
        blobs={ref:('original-'+ref).encode() for ref in (p.VERSION,c.DIGEST,'latest')}
        # Frozen constants are patched only inside this synthetic test.
        target=oci.digest(blobs[p.VERSION]);blobs[c.DIGEST]=blobs[p.VERSION]
        def manifest(ref):
            b=blobs['latest' if ref=='latest' else p.VERSION]
            return b,{'Docker-Content-Digest':oci.digest(b)}
        for fault in (None,'tag','image','latest','visibility','private','release'):
            def remote(route,**kw):
                data=github(route,**kw)
                if fault=='tag' and '/git/ref/' in route:data['object']['sha']='0'*40
                if fault=='private' and route=='repos/'+p.REPO:data['private']=False
                if fault=='release' and '/releases/tags/' in route:return {'prerelease':True}
                return data
            def registry(ref):
                b,h=manifest(ref)
                if (fault=='image' and ref==p.VERSION) or (fault=='latest' and ref=='latest'):b=b'wrong'
                return b,h
            with self.subTest(fault=fault),patch.object(c,'DIGEST',target),patch.object(c,'LATEST',oci.digest(blobs['latest'])),patch.object(p,'publication_context'),patch.object(p,'github',side_effect=remote),patch.object(p,'registry_manifest',side_effect=registry),patch.object(p,'package',return_value={} if fault=='visibility' else c.PACKAGE):
                if fault:
                    with self.assertRaises(AssertionError):c.guard()
                else:c.guard()

    def test_completion_context_is_distinct_from_initial_publication(self):
        valid={'GITHUB_REPOSITORY':p.REPO,'GITHUB_REF':'refs/heads/'+p.BRANCH,'GITHUB_EVENT_NAME':'workflow_dispatch',
               'APPROVE_PUBLISH':'COMPLETE '+p.TAG,'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux',
               'RUNNER_ARCH':'X64','GITHUB_RUN_ATTEMPT':'1'}
        with patch.dict(os.environ,valid,clear=True):
            p.publication_context('complete')
            with self.assertRaises(AssertionError):p.publication_context()
        valid['GITHUB_RUN_ATTEMPT']='2'
        with patch.dict(os.environ,valid,clear=True),self.assertRaises(AssertionError):p.publication_context('complete')

    def test_post_verification_requires_exact_assets_and_digests(self):
        for fault in (None,'bytes','digest','missing','latest'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as d:
                root=Path(d);assets=root/'release-assets';assets.mkdir();downloaded=root/'downloaded-release';downloaded.mkdir()
                (assets/'data.txt').write_bytes(b'approved');(downloaded/'data.txt').write_bytes(b'approved')
                (assets/'release-latest-before.json').write_text('null');(downloaded/'release-latest-before.json').write_text('null')
                metadata={'html_url':'https://example.test/release','assets':[
                    {'name':f.name,'size':len(f.read_bytes()),'digest':oci.digest(f.read_bytes())} for f in assets.iterdir()]}
                if fault=='bytes':(downloaded/'data.txt').write_bytes(b'changed')
                if fault=='digest':metadata['assets'][0]['digest']='sha256:'+'f'*64
                if fault=='missing':(downloaded/'data.txt').unlink()
                def remote(route,**kw):return ({'unexpected':'stable'} if fault=='latest' else None) if route.endswith('/latest') else metadata
                with patch.object(c,'guard'),patch.object(p,'github',side_effect=remote),patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(root/'summary')}):
                    if fault:
                        with self.assertRaises(AssertionError):c.post(root)
                    else:
                        c.post(root);self.assertEqual(json.loads((root/'completion-result.json').read_text())['status'],'PASS')

    def test_completion_workflow_has_no_build_push_or_tag_writer(self):
        source=Path('.github/workflows/publish-pre.yml').read_text().split('\n  complete-existing:',1)[1]
        self.assertIn('packages: read',source)
        self.assertIn('runs-on: [self-hosted, Linux, X64, bibliothekar-safe]',source)
        for command in ('docker build','docker push','reserve-tag','git tag','git push','packages: write'):
            self.assertNotIn(command,source)
        self.assertLess(source.index('complete.py verify'),source.index('gh release create'))
        self.assertIn('--verify-tag',source);self.assertIn('--prerelease --latest=false',source)

if __name__=='__main__':unittest.main()
