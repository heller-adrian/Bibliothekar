"""Strict release graph verification, independent of Docker's image-store ID model.

References: OCI image-spec image-index.md / descriptor.md and Docker's
attestation-storage specification. Unknown graphs fail this release gate.
Attestations are digest-bound metadata, not an independent signed trust root.
"""
import hashlib
import json
import re

OCI_INDEX='application/vnd.oci.image.index.v1+json'
DOCKER_INDEX='application/vnd.docker.distribution.manifest.list.v2+json'
OCI_MANIFEST='application/vnd.oci.image.manifest.v1+json'
DOCKER_MANIFEST='application/vnd.docker.distribution.manifest.v2+json'
INDEX_TYPES={OCI_INDEX,DOCKER_INDEX}
MANIFEST_TYPES={OCI_MANIFEST,DOCKER_MANIFEST}
CONFIG_TYPES={'application/vnd.oci.image.config.v1+json','application/vnd.docker.container.image.v1+json'}
LAYER_TYPES={'application/vnd.oci.image.layer.v1.tar','application/vnd.oci.image.layer.v1.tar+gzip',
             'application/vnd.oci.image.layer.v1.tar+zstd','application/vnd.docker.image.rootfs.diff.tar.gzip'}
IN_TOTO='application/vnd.in-toto+json'


def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def descriptor(d,types):
    assert isinstance(d,dict) and d.get('mediaType') in types,'Unexpected descriptor media type'
    assert re.fullmatch(r'sha256:[0-9a-f]{64}',d.get('digest','')),'Invalid descriptor digest'
    assert type(d.get('size')) is int and 0<d['size']<100_000_000_000,'Invalid descriptor size'
    assert not any(k in d for k in ('urls','data')),'External or inline descriptor refused'
    return d


def decoded(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            assert key not in result,'Duplicate JSON key'
            result[key]=value
        return result
    obj=json.loads(raw,object_pairs_hook=unique)
    assert isinstance(obj,dict),'Expected JSON object'
    return obj


def verify_graph(reference,fetch_manifest,fetch_blob,revision):
    """Verify exact bytes, headers, descriptors and executable/attestation separation."""
    documents={}
    def manifest(ref,desc=None):
        raw,headers=fetch_manifest(ref)
        sha=digest(raw)
        assert headers.get('Docker-Content-Digest')==sha,'Registry digest header mismatch'
        if ref.startswith('sha256:'):assert sha==ref,'Manifest digest mismatch'
        if desc:
            assert sha==desc['digest'] and len(raw)==desc['size'],'Manifest descriptor mismatch'
        obj=decoded(raw)
        assert obj.get('schemaVersion')==2,'Unexpected manifest schema'
        assert obj.get('mediaType') in INDEX_TYPES|MANIFEST_TYPES,'Unexpected manifest type'
        content_type=headers.get('Content-Type','').split(';',1)[0]
        assert content_type==obj['mediaType'],'HTTP/JSON media type mismatch'
        if desc:assert obj['mediaType']==desc['mediaType'],'Descriptor media type mismatch'
        documents[sha]=raw
        return sha,obj
    def blob(desc,types):
        descriptor(desc,types);raw,_=fetch_blob(desc['digest'])
        assert len(raw)==desc['size'] and digest(raw)==desc['digest'],'Blob descriptor mismatch'
        obj=decoded(raw);documents[desc['digest']]=raw
        return obj
    root_sha,root=manifest(reference)
    attestations=[]
    if root['mediaType'] in INDEX_TYPES:
        entries=root.get('manifests')
        assert isinstance(entries,list) and entries,'Index has no manifests'
        seen=set();apps=[];att=[]
        for entry in entries:
            descriptor(entry,MANIFEST_TYPES)
            assert entry['digest'] not in seen,'Duplicate manifest descriptor';seen.add(entry['digest'])
            annotations=entry.get('annotations',{})
            platform=entry.get('platform')
            if annotations.get('vnd.docker.reference.type')=='attestation-manifest':
                assert platform=={'os':'unknown','architecture':'unknown'},'Executable attestation refused'
                att.append(entry)
            else:
                assert not annotations.get('vnd.docker.reference.type'),'Unknown reference type'
                assert platform=={'os':'linux','architecture':'amd64'},'Unexpected or missing platform'
                apps.append(entry)
        assert len(apps)==1,'Missing or ambiguous linux/amd64 application'
        app_sha,app=manifest(apps[0]['digest'],apps[0])
        assert app['mediaType'] in MANIFEST_TYPES
        for entry in att:
            assert entry['annotations'].get('vnd.docker.reference.digest')==app_sha,'Attestation target mismatch'
            att_sha,att_obj=manifest(entry['digest'],entry)
            assert att_obj['mediaType']==OCI_MANIFEST,'Unexpected attestation manifest'
            blob(att_obj['config'],CONFIG_TYPES)
            layers=att_obj.get('layers');assert isinstance(layers,list) and layers,'Empty attestation'
            for layer in layers:
                statement=blob(layer,{IN_TOTO})
                assert statement.get('_type') in {'https://in-toto.io/Statement/v0.1','https://in-toto.io/Statement/v1'}
                assert statement.get('predicateType') in {'https://slsa.dev/provenance/v0.2','https://slsa.dev/provenance/v1'},'Unexpected provenance type'
                assert layer.get('annotations',{}).get('in-toto.io/predicate-type')==statement['predicateType']
                subjects=statement.get('subject');assert isinstance(subjects,list) and subjects
                assert all(s.get('digest')=={'sha256':app_sha[7:]} for s in subjects),'Provenance subject mismatch'
                assert isinstance(statement.get('predicate'),dict),'Missing provenance predicate'
            attestations.append(att_sha)
    else:
        app_sha,app=root_sha,root
    assert 'artifactType' not in app and 'subject' not in app,'Artifact cannot be executable application'
    config_desc=descriptor(app['config'],CONFIG_TYPES)
    config=blob(config_desc,CONFIG_TYPES)
    assert config.get('os')=='linux' and config.get('architecture')=='amd64','Config platform mismatch'
    assert config.get('config',{}).get('Labels',{}).get('org.opencontainers.image.revision')==revision,'Config revision mismatch'
    layers=app.get('layers');assert isinstance(layers,list) and layers,'Application has no layers'
    for layer in layers:descriptor(layer,LAYER_TYPES)
    rootfs=config.get('rootfs',{})
    assert rootfs.get('type')=='layers' and len(rootfs.get('diff_ids',[]))==len(layers),'Config layer mismatch'
    assert all(re.fullmatch(r'sha256:[0-9a-f]{64}',s) for s in rootfs['diff_ids'])
    return {'index_digest':root_sha,'root_media_type':root['mediaType'],'application_manifest':app_sha,
            'config_digest':config_desc['digest'],'attestations':attestations,
            'platform':'linux/amd64','revision':revision},config,documents


def verify_docker(info,proof,config,ref):
    # Classic Docker IDs are config digests. The containerd image store may use
    # the root index/manifest digest instead; accept only this verified graph.
    allowed={proof['config_digest'],proof['application_manifest'],proof['index_digest']}
    assert info['Id'] in allowed,'Docker image ID outside verified graph'
    assert ref in info['RepoDigests'],'Docker RepoDigest mismatch'
    assert info['Os']=='linux' and info['Architecture']=='amd64','Docker platform mismatch'
    assert info['RootFS']['Type']=='layers' and info['RootFS']['Layers']==config['rootfs']['diff_ids'],'Docker rootfs mismatch'
    for key,value in config['config'].items():
        assert info['Config'].get(key)==value,'Docker config mismatch: '+key
    return dict(proof,docker_image_id=info['Id'],docker_id_kind=(
        'config' if info['Id']==proof['config_digest'] else
        'index' if info['Id']==proof['index_digest'] else 'platform-manifest'))
