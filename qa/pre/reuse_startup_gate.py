"""Reuse the exact passed targeted gate after changes ONLY to container QA/docs.

The original run failed later in its container QA, not in these 118 tests.
This is not a replacement PASS: verify source equality, the successful step,
original artifact ZIP digest and every JUnit case before reusing its evidence.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from urllib import request,error
import xml.etree.ElementTree as ET
import zipfile

BASE='12463d2283753671a2489d9098447c451d3858a6'
RUN=40904815727
ARTIFACT=12911476422
DIGEST='sha256:32ab7889908039cee4ff4600c721f419a0aadac663aba0fed52b0f71b1f800b0'
REPO='heller-adrian/Bibliothekar'
subprocess.run(['git','merge-base','--is-ancestor',BASE,'HEAD'],check=True)
subprocess.run(['git','diff','--exit-code',BASE,'HEAD','--','app','tests','requirements.txt',
                'requirements-rc.constraints.txt','Dockerfile','qa/f14'],check=True)
class Redirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):
        assert url.startswith('https://')
        redirected=super().redirect_request(req,fp,code,msg,headers,url)
        if redirected:redirected.remove_header('Authorization')
        return redirected

def get(route):
    req=request.Request('https://api.github.com/repos/'+REPO+'/'+route,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    try:
        with request.build_opener(Redirect()).open(req,timeout=60) as r:return r.read()
    except error.HTTPError as e:raise RuntimeError('Accepted gate unavailable HTTP '+str(e.code)) from None

run=json.loads(get(f'actions/runs/{RUN}'))
assert run['head_sha']==BASE and run['status']=='completed' and run['run_attempt']==1
jobs=json.loads(get(f'actions/runs/{RUN}/jobs'))['jobs']
steps=[s for j in jobs for s in j['steps'] if s['name']=='Isolated targeted Python regressions']
assert len(steps)==1 and steps[0]['conclusion']=='success'
meta=json.loads(get(f'actions/artifacts/{ARTIFACT}'))
assert meta['digest']==DIGEST and not meta['expired'] and meta['workflow_run']['id']==RUN and meta['workflow_run']['head_sha']==BASE
raw=get(f'actions/artifacts/{ARTIFACT}/zip')
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==DIGEST
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    names=[n for n in z.namelist() if n=='targeted.xml' or n.endswith('/targeted.xml')]
    assert len(names)==1
    xml=z.read(names[0])
cases=list(ET.fromstring(xml).iter('testcase'))
assert len(cases)==118 and all(all(c.find(k) is None for k in ('failure','error','skipped')) for c in cases)
root=Path(os.environ['QA_WORK']);(root/'targeted.xml').write_bytes(xml)
(root/'accepted-targeted-evidence.json').write_text(json.dumps({'status':'PASS','reused':True,'run':RUN,
    'source':BASE,'artifact':ARTIFACT,'artifact_digest':DIGEST,'passed':118,
    'app_tests_dependencies_unchanged':True},indent=2))
print('Reused 118 passed Linux regressions from exact unchanged code; original ZIP digest verified.')
