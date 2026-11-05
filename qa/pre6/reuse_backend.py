"""Reuse only exact immutable 98-node backend evidence; never run a write API."""
import sys,os,json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,'docs/pre5/release')
import core as c
SOURCE='d64bfba83af80bfe79dfce80ccfc017cf49aad12'
ARTIFACT=13197717109
DIGEST='c2e537bda5d1eb1a5c3889060ad2f5033697b7ec32e8a9d382a0216b46a15446'
root=Path(os.environ['WORK'])
for name in ['app','tests','Dockerfile','requirements.txt','requirements-rc.constraints.txt','qa/f14','qa/pre6/targets.json']:
 assert c.git('rev-parse',SOURCE+':'+name)==c.git('rev-parse','HEAD:'+name), 'Backend source changed: '+name
run=c.github('repos/'+c.REPO+'/actions/runs/41562234548')
assert run['head_sha']==SOURCE and run['status']=='completed' and run['conclusion']=='failure'
jobs=c.github('repos/'+c.REPO+'/actions/runs/41562234548/jobs')['jobs']
assert len(jobs)==1
steps={s['number']:s['conclusion'] for s in jobs[0]['steps']}
assert steps[3]=='success' and steps[4]=='failure' and steps[5]=='skipped'
meta=c.github('repos/'+c.REPO+'/actions/artifacts/'+str(ARTIFACT))
assert not meta['expired'] and meta['digest']=='sha256:'+DIGEST
assert meta['workflow_run']['head_sha']==SOURCE and meta['workflow_run']['id']==41562234548
raw,_=c.http(meta['archive_download_url'],{'Authorization':'Bearer '+os.environ['GH_TOKEN']})
assert hashlib.sha256(raw).hexdigest()==DIGEST
(root/'accepted-backend.zip').write_bytes(raw)
extracted=root/'accepted-backend';c.safe_extract(raw,extracted)
evidence=json.loads((extracted/'EVIDENCE.json').read_text());assert evidence['source']==SOURCE
relative='f14-qa/targets/results/result.xml'
assert hashlib.sha256((extracted/relative).read_bytes()).hexdigest()==evidence['files'][relative]
cases=list(ET.parse(extracted/relative).getroot().iter('testcase'))
assert len(cases)==98 and len({(c.get('classname'),c.get('name')) for c in cases})==98
assert all(not any(c.find(s) is not None for s in ('failure','error','skipped')) for c in cases)
output={'status':'PASS','tests':98,'failures':0,'errors':0,'skipped':0,'source':SOURCE,'checked_current_commit':os.environ['GITHUB_SHA'],'source_trees_identical':True,'run':41562234548,'artifact_id':ARTIFACT,'artifact_sha256':DIGEST}
(root/'BACKEND-EVIDENCE.json').write_text(json.dumps(output,indent=2))
print(json.dumps(output))
