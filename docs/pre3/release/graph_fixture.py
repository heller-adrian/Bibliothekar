"""Synthetic OCI graph fixture from the accepted OCI correction tests."""
import copy,json
import oci
import publish as p

def raw(obj):return json.dumps(obj,separators=(',',':')).encode()

class Graph:
    def __init__(self):
        self.config={'os':'linux','architecture':'amd64','config':{'Labels':{'org.opencontainers.image.revision':p.BUILD}},
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
    def verify(self,reference=None):return oci.verify_graph(reference or self.digest,self.manifest,self.blob,p.BUILD)
