"""Version-bound, one-shot pre.2 publication. Never retries a partial release."""
import argparse
import base64
from contextlib import closing
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile

import core as c
import oci

VERSION='1.0.0-pre.2';TAG='v'+VERSION
IMAGE='ghcr.io/heller-adrian/bibliothekar:'+VERSION
BRANCH='codex/publish-1.0.0-pre.2'
HOTFIX='ff1cdf3557b87e5f390f8c1f71abe179ac9d4a52'
BUILD='f8e128c9e5aec462d16f987d2e71dbe0d02f1549'
DOC='a953461979a9a91880347fc31c6a04b778867c65'
QA=40957407776;QA_ARTIFACT=12933834151
QA_ZIP='sha256:46a5015aaacf31c5307bfa2a5c9d2b34efe3594ba88073121748e60a4f201668'
PROTECTED={
 'v1.0.0-pre':('9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5','sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b'),
 'v1.0.0-pre.1':('282aeba2dd8464f30c8484034759cbb0fd8e0823','sha256:cbaa863fb6173736bcd43e917de994fadba3d05cc69c1688c618fad21d8a17b8')}
LATEST='sha256:b2a523e09730fd28e6c3178182a15fb1a47e5a529790b7c9ba09f413377aeff1'


def context():
    expected={'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF':'refs/heads/'+BRANCH,
        'GITHUB_EVENT_NAME':'workflow_dispatch','APPROVE_PUBLISH':'PUBLISH '+TAG,
        'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64','GITHUB_RUN_ATTEMPT':'1'}
    for key,value in expected.items():assert os.environ.get(key)==value,'Publication context refused: '+key
    assert c.git('rev-parse','HEAD')==os.environ['GITHUB_SHA']


def source_audit():
    for ancestor in (HOTFIX,DOC,BUILD):c.git('merge-base','--is-ancestor',ancestor,'HEAD')
    assert set(c.git('diff','--name-only',HOTFIX,DOC).splitlines())=={
        'docs/pre2/EVIDENCE.json','docs/pre2/METADATA-RECOVERY.md','docs/pre2/PROGRESS.md'}
    assert c.git('rev-parse',HOTFIX+':app')==c.git('rev-parse',DOC+':app')
    assert c.git('diff','--name-only',DOC,BUILD).splitlines()==['app/__init__.py']
    before=subprocess.check_output(['git','show',HOTFIX+':app/__init__.py'])
    after=subprocess.check_output(['git','show',BUILD+':app/__init__.py'])
    assert before.count(b'__version__ = "1.0.0-pre.1"')==1
    assert after==before.replace(b'__version__ = "1.0.0-pre.1"',b'__version__ = "1.0.0-pre.2"',1)
    assert c.git('diff','--name-only',HOTFIX,BUILD,'--','app').splitlines()==['app/__init__.py']
    c.git('diff','--exit-code',HOTFIX,BUILD,'--','tests','qa','Dockerfile','requirements.txt',
          'requirements-rc.constraints.txt','compose.example.yaml','compose.removable.yaml','compose.nas-source.yaml')
    changed=set(c.git('diff','--name-only',BUILD,'HEAD').splitlines())
    assert all(n.startswith('docs/pre2/') or n=='.github/workflows/publish-pre2.yml' for n in changed),'Unexpected post-build source changes'
    assert not c.git('diff','--name-only','HEAD'),'Dirty tracked source'
    stable=c.git('show',HOTFIX+':.github/workflows/publish-container.yml')
    assert "      - '!v*-*'" in stable and c.git('show','HEAD:.github/workflows/publish-container.yml')==stable

def free():
    assert c.github('repos/'+c.REPO+'/git/ref/tags/'+TAG,missing=True) is None,'Tag occupied; stop'
    assert c.github('repos/'+c.REPO+'/releases/tags/'+TAG,missing=True) is None,'Release occupied; stop'
    assert c.registry_manifest(VERSION,missing=True)[0] is None,'Image tag occupied; stop'


def old_release(tag):
    release=c.github('repos/'+c.REPO+'/releases/tags/'+tag)
    return {'id':release['id'],'tag_name':release['tag_name'],'prerelease':release['prerelease'],
        'draft':release['draft'],'body_sha256':hashlib.sha256(release['body'].encode()).hexdigest(),
        'assets':sorted([{k:a[k] for k in ('id','name','size','digest','updated_at')} for a in release['assets']],key=lambda x:x['name'])}


def stable_release():
    release=c.github('repos/'+c.REPO+'/releases/latest',missing=True)
    return None if release is None else {k:release[k] for k in ('id','tag_name','target_commitish','prerelease','draft')}


def unchanged(work,first=False):
    assets=Path(work)/'release-assets'
    assert c.github('repos/'+c.REPO)['private'] is True
    package=c.package();assert package=={'name':'bibliothekar','package_type':'container','visibility':'public'}
    protected={}
    for tag,(commit,digest) in PROTECTED.items():
        value=c.github('repos/'+c.REPO+'/git/ref/tags/'+tag)
        assert value['object']['type']=='commit' and value['object']['sha']==commit
        raw,headers=c.registry_manifest(tag[1:])
        assert oci.digest(raw)==headers.get('Docker-Content-Digest')==digest,'Protected image changed: '+tag
        protected[tag]={'commit':commit,'image':digest,'release':old_release(tag)}
    raw,headers=c.registry_manifest('latest')
    assert oci.digest(raw)==headers.get('Docker-Content-Digest')==LATEST,'latest changed'
    refs=c.github('repos/'+c.REPO+'/git/matching-refs/tags/')
    all_tags={r['ref']:r['object'] for r in refs if r['ref']!='refs/tags/'+TAG}
    snapshot={'package':package,'private':True,'protected':protected,'latest_image':LATEST,
              'existing_tags':all_tags,'latest_stable_release':stable_release()}
    if first:c.dump(assets/'protected-before.json',snapshot)
    else:assert snapshot==json.loads((assets/'protected-before.json').read_text()),'Protected release or access changed'

def fetch_evidence(work):
    work=Path(work);assets=work/'release-assets';assets.mkdir(exist_ok=False)
    run=c.github(f'repos/{c.REPO}/actions/runs/{QA}')
    assert run['head_sha']==HOTFIX and run['status']=='completed' and run['run_attempt']==1 and run['conclusion']=='success'
    assert run['path']=='.github/workflows/qa-pre2-metadata.yml'
    jobs=c.github(f'repos/{c.REPO}/actions/runs/{QA}/jobs?per_page=100')['jobs']
    assert len(jobs)==1 and jobs[0]['conclusion']=='success'
    meta=c.github(f'repos/{c.REPO}/actions/artifacts/{QA_ARTIFACT}')
    assert not meta['expired'] and meta['digest']==QA_ZIP and meta['workflow_run']['id']==QA and meta['workflow_run']['head_sha']==HOTFIX
    raw,_=c.http(f'https://api.github.com/repos/{c.REPO}/actions/artifacts/{QA_ARTIFACT}/zip',{'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    assert oci.digest(raw)==QA_ZIP
    (assets/'hotfix-accepted-evidence.zip').write_bytes(raw)
    evidence=work/'hotfix-evidence';c.safe_extract(raw,evidence)
    accepted=json.loads(c.git('show',DOC+':docs/pre2/EVIDENCE.json'))
    files={str(p.relative_to(evidence)):hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence.rglob('*') if p.is_file()}
    assert accepted['source_commit']==HOTFIX and accepted['artifact_sha256']==QA_ZIP[7:] and files==accepted['artifact_files']
    cases=list(ET.parse(evidence/'regressions.xml').iter('testcase'))
    assert len(cases)==148 and all(all(t.find(k) is None for k in ('failure','error','skipped')) for t in cases)
    assert sum(t.attrib.get('classname','').endswith('test_pre2_metadata_abort') for t in cases)==32
    stock=json.loads((evidence/'startup-evidence.json').read_text())
    assert stock['source']==HOTFIX
    correction=json.loads((evidence/'pre-evidence.json').read_text());assert correction['commit']==HOTFIX
    general=json.loads((evidence/'pre2-evidence.json').read_text());assert general['source']==HOTFIX
    qualify_runtime(stock,correction,general)
    c.dump(assets/'hotfix-accepted-run.json',run);c.dump(assets/'hotfix-accepted-artifact.json',meta)
    c.dump(assets/'verified-accepted-QA.json',{'status':'PASS','hotfix':HOTFIX,'run':QA,'passed':148,'new_metadata_cases':32,
           'artifact':QA_ARTIFACT,'artifact_digest':QA_ZIP,'stock':stock,'general':general})


def qualify_runtime(stock,metadata,general):
    assert stock['status']=='PASS' and stock['count']==4000 and stock['web_uid']==568
    assert stock['corrected_files_preserved']==14 and all(stock[k] for k in ('origins_preserved','readonly_bytes_preserved','recheck_passed'))
    assert len(stock['cases'])==2 and all(x['ready'] and x['authenticated_http'] and x['helper_disabled'] and x['startup_seconds']<60 for x in stock['cases'])
    assert metadata['status']=='PASS' and metadata['corrected_files']==14
    assert all(metadata[k] for k in ('same_reservation_preserved_until_retry','origin_preserved','readonly_bytes_preserved'))
    assert metadata['before']['origin']==metadata['after']['origin'] and metadata['before']['readonly']==metadata['final']['readonly']
    assert general['status']=='PASS' and general['real_DNG_1_7']=='NOT_RUN'
    rows={r['label']:r for r in general['cases']};assert len(general['cases'])==len(rows)==3
    assert set(rows)=={'historical','foreign','crash'}
    assert all(r['status']=='PASS' and r['pre1_block_reproduced'] and r['archive_unchanged'] and r['authenticated_http'] for r in rows.values())
    assert rows['historical']['historic_error_row_unchanged'] and rows['historical']['future_refusal_and_restart_ready']
    assert rows['historical']['historic_same_reservation_preserved_in_receipt']
    assert rows['foreign']['foreign_bytes_preserved_and_blocked']
    assert rows['crash']['real_web_sigkill_recovered_same_nonce'] and rows['crash']['historic_same_reservation_preserved_in_receipt']

def prepare(work):
    context();source_audit();free();fetch_evidence(work);unchanged(work,first=True)
    assert c.github('repos/'+c.REPO+'/branches/'+c.parse.quote(BRANCH,safe=''))['commit']['sha']==os.environ['GITHUB_SHA']
    local=subprocess.run(['docker','image','inspect',IMAGE],capture_output=True)
    assert local.returncode!=0,'Local release tag exists; stop instead of overwriting runner state'
    c.run('docker','info')
    work=Path(work);assets=work/'release-assets';source=work/'source';source.mkdir()
    raw=subprocess.check_output(['git','archive','--format=tar',BUILD])
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:t.extractall(source,filter='data')
    for path in source.rglob('*'):
        if path.is_dir():path.chmod(0o755)
        elif path.is_file():path.chmod(0o755 if path.stat().st_mode&0o111 else 0o644)
    source.chmod(0o755)
    archive=subprocess.check_output(['git','archive','--format=tar','--prefix=bibliothekar-'+VERSION+'/',BUILD])
    with (assets/('bibliothekar-'+VERSION+'-source.tar.gz')).open('wb') as f:
        with gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as gz:gz.write(archive)
    for name in ('RELEASE-NOTES.md','UPGRADE-TRUENAS.md','TEST-REPORT.md'):
        shutil.copyfile(Path('docs/pre2')/name,assets/name)
    (assets/'VERSION-ONLY-DIFF.patch').write_bytes(subprocess.check_output(['git','diff',HOTFIX,BUILD,'--','app']))
    for name in ('METADATA-RECOVERY.md','EVIDENCE.json'):
        (assets/('development-'+name)).write_text(c.git('show',DOC+':docs/pre2/'+name)+'\n')
    for name in ('Dockerfile','requirements.txt','requirements-rc.constraints.txt','compose.removable.yaml','compose.nas-source.yaml'):
        (assets/name).write_bytes(subprocess.check_output(['git','show',BUILD+':'+name]))
    (assets/'compose.pre2.yaml').write_text(c.git('show',BUILD+':compose.example.yaml').replace('bibliothekar:1.0.0-pre}', 'bibliothekar:1.0.0-pre.2}')+'\n')
    c.dump(assets/'SOURCE-IDENTITY.json',{'accepted_hotfix':HOTFIX,'versioned_build_source':BUILD,'documentation':DOC,
        'publisher':os.environ['GITHUB_SHA'],'version':VERSION,'only_app_difference':'app/__init__.py version string',
        'native_truenas_nfs4':'NOT_RUN','physical_sd_usb':'NOT_RUN','DNG_1_7':'NOT_RUN','loss_finalization':'DEFERRED'})


def verify_image(work,ref):
    work=Path(work);source=work/'source';expected={};raw_expected={}
    for p in (source/'app').rglob('*'):
        assert not p.is_symlink()
        assert p.is_dir() or p.is_file()
        if p.is_file():
            name=str(p.relative_to(source));raw_expected[name]=p.read_bytes()
            expected[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)}
    code=r'''from pathlib import Path
import base64,json,stat
root=Path('/opt/kamera');data={}
for p in (root/'app').rglob('*'):
 assert not p.is_symlink()
 assert p.is_dir() or p.is_file()
 if p.is_file():data[str(p.relative_to(root))]={'bytes':base64.b64encode(p.read_bytes()).decode(),'mode':stat.S_IMODE(p.stat().st_mode)}
from app import __version__
assert __version__=='1.0.0-pre.2'
print(json.dumps(data))'''
    actual=json.loads(c.run('docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp','--user','568:568','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python',ref,'-c',code))
    assert expected and set(actual)==set(expected),'Embedded app file set changed'
    for name,entry in actual.items():
        assert base64.b64decode(entry['bytes'],validate=True)==raw_expected[name] and entry['mode']==expected[name]['mode'],'Embedded file/mode mismatch: '+name
    info=json.loads(c.run('docker','image','inspect','--platform','linux/amd64',ref))[0]
    assert info['Os']=='linux' and info['Architecture']=='amd64'
    assert info['Config']['Labels']['org.opencontainers.image.revision']==BUILD
    assert info['Config']['Labels']['org.opencontainers.image.version']==VERSION
    c.dump(work/'release-assets/APP-PAYLOAD.json',expected)
    return info


def runtime(work):
    work=Path(work);assets=work/'release-assets';data={}
    for name in ('startup-evidence.json','pre-evidence.json','pre2-evidence.json'):
        value=json.loads((work/'runtime'/name).read_text())
        assert value.get('source',value.get('commit'))==BUILD
        data[name]=value;c.dump(assets/('pre2-'+name),value)
    qualify_runtime(data['startup-evidence.json'],data['pre-evidence.json'],data['pre2-evidence.json'])
    for name in ('startup-container.log','pre-container.log'):
        shutil.copyfile(work/'runtime'/name,assets/('pre2-'+name))
    for path in sorted((work/'runtime/pre2-general').glob('*.log')):
        shutil.copyfile(path,assets/('pre2-general-'+path.name))
    metadata=data['pre-evidence.json']
    assert metadata['candidate_exiftool']=='12.57','ExifTool changed since accepted image; stop for investigation'
    c.dump(work/'runtime-passed.json',{'status':'PASS','build':BUILD})

def reserve(work):
    context();source_audit();free();unchanged(work)
    assert json.loads((Path(work)/'runtime-passed.json').read_text())=={'status':'PASS','build':BUILD}
    verify_image(work,IMAGE)
    assert c.github('repos/'+c.REPO+'/branches/'+c.parse.quote(BRANCH,safe=''))['commit']['sha']==os.environ['GITHUB_SHA']
    result=c.github('repos/'+c.REPO+'/git/refs',payload={'ref':'refs/tags/'+TAG,'sha':BUILD})
    assert result['object']['type']=='commit' and result['object']['sha']==BUILD
    c.dump(Path(work)/'release-assets/tag-reservation.json',result)


def finish(work,digest):
    assert re.fullmatch(r'sha256:[0-9a-f]{64}',digest)
    work=Path(work);assets=work/'release-assets';ref=IMAGE.rsplit(':',1)[0]+'@'+digest
    info=verify_image(work,ref)
    proof,config,documents=oci.verify_graph(digest,c.registry_manifest,lambda d:c.registry_manifest(d,blob=True),BUILD)
    proof=oci.verify_docker(info,proof,config,ref)
    assert proof['attestations'],'Missing provenance attestation'
    assert info['Id']==(work/'built-platform-id').read_text().strip(),'Built/pulled platform ID mismatch'
    raw,headers=c.registry_manifest(VERSION);assert oci.digest(raw)==headers.get('Docker-Content-Digest')==digest
    unchanged(work)
    c.dump(assets/'OCI-VERIFICATION.json',proof)
    for sha,raw in documents.items():(assets/('registry-'+sha[7:]+'.json')).write_bytes(raw)
    (assets/'IMAGE-DIGEST.txt').write_text(ref+'\n')
    for name in ('RELEASE-NOTES.md','UPGRADE-TRUENAS.md','TEST-REPORT.md'):
        p=assets/name;p.write_text(p.read_text()+'\n\nGeprüftes Image: `'+ref+'`\nBuild-Commit: `'+BUILD+'`\nFreigegebener Hotfix: `'+HOTFIX+'`\n')
    compose=assets/'compose.pre2.yaml';text=compose.read_text();assert text.count(IMAGE)==1;compose.write_text(text.replace(IMAGE,ref))
    c.checksums(assets)


def release_guard(work,digest):
    context();unchanged(work)
    assert c.github('repos/'+c.REPO+'/git/ref/tags/'+TAG)['object']['sha']==BUILD
    assert c.github('repos/'+c.REPO+'/releases/tags/'+TAG,missing=True) is None
    raw,headers=c.registry_manifest(VERSION);assert oci.digest(raw)==headers.get('Docker-Content-Digest')==digest
    assert json.loads((Path(work)/'release-assets/OCI-VERIFICATION.json').read_text())['index_digest']==digest


def post(work,digest):
    work=Path(work);assets=work/'release-assets';download=work/'downloaded-release';unchanged(work)
    assert c.github('repos/'+c.REPO+'/git/ref/tags/'+TAG)['object']['sha']==BUILD
    raw,headers=c.registry_manifest(VERSION);assert oci.digest(raw)==headers.get('Docker-Content-Digest')==digest
    r=c.github('repos/'+c.REPO+'/releases/tags/'+TAG);assert r['prerelease'] and not r['draft'] and r['tag_name']==TAG
    names={p.name for p in assets.iterdir() if p.is_file()}
    assert len(r['assets'])==len(names) and {a['name'] for a in r['assets']}==names
    assert {p.name for p in download.iterdir()}==names
    for a in r['assets']:
        data=(assets/a['name']).read_bytes()
        assert (download/a['name']).read_bytes()==data and len(data)==a['size'] and oci.digest(data)==a['digest']
    c.dump(work/'publication-result.json',{'status':'PASS','release':r['html_url'],'tag':TAG,'commit':BUILD,
        'image':IMAGE.rsplit(':',1)[0]+'@'+digest,'assets':len(names),'protected_unchanged':True})
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(r['html_url']+'\n\n'+(assets/'IMAGE-DIGEST.txt').read_text())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['audit','prepare','verify-image','runtime','reserve','finish','release-guard','post'])
    ap.add_argument('--work',type=Path);ap.add_argument('--ref');ap.add_argument('--digest');a=ap.parse_args()
    if a.command=='audit':source_audit()
    elif a.command=='verify-image':verify_image(a.work,a.ref)
    elif a.command in ('finish','release-guard','post'):globals()[a.command.replace('-','_')](a.work,a.digest)
    else:globals()[a.command](a.work)

if __name__=='__main__':main()
