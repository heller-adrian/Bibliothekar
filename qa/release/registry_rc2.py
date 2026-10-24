"""Read-only GHCR manifest checks for the explicitly authorized RC2 publication."""
import base64,hashlib,json,os,re,sys,urllib.request,urllib.error,urllib.parse
from pathlib import Path
REPO='heller-adrian/bibliothekar';TAG='1.0.0-rc.2'
out=Path('release-assets');out.mkdir(exist_ok=True)
secret=os.environ['GH_TOKEN'];actor=os.environ['GITHUB_ACTOR']
request=urllib.request.Request('https://ghcr.io/token?'+urllib.parse.urlencode({'service':'ghcr.io','scope':f'repository:{REPO}:pull'}),headers={'Authorization':'Basic '+base64.b64encode((actor+':'+secret).encode()).decode()})
with urllib.request.urlopen(request,timeout=30) as response:token=json.load(response)['token']
headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'}
def fetch(path,absent_ok=False):
 req=urllib.request.Request('https://ghcr.io/v2/'+REPO+'/'+path,headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=30) as response:return response.read(),dict(response.headers)
 except urllib.error.HTTPError as error:
  if absent_ok and error.code==404:return None,{}
  raise

def manifest(ref,absent_ok=False):
 data,h=fetch('manifests/'+ref,absent_ok)
 if data is None:return None
 digest='sha256:'+hashlib.sha256(data).hexdigest()
 assert digest==next(v for k,v in h.items() if k.lower()=='docker-content-digest')
 return {'digest':digest,'raw':data}

def all_tags():
 data,h=fetch('tags/list?n=1000');assert not any(k.lower()=='link' for k in h),'Refusing incomplete tag inventory'
 tags=json.loads(data)['tags'];return {tag:manifest(tag)['digest'] for tag in sorted(tags)}
mode=sys.argv[1]
if mode=='before':
 tags=all_tags();assert '1.0.0-rc.1' in tags and TAG not in tags
 (out/'registry-tags-before.json').write_text(json.dumps(tags,indent=2))
 assert manifest(TAG,True) is None
 print('Existing tag digests recorded; RC2 name unused:',len(tags))
elif mode=='absent':
 assert manifest(TAG,True) is None,'RC2 tag already exists; refusing replacement'
elif mode=='after':
 digest=Path('release-assets/IMAGE-DIGEST.txt').read_text().strip().split('@')[1]
 assert re.fullmatch('sha256:[0-9a-f]{64}',digest)
 published=manifest(digest);assert published['digest']==digest
 assert manifest(TAG)['digest']==digest
 (out/'registry-manifest.json').write_bytes(published['raw'])
 before=json.loads((out/'registry-tags-before.json').read_text());after=all_tags()
 assert all(after.get(k)==v for k,v in before.items()),'An existing tag changed'
 assert set(after)-set(before)=={TAG},'Unexpected new tag set'
 (out/'registry-tags-after.json').write_text(json.dumps(after,indent=2))
 print('Published manifest verified; all previous tag digests unchanged:',len(before))
else:raise SystemExit('Unknown mode')
