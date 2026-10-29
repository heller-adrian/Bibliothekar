"""Complete only the frozen partial publication. No build, push or tag writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

import oci
import publish as p

TAG_COMMIT='9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5'
DIGEST='sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b'
LATEST='sha256:b2a523e09730fd28e6c3178182a15fb1a47e5a529790b7c9ba09f413377aeff1'
FIRST_RUN=40891738442
FIRST_ARTIFACT=12906075241
FIRST_ZIP='sha256:433839bee6b3482cc655cd539fc2f859d9d3ba3f58fffd251a20de07982adf47'
PACKAGE={'name':'bibliothekar','package_type':'container','visibility':'public'}
REF=p.IMAGE.rsplit(':',1)[0]+'@'+DIGEST


def guard(release_exists=False):
    p.publication_context('complete')
    assert p.github('repos/'+p.REPO+'/git/ref/tags/'+p.TAG)['object']=={'type':'commit','sha':TAG_COMMIT,
        'url':'https://api.github.com/repos/'+p.REPO+'/git/commits/'+TAG_COMMIT},'Existing tag changed'
    for reference,expected in ((p.VERSION,DIGEST),(DIGEST,DIGEST),('latest',LATEST)):
        raw,headers=p.registry_manifest(reference)
        assert oci.digest(raw)==expected and headers.get('Docker-Content-Digest')==expected,'Registry identity changed: '+reference
    repo=p.github('repos/'+p.REPO);assert repo['private'] is True and repo['full_name']==p.REPO
    assert p.package()==PACKAGE,'Package visibility changed'
    release=p.github('repos/'+p.REPO+'/releases/tags/'+p.TAG,missing=True)
    if release_exists:
        assert release and release['prerelease'] and not release['draft'] and release['tag_name']==p.TAG
    else:assert release is None,'Release exists: do not repeat completion'


def original(work):
    p.publication_context('complete');p.audit_source();guard()
    assert p.git('rev-parse',p.TAG)==TAG_COMMIT
    assert p.git('merge-base','--is-ancestor',TAG_COMMIT,'HEAD')==''
    work=Path(work);assets=work/'release-assets'
    first=p.github(f'repos/{p.REPO}/actions/runs/{FIRST_RUN}')
    assert first['head_sha']==TAG_COMMIT and first['status']=='completed' and first['conclusion']=='failure'
    assert first['run_attempt']==1 and first['path']=='.github/workflows/publish-pre.yml'
    meta=p.github(f'repos/{p.REPO}/actions/artifacts/{FIRST_ARTIFACT}')
    assert meta['name']=='pre-publication-evidence' and not meta['expired']
    assert meta['digest']==FIRST_ZIP and meta['workflow_run']['id']==FIRST_RUN and meta['workflow_run']['head_sha']==TAG_COMMIT
    raw,_=p.http(f'https://api.github.com/repos/{p.REPO}/actions/artifacts/{FIRST_ARTIFACT}/zip',
                {'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    assert oci.digest(raw)==FIRST_ZIP,'Original publication evidence changed'
    (assets/'original-publication-evidence.zip').write_bytes(raw)
    p.safe_extract(raw,work/'original-publication')
    originals=list((work/'original-publication').rglob('existing-package.json'))
    assert len(originals)==1 and json.loads(originals[0].read_text())==PACKAGE
    original_assets=originals[0].parent
    assert DIGEST in (original_assets/'image-push.log').read_text()
    assert REF in (original_assets/'image-pull.log').read_text()
    (work/'original-assets-location').write_text(str(original_assets))
    p.dump(assets/'existing-package.json',PACKAGE)
    p.dump(assets/'original-publication-run.json',first)
    p.dump(assets/'original-publication-artifact.json',meta)
    p.dump(assets/'tag-reservation.json',p.github('repos/'+p.REPO+'/git/ref/tags/'+p.TAG))
    p.dump(assets/'release-latest-before.json',p.github('repos/'+p.REPO+'/releases/latest',missing=True))


def verify(work):
    work=Path(work);assets=work/'release-assets';guard()
    proof,config,documents=oci.verify_graph(DIGEST,p.registry_manifest,
        lambda d:p.registry_manifest(d,blob=True),p.SHA)
    assert len(proof['attestations'])==1,'Expected original provenance attestation'
    info=json.loads(p.run('docker','image','inspect','--platform','linux/amd64',REF))[0]
    proof=oci.verify_docker(info,proof,config,REF)
    original_assets=Path((work/'original-assets-location').read_text())
    assert json.loads((original_assets/'APP-PAYLOAD.json').read_text())==json.loads((assets/'APP-PAYLOAD.json').read_text()),'Original and current app payload differ'
    p.save_graph(assets,proof,documents)
    p.dump(assets/'registry-repodigests.json',info['RepoDigests'])
    p.dump(assets/'COMPLETION-IDENTITY.json',{'tag':p.TAG,'tag_commit':TAG_COMMIT,
        'application_commit':p.SHA,'documentation_commit':p.DOC,'accepted_QA':p.RUN,
        'original_publication_run':FIRST_RUN,'completion_run':int(os.environ['GITHUB_RUN_ID']),
        'completion_commit':p.git('rev-parse','HEAD'),'image':REF,'new_build':False,'image_push':False,
        'tag_write':False,'repository_private':True,'package':PACKAGE,'latest_image':LATEST,
        'native_truenas_nfs4':'NOT_RUN','physical_sd_usb':'NOT_RUN','DNG_1_7':'NOT_RUN',
        'independent_loss_finalization':'DEFERRED'})
    (assets/'COMPLETION-REPORT.md').write_text(
        '# Kontrollierter Veröffentlichungsabschluss\n\n'
        f'Vorhandener Tag {p.TAG}: {TAG_COMMIT}. Anwendung: {p.SHA}.\n\n'
        f'Erster Lauf: {FIRST_RUN}; Abschlusslauf: '+os.environ['GITHUB_RUN_ID']+'.\n\n'
        'Kein Neubau, kein Image-Push und keine Tagänderung. Der vorhandene OCI-Index, '
        'sein linux/amd64-Manifest, die Konfiguration und Provenance-Blobs wurden anhand '
        'ihrer Bytes, SHA-256-Digests, Descriptorgrößen und Zuordnungen geprüft. '
        'Die Attestation ist Bestandteil des bestehenden Digestbaums und kein unabhängiger Signaturnachweis. '
        'Ein tatsächlicher Digest-Pull und der vollständige Vergleich eingebetteter Appdateien '
        'einschließlich Dateimodi, Version und OCI-Revision wurden erneut ausgeführt. '
        'Die elf ursprünglichen QA-Artefakte wurden erneut heruntergeladen und kryptografisch geprüft; '
        'keine vollständige Testmatrix wurde wiederholt.\n\n'
        'Native TrueNAS-/NFSv4-, physische SD-/USB- und DNG-1.7-Abnahme: NOT_RUN. '
        'Eigenständiges Verlustabschlussmodell: DEFERRED.\n')
    p.finish_assets(assets,REF)
    guard()


def post(work):
    work=Path(work);assets=work/'release-assets';downloaded=work/'downloaded-release'
    guard(release_exists=True)
    assert p.github('repos/'+p.REPO+'/releases/latest',missing=True)==json.loads((assets/'release-latest-before.json').read_text()),'Latest stable release changed'
    release=p.github('repos/'+p.REPO+'/releases/tags/'+p.TAG)
    expected={f.name for f in assets.iterdir() if f.is_file()}
    assert len(release['assets'])==len(expected) and {a['name'] for a in release['assets']}==expected
    assert {f.name for f in downloaded.iterdir()}==expected,'Downloaded asset set mismatch'
    for item in release['assets']:
        name=item['name'];local=(assets/name).read_bytes();remote=(downloaded/name).read_bytes()
        assert remote==local and item['size']==len(local),'Release asset mismatch: '+name
        assert item['digest']==oci.digest(local),'GitHub asset digest mismatch: '+name
    proof={'release_url':release['html_url'],'assets':len(expected),'status':'PASS',
           'asset_digests':{f.name:oci.digest(f.read_bytes()) for f in sorted(downloaded.iterdir())},
           'tag_commit':TAG_COMMIT,'index_digest':DIGEST,'latest_unchanged':LATEST,
           'repository_private':True,'package_visibility':PACKAGE['visibility'],
           'new_build':False,'image_push':False,'tag_write':False}
    p.dump(work/'completion-result.json',proof)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
        f.write('Verified prerelease: '+release['html_url']+'\n\n'+REF+'\n\nAssets verified: '+str(len(expected))+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['guard','original','verify','post'])
    ap.add_argument('--work',type=Path);a=ap.parse_args()
    if a.command=='guard':guard()
    else:globals()[a.command](a.work)

if __name__=='__main__':main()
