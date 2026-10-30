"""Version-bound, one-shot pre.4 publication. Never retries a partial release."""
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

VERSION='1.0.0-pre.4';TAG='v'+VERSION
IMAGE='ghcr.io/heller-adrian/bibliothekar:'+VERSION
BRANCH='codex/publish-1.0.0-pre.4'
HOTFIX='cd074b76e208fc05932d1afa172eb18b7fc0ddda'
BUILD='adcc2aa9a444042440ff764be10fe1e42191904d'
DOC='6978244a416c5cb455b99b44c02724e09664b017'
QA=41049302266;QA_TARGETED=12973494555;QA_CONTAINER=12973459560
QA_TARGETED_ZIP='sha256:0ace2c6dc86580c90b2a34dfcda43666dee927fc1f88e5508eb891721646c2c2'
QA_CONTAINER_ZIP='sha256:c22f3fd6c44f7e04cbc2450468d9a36e8f8bfb643815b526d446402dc386fdf1'
PROTECTED={
 'v1.0.0-pre':('9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5','sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b'),
 'v1.0.0-pre.1':('282aeba2dd8464f30c8484034759cbb0fd8e0823','sha256:cbaa863fb6173736bcd43e917de994fadba3d05cc69c1688c618fad21d8a17b8'),
 'v1.0.0-pre.2':('f8e128c9e5aec462d16f987d2e71dbe0d02f1549','sha256:b9434137951a8f1e40de047bed6e3d8ee3be425e079b92aa6df9ec491c982c13'),
 'v1.0.0-pre.3':('f18b377a5d3a6a04aab0d1b51ddd1d4c33dc9793','sha256:0a682f37ad63f20c0b108dd5fdd7a5252b4db7c87af04fede7c8e515bdd3bbb0')}
LATEST='sha256:b2a523e09730fd28e6c3178182a15fb1a47e5a529790b7c9ba09f413377aeff1'


def context():
    expected={'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF':'refs/heads/'+BRANCH,
        'GITHUB_EVENT_NAME':'push','APPROVE_PUBLISH':'PUBLISH '+TAG,
        'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64','GITHUB_RUN_ATTEMPT':'1'}
    for key,value in expected.items():assert os.environ.get(key)==value,'Publication context refused: '+key
    assert c.git('rev-parse','HEAD')==os.environ['GITHUB_SHA']


def source_audit():
    for ancestor in (HOTFIX,DOC,BUILD):c.git('merge-base','--is-ancestor',ancestor,'HEAD')
    doc_files=set(c.git('diff','--name-only',HOTFIX,DOC).splitlines())
    assert doc_files=={'docs/pre4/EVIDENCE.json','docs/pre4/REPORT.md','docs/pre4/RELEASE-NOTES.md',
        'docs/pre4/UPGRADE-TRUENAS.md','docs/pre4/TEST-REPORT.md','docs/pre4/READ-ONLY-DIAGNOSIS.md'}
    assert c.git('rev-parse',HOTFIX+':app')==c.git('rev-parse',DOC+':app')
    assert c.git('diff','--name-only',DOC,BUILD).splitlines()==['app/__init__.py']
    before=subprocess.check_output(['git','show',DOC+':app/__init__.py'])
    after=subprocess.check_output(['git','show',BUILD+':app/__init__.py'])
    assert before.count(b'__version__ = "1.0.0-pre.3"')==1
    assert after==before.replace(b'__version__ = "1.0.0-pre.3"',b'__version__ = "1.0.0-pre.4"',1)
    assert c.git('diff','--name-only',HOTFIX,BUILD,'--','app').splitlines()==['app/__init__.py']
    c.git('diff','--exit-code',HOTFIX,BUILD,'--','tests','qa','Dockerfile','requirements.txt',
          'requirements-rc.constraints.txt','compose.example.yaml','compose.removable.yaml','compose.nas-source.yaml')
    changed=set(c.git('diff','--name-only',BUILD,'HEAD').splitlines())
    assert changed and all(n.startswith('docs/pre4/release/') or n=='.github/workflows/publish-pre4.yml'
                           for n in changed),'Unexpected publisher changes'
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
    assert run['path']=='.github/workflows/qa-pre4-operation-separation.yml'
    jobs=c.github(f'repos/{c.REPO}/actions/runs/{QA}/jobs?per_page=100')['jobs']
    assert len(jobs)==2 and {j['name'] for j in jobs}=={'targeted','container'}
    for job in jobs:
        assert job['status']=='completed' and job['conclusion']=='success'
        assert all(step['conclusion']=='success' for step in job['steps'] if step['name']!='Complete job')
    accepted=json.loads(c.git('show',DOC+':docs/pre4/EVIDENCE.json'))
    assert accepted['tested_commit']==HOTFIX and accepted['workflow']['run_id']==QA
    for key,artifact,digest in [('targeted',QA_TARGETED,QA_TARGETED_ZIP),('container',QA_CONTAINER,QA_CONTAINER_ZIP)]:
        meta=c.github(f'repos/{c.REPO}/actions/artifacts/{artifact}')
        assert not meta['expired'] and meta['digest']==digest and meta['workflow_run']['id']==QA and meta['workflow_run']['head_sha']==HOTFIX
        assert accepted['artifacts'][key]['id']==artifact and accepted['artifacts'][key]['digest']==digest
        raw,_=c.http(f'https://api.github.com/repos/{c.REPO}/actions/artifacts/{artifact}/zip',
                     {'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
        assert oci.digest(raw)==digest,'Accepted artifact ZIP changed: '+key
        (assets/('pre4-'+key+'-accepted.zip')).write_bytes(raw)
        extracted=work/('accepted-'+key)
        c.safe_extract(raw,extracted)
        for name in accepted['artifacts'][key]['files']:
            assert (extracted/name).is_file(),'Missing accepted evidence: '+name
    records={}
    for kind,count in [('contracts',39),('historical',148)]:
        root=ET.parse(work/'accepted-targeted'/(kind+'.xml'))
        cases=list(root.iter('testcase'))
        assert len(cases)==count and all(all(t.find(k) is None for k in ('failure','error','skipped')) for t in cases)
        records[kind]=count
    evidence=work/'accepted-container'
    stock=json.loads((evidence/'startup-evidence.json').read_text())
    iphone=json.loads((evidence/'pre-evidence.json').read_text())
    pre3=json.loads((evidence/'pre3-evidence.json').read_text())
    pre4=json.loads((evidence/'pre4-live.json').read_text())
    browser=json.loads((evidence/'pre4-browser/results.json').read_text())
    assert all(x.get('source',x.get('commit'))==HOTFIX for x in (stock,iphone,pre3,pre4))
    qualify_runtime(stock,iphone,pre3,pre4,browser)
    c.dump(assets/'pre4-accepted-run.json',run)
    c.dump(assets/'verified-accepted-QA.json',{'status':'PASS','source':HOTFIX,'run':QA,'pytest':records,
        'artifacts':{'targeted':QA_TARGETED_ZIP,'container':QA_CONTAINER_ZIP},
        'pre4_checks':pre4['checks'],'browser':browser['cases'],'pre3_cases':len(pre3['cases']),
        'stock_cases':stock['cases'],'iphone_corrected':iphone['corrected_files']})

def qualify_runtime(stock,iphone,pre3,pre4,browser):
    assert stock['status']=='PASS' and stock['count']==4000 and stock['web_uid']==568
    assert stock['corrected_files_preserved']==14 and all(stock[k] for k in ('origins_preserved','readonly_bytes_preserved','recheck_passed'))
    assert len(stock['cases'])==2 and all(x['ready'] and x['authenticated_http'] and x['helper_disabled'] and x['startup_seconds']<60 for x in stock['cases'])
    assert iphone['status']=='PASS' and iphone['corrected_files']==14 and iphone['same_reservation_preserved_until_retry']
    assert iphone['origin_preserved'] and iphone['readonly_bytes_preserved']
    assert pre3['status']=='PASS' and pre3['native_truenas']=='NOT_RUN' and pre3['real_DNG_1_7']=='NOT_RUN'
    cases={r['label']:r for r in pre3['cases']}
    assert len(cases)==len(pre3['cases'])==6 and set(cases)=={'historical','rc14','foreign','three','sigkill','import-sigkill'}
    assert all(r['status']=='PASS' and r['archive_unchanged'] for r in cases.values())
    assert all(cases[k]['same_reservation_proven_transfer'] for k in ('historical','rc14','sigkill','import-sigkill'))
    assert all(cases[k]['read_only_recovery_and_write_fence'] for k in ('foreign','three'))
    assert pre4['status']=='PASS' and pre4['native_truenas']=='NOT_RUN' and pre4['real_DNG_1_7']=='NOT_RUN'
    assert all(v=='PASS' for v in pre4['checks'].values()) and len(pre4['checks'])==4
    assert browser['status']=='PASS' and len(browser['cases'])==8
    assert all(x['status']=='PASS' for x in browser['cases'])

def prepare(work):
    context();source_audit();free();fetch_evidence(work);unchanged(work,first=True)
    assert c.github('repos/'+c.REPO+'/branches/'+c.parse.quote(BRANCH,safe=''))['commit']['sha']==os.environ['GITHUB_SHA']
    local=subprocess.run(['docker','image','inspect',IMAGE],capture_output=True)
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
    for name in ('RELEASE-NOTES.md','UPGRADE-TRUENAS.md','TEST-REPORT.md','READ-ONLY-DIAGNOSIS.md'):
        shutil.copyfile(Path('docs/pre4')/name,assets/name)
    shutil.copyfile('qa/pre3/read_only_diagnosis.py',assets/'read_only_diagnosis.py')
    (assets/'VERSION-ONLY-DIFF.patch').write_bytes(subprocess.check_output(['git','diff',HOTFIX,BUILD,'--','app']))
    for name in ('REPORT.md','EVIDENCE.json','ARCHITECTURE.md'):
        (assets/('development-'+name)).write_text(c.git('show',DOC+':docs/pre4/'+name)+'\n')
    for name in ('Dockerfile','requirements.txt','requirements-rc.constraints.txt','compose.removable.yaml','compose.nas-source.yaml'):
        (assets/name).write_bytes(subprocess.check_output(['git','show',BUILD+':'+name]))
    (assets/'compose.pre4.yaml').write_text(c.git('show',BUILD+':compose.example.yaml').replace('bibliothekar:1.0.0-pre}', 'bibliothekar:1.0.0-pre.4}')+'\n')
    c.dump(assets/'SOURCE-IDENTITY.json',{'accepted_hotfix':HOTFIX,'versioned_build_source':BUILD,'documentation':DOC,
        'publisher':os.environ['GITHUB_SHA'],'version':VERSION,'only_app_difference':'app/__init__.py version string',
        'native_truenas_nfs4':'NOT_RUN','physical_sd_usb':'NOT_RUN','DNG_1_7':'NOT_RUN','actual_nas_f14':'NOT_VERIFIED'})
    if local.returncode==0:
        info=verify_image(work,IMAGE)
        assert info['Config']['Labels']['org.opencontainers.image.revision']==BUILD
        assert info['Config']['Labels']['org.opencontainers.image.version']==VERSION
        c.dump(assets/'local-build-preexists.json',{'verified':True,'image_id':info['Id'],'build':BUILD})

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
assert __version__=='1.0.0-pre.4'
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
    for name in ('startup-evidence.json','pre-evidence.json','pre3-evidence.json','pre4-live.json'):
        value=json.loads((work/'runtime'/name).read_text())
        assert value.get('source',value.get('commit'))==BUILD
        data[name]=value;c.dump(assets/('release-'+name),value)
    browser=json.loads((work/'runtime/pre4-browser/results.json').read_text())
    qualify_runtime(data['startup-evidence.json'],data['pre-evidence.json'],data['pre3-evidence.json'],data['pre4-live.json'],browser)
    c.dump(assets/'release-pre4-browser-results.json',browser)
    for name in ('startup.log','iphone.log','container.log','pre4-container.log','historical-container.log'):
        shutil.copyfile(work/'runtime'/name,assets/('release-'+name))
    for folder in ('pre4-historical',):
        for path in sorted((work/'runtime'/folder).glob('*.log')):
            shutil.copyfile(path,assets/('release-'+folder+'-'+path.name))
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
    compose=assets/'compose.pre4.yaml';text=compose.read_text();assert text.count(IMAGE)==1;compose.write_text(text.replace(IMAGE,ref))
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
