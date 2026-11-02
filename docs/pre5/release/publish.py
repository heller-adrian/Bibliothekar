"""Version-bound, one-shot pre.5 publication. Never retries a partial release."""
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

VERSION='1.0.0-pre.5';TAG='v'+VERSION
IMAGE='ghcr.io/heller-adrian/bibliothekar:'+VERSION
BRANCH='codex/publish-1.0.0-pre.5'
APPROVAL=json.loads(Path(__file__).with_name('ACCEPTANCE.json').read_text())
BUILD=HOTFIX=APPROVAL['source'];DOC=APPROVAL['documentation'];QA=APPROVAL['run']
PROTECTED={
 'v1.0.0-pre':('9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5','sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b'),
 'v1.0.0-pre.1':('282aeba2dd8464f30c8484034759cbb0fd8e0823','sha256:cbaa863fb6173736bcd43e917de994fadba3d05cc69c1688c618fad21d8a17b8'),
 'v1.0.0-pre.2':('f8e128c9e5aec462d16f987d2e71dbe0d02f1549','sha256:b9434137951a8f1e40de047bed6e3d8ee3be425e079b92aa6df9ec491c982c13'),
 'v1.0.0-pre.3':('f18b377a5d3a6a04aab0d1b51ddd1d4c33dc9793','sha256:0a682f37ad63f20c0b108dd5fdd7a5252b4db7c87af04fede7c8e515bdd3bbb0'),
 'v1.0.0-pre.4':('adcc2aa9a444042440ff764be10fe1e42191904d','sha256:0678dca61f426a01ae724852741bcad6fd7cf45ae3c13df873ed6f14349c4d77')}
LATEST='sha256:b2a523e09730fd28e6c3178182a15fb1a47e5a529790b7c9ba09f413377aeff1'


def context():
    expected={'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF':'refs/heads/'+BRANCH,
        'GITHUB_EVENT_NAME':'push','APPROVE_PUBLISH':'PUBLISH '+TAG,
        'BUILD_SHA':BUILD,'IMAGE':IMAGE,'VERSION':VERSION,'TAG':TAG,
        'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64','GITHUB_RUN_ATTEMPT':'1'}
    for key,value in expected.items():assert os.environ.get(key)==value,'Publication context refused: '+key
    assert c.git('rev-parse','HEAD')==os.environ['GITHUB_SHA']


def source_audit():
    assert APPROVAL['status']=='LINUX_ACCEPTED_NOT_RELEASED','Acceptance is not complete'
    assert re.fullmatch('[0-9a-f]{40}',BUILD) and re.fullmatch('[0-9a-f]{40}',DOC)
    c.git('merge-base','--is-ancestor',PROTECTED['v1.0.0-pre.4'][0],BUILD)
    c.git('merge-base','--is-ancestor',BUILD,DOC)
    c.git('merge-base','--is-ancestor',DOC,'HEAD')
    assert all(n.startswith('docs/pre5/') or n=='FORTSETZUNG.md'
               for n in c.git('diff','--name-only',BUILD,DOC).splitlines())
    assert c.git('rev-parse',BUILD+':app')==c.git('rev-parse',DOC+':app')
    from acceptance import audit_source
    audit_source(APPROVAL)
    changed=c.git('diff','--name-only',DOC,'HEAD').splitlines()
    assert changed and all(n.startswith('docs/pre5/release/') or n=='.github/workflows/publish-pre5.yml'
                           for n in changed),'Unexpected publisher changes'
    assert not c.git('diff','--name-only','HEAD'),'Dirty tracked source'
    assert '__version__ = "'+VERSION+'"' in c.git('show',BUILD+':app/__init__.py')
    stable=c.git('show',BUILD+':.github/workflows/publish-container.yml')
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
    from acceptance import fetch
    fetch(work,APPROVAL,qualify_runtime_folder)


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

def qualify_runtime_folder(folder,source):
    data={name:json.loads((folder/name).read_text()) for name in (
        'startup-evidence.json','pre-evidence.json','pre3-evidence.json','pre4-live.json',
        'pre5-live.json','pre5-manual-changes.json')}
    assert all(value.get('source',value.get('commit'))==source for value in data.values())
    baseline=json.loads((folder/'pre4-browser/results.json').read_text())
    qualify_runtime(*(data[n] for n in ('startup-evidence.json','pre-evidence.json','pre3-evidence.json','pre4-live.json')),baseline)
    live=data['pre5-live.json'];manual=data['pre5-manual-changes.json']
    assert live['status']=='PASS' and set(live['checks'])=={
        'real_general_api_and_two_restarts','real_pre4_inventory_failure_upgrade_original_reservation',
        'scoped_conflict_real_import_event_sort_two_restarts','authenticated_scoped_diagnostics',
        'archives_unchanged','chromium_normal_pages_fenced_reads_de_en_mobile_desktop'}
    assert all(value=='PASS' for value in live['checks'].values())
    assert manual['status']=='PASS' and all(v=='PASS' for v in manual['checks'].values())
    assert manual['fixture']=={'files':90,'families':47,'days':8,'native_RAW':'NOT_RUN'}
    assert 'catalogue_hashes_general_copies_and_both_sqlite_integrities' in manual['checks']
    assert not manual['final']['operations'] and manual['final']['origins']==manual['initial']['origins']
    assert all(manual['final']['archives'].get(k)==v for k,v in manual['initial']['archives'].items())
    assert all(row['actual_sha']==row['sha256_current'] for row in manual['final']['files'])
    browser=json.loads((folder/'pre5-browser/results.json').read_text())
    assert browser['status']=='PASS' and len(browser['cases'])==8 and all(x['status']=='PASS' for x in browser['cases'])


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
        shutil.copyfile(Path('docs/pre5')/name,assets/name)
    shutil.copyfile('qa/pre3/read_only_diagnosis.py',assets/'read_only_diagnosis.py')
    (assets/'QA-SOURCE-DIFF.patch').write_bytes(subprocess.check_output(['git','diff',BUILD,DOC,'--','app','tests','qa','Dockerfile','requirements.txt','requirements-rc.constraints.txt']))
    c.dump(assets/'ACCEPTANCE.json',APPROVAL)
    for name in ('REPORT.md','EVIDENCE.json','ARCHITECTURE.md'):
        (assets/('development-'+name)).write_text(c.git('show',DOC+':docs/pre5/'+name)+'\n')
    for name in ('Dockerfile','requirements.txt','requirements-rc.constraints.txt','compose.removable.yaml','compose.nas-source.yaml'):
        (assets/name).write_bytes(subprocess.check_output(['git','show',BUILD+':'+name]))
    (assets/'compose.pre5.yaml').write_text(c.git('show',BUILD+':compose.example.yaml')+'\n')
    c.dump(assets/'SOURCE-IDENTITY.json',{'accepted_hotfix':HOTFIX,'versioned_build_source':BUILD,'documentation':DOC,
        'publisher':os.environ['GITHUB_SHA'],'version':VERSION,'application_difference_from_final_QA':'none; version already tested',
        'backend_source':APPROVAL['backend_source'],'backend_delta':APPROVAL['reviewed_backend_delta'],
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
assert __version__=='1.0.0-pre.5'
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
    work=Path(work);assets=work/'release-assets';folder=work/'runtime'
    qualify_runtime_folder(folder,BUILD)
    for path in sorted(folder.glob('*.json')):shutil.copyfile(path,assets/('release-'+path.name))
    for path in sorted(folder.glob('*.log')):shutil.copyfile(path,assets/('release-'+path.name))
    for name in ('pre4-browser','pre5-browser'):
        shutil.copyfile(folder/name/'results.json',assets/('release-'+name+'-results.json'))
    for path in sorted((folder/'pre4-historical').glob('*.log')):
        shutil.copyfile(path,assets/('release-pre4-historical-'+path.name))
    c.dump(work/'runtime-passed.json',{'status':'PASS','build':BUILD})


def delta(work):
    from acceptance import passing_xml
    work=Path(work);folder=work/'delta/f14-qa/targets/results'
    count=passing_xml(folder/'result.xml',21)
    assert json.loads((folder/'exit.json').read_text())['returncode']==0
    shutil.copyfile(folder/'result.xml',work/'release-assets/release-delta-tests.xml')
    c.dump(work/'delta-passed.json',{'status':'PASS','build':BUILD,'tests':count})
    c.dump(work/'release-assets/release-delta-tests.json',{'status':'PASS','build':BUILD,'tests':count,
        'selectors':json.loads(Path(__file__).with_name('DELTA-TESTS.json').read_text())})


def reserve(work):
    context();source_audit();free();unchanged(work)
    assert json.loads((Path(work)/'runtime-passed.json').read_text())=={'status':'PASS','build':BUILD}
    assert json.loads((Path(work)/'delta-passed.json').read_text())['build']==BUILD
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
    compose=assets/'compose.pre5.yaml';text=compose.read_text();assert text.count(IMAGE)==1;compose.write_text(text.replace(IMAGE,ref))
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
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['audit','prepare','verify-image','runtime','delta','reserve','finish','release-guard','post'])
    ap.add_argument('--work',type=Path);ap.add_argument('--ref');ap.add_argument('--digest');a=ap.parse_args()
    if a.command=='audit':source_audit()
    elif a.command=='verify-image':verify_image(a.work,a.ref)
    elif a.command in ('finish','release-guard','post'):globals()[a.command.replace('-','_')](a.work,a.digest)
    else:globals()[a.command](a.work)

if __name__=='__main__':main()
