"""Release-only gates. No command changes app code, host ACLs or NAS data."""
import argparse
import base64
from contextlib import closing
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
from urllib import error, parse, request
import zipfile

SHA='70c0bb57afa168efec83b1b60245b819b36161ff'
DOC='30e492574b02579496fbaece8c3acfe657a70009'
RUN=40840603811
REPO='heller-adrian/Bibliothekar'
BRANCH='codex/prepare-1.0.0-pre-release'
VERSION='1.0.0-pre'
TAG='v'+VERSION
IMAGE='ghcr.io/heller-adrian/bibliothekar:'+VERSION
REGISTRY='https://ghcr.io'
PREFIX='heller-adrian/bibliothekar'
RELEASE_FILES={'.github/workflows/publish-pre.yml',
    'docs/pre/RELEASE-NOTES.md','docs/pre/PUBLISHING.md',
    'docs/pre/release/publish.py','docs/pre/release/verify_evidence.py',
    'docs/pre/release/test_release.py','docs/pre/release/REGISTER-WORKFLOW.yml',
    'docs/pre/release/PREPARATION-REPORT.md','docs/pre/release/actionlint.yaml'}


def run(*args):
    return subprocess.check_output(args,text=True).strip()


def git(*args):return run('git',*args)

def dump(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def publication_context():
    expected={'GITHUB_REPOSITORY':REPO,'GITHUB_REF':'refs/heads/'+BRANCH,
              'GITHUB_EVENT_NAME':'workflow_dispatch','APPROVE_PUBLISH':'PUBLISH '+TAG,
              'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64'}
    for key,value in expected.items():
        assert os.environ.get(key)==value,'Publication context refused: '+key
    assert os.environ.get('GITHUB_RUN_ATTEMPT')=='1','A partial publication requires inspection; never overwrite on retry'


def audit_source():
    assert git('rev-parse',SHA)==SHA and git('rev-parse',DOC)==DOC
    assert git('merge-base','--is-ancestor',DOC,'HEAD')==''
    subprocess.run(['git','diff','--exit-code',SHA,DOC,'--','app','tests','qa','Dockerfile',
                    'requirements.txt','requirements-rc.constraints.txt','compose.example.yaml',
                    'compose.removable.yaml','compose.nas-source.yaml'],check=True)
    changed=set(git('diff','--name-only',DOC,'HEAD').splitlines())
    assert changed<=RELEASE_FILES,'Unapproved source changes: '+repr(changed-RELEASE_FILES)
    assert not git('diff','--name-only','HEAD'),'Dirty tracked source'
    stable=git('show',SHA+':.github/workflows/publish-container.yml')
    assert "      - '!v*-*'" in stable,'Stable tag publisher does not exclude pre tags'
    assert git('show','HEAD:.github/workflows/publish-container.yml')==stable
    assert git('rev-parse','HEAD:app')==git('rev-parse',SHA+':app')


class StripAuthRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        assert parse.urlparse(newurl).scheme=='https','Non-HTTPS artifact redirect'
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected:
            redirected.remove_header('Authorization')
        return redirected


def http(url,headers=None,method='GET',data=None,missing=False):
    req=request.Request(url,headers=headers or {},method=method,data=data)
    try:
        with request.build_opener(StripAuthRedirect()).open(req,timeout=90) as response:
            return response.read(),dict(response.headers)
    except error.HTTPError as exc:
        if missing and exc.code==404:return None,{}
        raise RuntimeError('Remote check failed: '+parse.urlparse(url).path+' HTTP '+str(exc.code)) from None


def github(path,*,missing=False,payload=None):
    headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28'}
    body=None if payload is None else json.dumps(payload).encode()
    if body is not None:headers['Content-Type']='application/json'
    raw,_=http('https://api.github.com/'+path,headers,'GET' if body is None else 'POST',body,missing)
    return None if raw is None else json.loads(raw)


def safe_extract(raw,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=set()
        for item in z.infolist():
            p=PurePosixPath(item.filename)
            assert item.filename and not p.is_absolute() and '..' not in p.parts and '\\' not in item.filename
            assert p.as_posix()==item.filename.rstrip('/'),'Noncanonical ZIP entry'
            canonical=p.as_posix()
            assert canonical not in names,'Duplicate ZIP entry';names.add(canonical)
            mode=item.external_attr>>16
            assert not stat.S_ISLNK(mode),'Artifact symlink'
            assert not (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR))
            assert item.file_size<100_000_000,'Unexpected artifact member size'
        assert sum(i.file_size for i in z.infolist())<300_000_000,'Unexpected artifact size'
        z.extractall(destination)


def verify_artifact_metadata(metadata):
    approved=json.loads(git('show',DOC+':docs/pre/CI-EVIDENCE.json'))
    expected={a['name']:a['digest'] for a in approved['artifacts']}
    artifacts=metadata['artifacts']
    assert len(artifacts)==metadata['total_count']==len(expected)==11
    assert len({a['id'] for a in artifacts})==11
    assert {a['name']:a['digest'] for a in artifacts}==expected
    assert all(not a['expired'] and a['size_in_bytes']>0 and a['workflow_run']['id']==RUN
               and a['workflow_run']['head_sha']==SHA for a in artifacts)
    return artifacts


def download(work):
    work=Path(work);assets=work/'release-assets';assets.mkdir(exist_ok=False)
    repo=github('repos/'+REPO);assert repo['private'] and repo['full_name']==REPO
    dump(assets/'repository-privacy.json',{'private':True,'full_name':REPO})
    for name,suffix in [('accepted-QA',''),('accepted-jobs','/jobs?per_page=100'),
                        ('accepted-artifacts','/artifacts?per_page=100')]:
        dump(assets/(name+'.json'),github(f'repos/{REPO}/actions/runs/{RUN}'+suffix))
    metadata=json.loads((assets/'accepted-artifacts.json').read_text())
    artifacts=verify_artifact_metadata(metadata)
    dest=work/'pre-accepted-evidence';dest.mkdir()
    raw_root=work/'original-artifact-zips';raw_root.mkdir()
    for artifact in artifacts:
        raw,_=http(f'https://api.github.com/repos/{REPO}/actions/artifacts/{artifact["id"]}/zip',
                   {'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
        assert 'sha256:'+hashlib.sha256(raw).hexdigest()==artifact['digest'],'Artifact digest mismatch'
        (raw_root/(artifact['name']+'.zip')).write_bytes(raw)
        safe_extract(raw,dest/artifact['name'])
    with tarfile.open(assets/'accepted-QA-evidence.tar.gz','w:gz') as tar:
        tar.add(dest,arcname='extracted');tar.add(raw_root,arcname='original-zips')


def stage(work):
    work=Path(work);assets=work/'release-assets';assets.mkdir(exist_ok=True)
    for name in ('TEST-REPORT.md','TRUENAS-TEST.md','UPGRADE-RC14.md','OPEN-RISKS.md','CI-EVIDENCE.json','CHANGES.md'):
        (assets/name).write_text(git('show',DOC+':docs/pre/'+name)+'\n')
    shutil.copyfile('docs/pre/RELEASE-NOTES.md',assets/'RELEASE-NOTES.md')
    for name in ('Dockerfile','requirements.txt','requirements-rc.constraints.txt','compose.removable.yaml','compose.nas-source.yaml'):
        (assets/name).write_text(git('show',SHA+':'+name)+'\n')
    (assets/'compose.pre.yaml').write_text(git('show',SHA+':compose.example.yaml')+'\n')
    raw=subprocess.check_output(['git','archive','--format=tar','--prefix=bibliothekar-'+VERSION+'/',SHA])
    with (assets/('bibliothekar-'+VERSION+'-tested-source.tar.gz')).open('wb') as f:
        with gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as gz:gz.write(raw)
    dump(assets/'SOURCE-IDENTITY.json',{'tested_application':SHA,'approved_documentation':DOC,
        'publisher_commit':git('rev-parse','HEAD'),'QA_run':RUN,'version':VERSION,
        'native_truenas':'NOT_RUN','sd_usb_hardware':'NOT_RUN','DNG_1_7':'NOT_RUN'})


def release_free():
    assert github('repos/'+REPO+'/git/ref/tags/'+TAG,missing=True) is None,'Tag already exists'
    assert github('repos/'+REPO+'/releases/tags/'+TAG,missing=True) is None,'Release already exists'


def registry_manifest(reference,*,missing=False):
    credentials=base64.b64encode((os.environ['GITHUB_ACTOR']+':'+os.environ['GH_TOKEN']).encode()).decode()
    token_raw,_=http(REGISTRY+'/token?'+parse.urlencode({'service':'ghcr.io','scope':'repository:'+PREFIX+':pull'}),
                     {'Authorization':'Basic '+credentials})
    token=json.loads(token_raw)['token']
    headers={'Authorization':'Bearer '+token,'Accept':','.join([
        'application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.v2+json'])}
    # A 404 may only mean MANIFEST_UNKNOWN; auth/network/other errors block.
    req=request.Request(REGISTRY+'/v2/'+PREFIX+'/manifests/'+reference,headers=headers)
    try:
        with request.build_opener(StripAuthRedirect()).open(req,timeout=60) as r:return r.read(),r.headers
    except error.HTTPError as exc:
        body=exc.read()
        if missing and exc.code==404 and {e['code'] for e in json.loads(body)['errors']}=={'MANIFEST_UNKNOWN'}:return None,{}
        raise RuntimeError('Registry access failed HTTP '+str(exc.code)) from None


def package():
    p=github('users/heller-adrian/packages/container/bibliothekar')
    assert p['name']=='bibliothekar' and p['package_type']=='container'
    assert p['visibility'] in {'public','private'}
    return {k:p[k] for k in ('name','package_type','visibility')}


def preflight(work):
    publication_context();audit_source();release_free()
    assert github('repos/'+REPO+'/branches/'+parse.quote(BRANCH,safe=''))['commit']['sha']==os.environ['GITHUB_SHA']
    assert git('rev-parse','HEAD')==os.environ['GITHUB_SHA']
    dump(Path(work)/'release-assets/existing-package.json',package())
    assert registry_manifest(VERSION,missing=True)[0] is None,'Image tag already exists'
    local=subprocess.run(['docker','image','inspect',IMAGE],capture_output=True)
    assert local.returncode!=0,'Local image tag already exists; do not overwrite shared runner state'
    run('docker','info')  # Permissions are prerequisites, never repaired here.


def verify_image(ref,source,assets):
    source=Path(source);expected={}
    for p in (source/'app').rglob('*'):
        assert not p.is_symlink()
        if p.is_file():expected[str(p.relative_to(source))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)}
    code='''from pathlib import Path
import hashlib,json,stat
r=Path('/opt/kamera');data={}
for p in (r/'app').rglob('*'):
 assert not p.is_symlink()
 if p.is_file():data[str(p.relative_to(r))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)}
from app import __version__
assert __version__=='1.0.0-pre'
print(json.dumps(data))'''
    actual=json.loads(run('docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp',
        '--user','568:568','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python',ref,'-c',code))
    assert expected and actual==expected,'Embedded application payload differs'
    info=json.loads(run('docker','image','inspect',ref))[0]
    assert info['Config']['Labels']['org.opencontainers.image.revision']==SHA
    assert info['Os']=='linux' and info['Architecture']=='amd64'
    dump(Path(assets)/'APP-PAYLOAD.json',expected)
    dump(Path(assets)/'APP-SHA256.json',{k:v['sha256'] for k,v in expected.items()})


def reserve_tag(work):
    publication_context();release_free()
    assert github('repos/'+REPO+'/branches/'+parse.quote(BRANCH,safe=''))['commit']['sha']==os.environ['GITHUB_SHA']
    assert registry_manifest(VERSION,missing=True)[0] is None,'Image appeared before push'
    result=github('repos/'+REPO+'/git/refs',payload={'ref':'refs/tags/'+TAG,'sha':os.environ['GITHUB_SHA']})
    assert result['object']['sha']==os.environ['GITHUB_SHA']
    dump(Path(work)/'release-assets/tag-reservation.json',result)


def finish(work,digest):
    assert re.fullmatch(r'sha256:[0-9a-f]{64}',digest)
    assets=Path(work)/'release-assets';raw,headers=registry_manifest(digest)
    assert hashlib.sha256(raw).hexdigest()==digest[7:]
    assert headers.get('Docker-Content-Digest')==digest
    manifest=json.loads(raw);assert manifest['mediaType'] in {
        'application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.v2+json'}
    ref=IMAGE.rsplit(':',1)[0]+'@'+digest
    info=json.loads(run('docker','image','inspect',ref))[0]
    assert manifest['config']['digest']==info['Id']==(Path(work)/'built-image-id').read_text().strip()
    assert ref in info['RepoDigests']
    assert package()==json.loads((assets/'existing-package.json').read_text()),'Package visibility changed'
    assert github('repos/'+REPO)['private'] is True
    (assets/'registry-manifest.json').write_bytes(raw)
    dump(assets/'registry-repodigests.json',info['RepoDigests'])
    (assets/'IMAGE-DIGEST.txt').write_text(ref+'\n')
    compose=assets/'compose.pre.yaml';text=compose.read_text();assert text.count(IMAGE)==1;compose.write_text(text.replace(IMAGE,ref))
    guide=assets/'TRUENAS-TEST.md'
    text=guide.read_text();old='Diese Anleitung ist vorbereitet; es gibt noch kein pre-Release oder Image.'
    assert old in text;guide.write_text(text.replace(old,'Diese Anleitung gilt für das veröffentlichte Prerelease '+TAG+'.'))
    guide=assets/'UPGRADE-RC14.md';text=guide.read_text()
    old='**Noch nicht installieren: Kandidat ohne Veröffentlichung.** Erst nach grüner\nvollständiger Abnahme, genauer Commitprüfung und ausdrücklicher Freigabe wird\nin einem eigenen Schritt ein unveränderliches Image bereitgestellt.'
    assert old in text;guide.write_text(text.replace(old,'Prüfe vor dem Upgrade die folgenden Sicherungs- und Mountbedingungen. Das freigegebene Prerelease-Image ist unten per Digest angegeben.'))
    for name in ('RELEASE-NOTES.md','TRUENAS-TEST.md','UPGRADE-RC14.md','TEST-REPORT.md'):
        p=assets/name;text=p.read_text()
        if name=='RELEASE-NOTES.md':
            prefix='https://github.com/'+REPO+'/releases/download/'+TAG+'/'
            text=re.sub(r'\]\((TRUENAS-TEST\.md|UPGRADE-RC14\.md)\)',lambda m:']('+prefix+m[1]+')',text)
        if name=='TEST-REPORT.md':
            text='Veröffentlichungskontext: '+TAG+'. Der folgende Bericht dokumentiert die vorausgehende Abnahme; damalige Hinweise auf eine ausstehende Veröffentlichung sind historisch.\n\n'+text
        p.write_text(text+'\n\nPublished image: '+ref+'\nTested application: '+SHA+'\n')
    checksums(assets)


def checksums(assets):
    assets=Path(assets)
    files=sorted(p for p in assets.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    assert all(not p.is_symlink() and '\n' not in p.name and '\\' not in p.name for p in files)
    (assets/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['audit-source','download','stage','preflight','verify-image','reserve-tag','finish','checksums'])
    p.add_argument('--work',type=Path);p.add_argument('--ref');p.add_argument('--source',type=Path);p.add_argument('--digest');a=p.parse_args()
    if a.command=='audit-source':audit_source()
    elif a.command=='verify-image':verify_image(a.ref,a.source,a.work/'release-assets')
    elif a.command=='finish':finish(a.work,a.digest)
    elif a.command=='checksums':checksums(a.work/'release-assets')
    else:globals()[a.command.replace('-','_')](a.work)

if __name__=='__main__':main()
