"""Read/checksum helpers copied from the successful OCI-aware pre publisher.
No tag, release or image writer lives in this module.
"""
import base64,hashlib,io,json,os,re,stat,subprocess,zipfile
from pathlib import Path,PurePosixPath
from urllib import error,parse,request
import oci
REPO='heller-adrian/Bibliothekar'
PREFIX='heller-adrian/bibliothekar'
REGISTRY='https://ghcr.io'
def run(*args):
    return subprocess.check_output(args,text=True).strip()

def git(*args):return run('git',*args)

def dump(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')

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

def registry_manifest(reference,*,missing=False,blob=False):
    credentials=base64.b64encode((os.environ['GITHUB_ACTOR']+':'+os.environ['GH_TOKEN']).encode()).decode()
    token_raw,_=http(REGISTRY+'/token?'+parse.urlencode({'service':'ghcr.io','scope':'repository:'+PREFIX+':pull'}),
                     {'Authorization':'Basic '+credentials})
    token=json.loads(token_raw)['token']
    headers={'Authorization':'Bearer '+token,'Accept':','.join([
        *sorted(oci.INDEX_TYPES|oci.MANIFEST_TYPES)])}
    # A 404 may only mean MANIFEST_UNKNOWN; auth/network/other errors block.
    req=request.Request(REGISTRY+'/v2/'+PREFIX+('/blobs/' if blob else '/manifests/')+reference,headers=headers)
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

def checksums(assets):
    assets=Path(assets)
    files=sorted(p for p in assets.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    assert all(not p.is_symlink() and '\n' not in p.name and '\\' not in p.name for p in files)
    (assets/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
