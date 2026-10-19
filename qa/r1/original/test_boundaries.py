from common import *
import pytest,subprocess,threading,time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

@pytest.mark.parametrize('mode',['logout','password','expiry','session_reset'])
def test_session_lifecycle(tmp_path,monkeypatch,mode):
    case,ev,data,db,ws=setup(tmp_path,'P5-B-session-'+mode,monkeypatch)
    client=TestClient(main.app,follow_redirects=False);csrf=login(client)
    assert client.get('/api/libraries/current').status_code==200
    if mode=='logout':assert client.post('/auth/logout',headers={'X-Bibliothekar-CSRF':csrf}).status_code==200
    elif mode=='password':monkeypatch.setenv('BIBLIOTHEKAR_ADMIN_PASSWORD',SECRET+'changed')
    elif mode=='expiry':
        key=hashlib.sha256(client.cookies.get('bibliothekar_session').encode()).hexdigest();old=security._SESSIONS[key];security._SESSIONS[key]=(0,old[1],old[2])
    else:security._SESSIONS.clear()
    r=client.get('/api/libraries/current');finish(case,ev,{'mode':mode,'status':r.status_code,'body':r.text,'session_reset_scope':'cleared in-memory store; separate process inheritance verified statically'})
    client.close();assert r.status_code==401

@pytest.mark.parametrize('scheme,forced',[('http',False),('https',False),('http',True)])
def test_cookie_attributes(tmp_path,monkeypatch,scheme,forced):
    case,ev,data,db,ws=setup(tmp_path,f'P5-B-cookies-{scheme}-{forced}',monkeypatch)
    monkeypatch.setenv('BIBLIOTHEKAR_COOKIE_SECURE','true' if forced else 'false')
    client=TestClient(main.app,base_url=scheme+'://testserver');r=client.post('/auth/login',json={'password':SECRET});cookies=r.headers.get_list('set-cookie')
    attributes=[c.split(';')[1:] for c in cookies]
    finish(case,ev,{'status':r.status_code,'cookie_attributes':attributes,'scheme':scheme,'forced':forced});client.close()
    assert r.status_code==200 and len(cookies)==2
    assert 'HttpOnly' in cookies[0] and 'SameSite=strict' in cookies[0]
    assert ('Secure' in cookies[0])==(scheme=='https' or forced)

@pytest.mark.parametrize('origin,referer,fetch_site,expected',[(None,None,None,200),('null',None,None,403),('https://other.invalid',None,None,403),('http://testserver',None,'same-site',403),('http://testserver',None,'cross-site',403),(None,'http://testserver/page',None,200),(None,'https://other.invalid/page',None,403),('http://user@testserver',None,None,403),('http://[bad',None,None,403)])
def test_origin_rules(tmp_path,monkeypatch,origin,referer,fetch_site,expected):
    name=hashlib.sha256(str((origin,referer,fetch_site)).encode()).hexdigest()[:8]
    case,ev,data,db,ws=setup(tmp_path,'P5-B-origin-'+name,monkeypatch)
    client=TestClient(main.app,raise_server_exceptions=False);csrf=login(client);h={'X-Bibliothekar-CSRF':csrf}
    if origin is not None:h['Origin']=origin
    if referer is not None:h['Referer']=referer
    if fetch_site:h['Sec-Fetch-Site']=fetch_site
    r=client.post('/auth/logout',headers=h);finish(case,ev,{'origin':origin,'referer':referer,'fetch_site':fetch_site,'expected':expected,'status':r.status_code,'body':r.text});client.close();assert r.status_code==expected

@pytest.mark.parametrize('mode',['malformed_json','list_json','surrogate_password','non_ascii_csrf','oversized_login'])
def test_malformed_security_input(tmp_path,monkeypatch,mode):
    case,ev,data,db,ws=setup(tmp_path,'P5-B-input-'+mode,monkeypatch)
    client=TestClient(main.app,raise_server_exceptions=False)
    if mode=='non_ascii_csrf':
        login(client);r=client.post('/auth/logout',headers=[(b'x-bibliothekar-csrf',b'\xff')]);expected=403
    elif mode=='malformed_json':r=client.post('/auth/login',content='{');expected=401
    elif mode=='list_json':r=client.post('/auth/login',json=[]);expected=401
    elif mode=='surrogate_password':r=client.post('/auth/login',content='{"password":"\\ud800"}',headers={'content-type':'application/json'});expected=401
    else:r=client.post('/auth/login',json={'password':'x'*17000});expected=413
    finish(case,ev,{'mode':mode,'status':r.status_code,'expected':expected,'body':r.text,'secret_in_response':SECRET in r.text});client.close();assert r.status_code==expected


def test_login_limit_and_forwarded_headers(tmp_path,monkeypatch):
    case,ev,data,db,ws=setup(tmp_path,'P5-B-rate-limit',monkeypatch)
    client=TestClient(main.app);statuses=[]
    for n in range(9):statuses.append(client.post('/auth/login',json={'password':'synthetic-wrong'},headers={'X-Forwarded-For':f'192.0.2.{n+1}'}).status_code)
    finish(case,ev,{'statuses':statuses,'scope':'TestClient does not trust forwarded client headers; deployment proxy separately assessed'});client.close();assert statuses==[401]*8+[429]

@pytest.mark.parametrize('device_id',['.','..','SAFE-UUID'])
def test_helper_mount_id(tmp_path,monkeypatch,device_id):
    case,ev,data,db,ws=setup(tmp_path,'P5-D-id-'+{'.':'dot','..':'dotdot','SAFE-UUID':'valid'}[device_id],monkeypatch)
    from app import source_helper as sh
    root=case/'synthetic-mounts';root.mkdir();calls=[];mounted=[False]
    node={'type':'disk','rm':1,'tran':'usb','model':'synthetic card reader','children':[{'type':'part','fstype':'vfat','path':'/synthetic-dev/p1','kname':'p1','uuid':device_id,'size':1024}]}
    monkeypatch.setattr(sh,'MOUNT_ROOT',root);monkeypatch.setattr(sh,'DEVICE_NODE_ROOT',case/'fake-devnodes');monkeypatch.setattr(sh,'lsblk',lambda:{'blockdevices':[node]})
    def run(*args,**kw):
        calls.append(args)
        if args[0]=='mount':mounted[0]=True
        return subprocess.CompletedProcess(args,0,'{"filesystems":[]}','')
    monkeypatch.setattr(sh,'run',run);monkeypatch.setattr(sh,'_ensure_mount_device_node',lambda item:('/synthetic-dev/p1',False))
    monkeypatch.setattr(sh,'_mount_info',lambda path:{'source':'/synthetic-dev/p1','options':'ro,nosuid,nodev,noexec'} if mounted[0] else None)
    client=TestClient(sh.app);r=client.post('/mount',json={'device_path':'/synthetic-dev/p1'});client.close()
    target=next(c[-1] for c in calls if c[0]=='mount');resolved=Path(target).resolve()
    finish(case,ev,{'device_id':device_id,'safe_id':sh.safe_id(device_id),'commands':calls,'status':r.status_code,'target':target,'target_resolved':str(resolved),'mock_only':True,'no_real_mount_or_mknod':True})
    assert resolved!=root and root in resolved.parents


def test_helper_id_collision(tmp_path,monkeypatch):
    case,ev,data,db,ws=setup(tmp_path,'P5-D-label-collision',monkeypatch)
    from app import source_helper as sh
    root=case/'mounts';root.mkdir();calls=[]
    parent={'type':'disk','rm':1,'tran':'usb','model':'synthetic reader','children':[{'type':'part','fstype':'vfat','path':f'/synthetic-dev/p{i}','kname':f'p{i}','label':label,'size':1024} for i,label in [(1,'Camera/One'),(2,'Camera?One')]]}
    monkeypatch.setattr(sh,'MOUNT_ROOT',root);monkeypatch.setattr(sh,'DEVICE_NODE_ROOT',case/'fake-nodes');monkeypatch.setattr(sh,'lsblk',lambda:{'blockdevices':[parent]})
    monkeypatch.setattr(sh,'run',lambda *a,**kw:(calls.append(a) or subprocess.CompletedProcess(a,0,'{"filesystems":[]}','')))
    monkeypatch.setattr(sh,'_mount_info',lambda p:{'source':'/synthetic-dev/p1','options':'ro,nosuid,nodev,noexec'})
    found=sh.devices();finish(case,ev,{'devices':found,'commands':calls,'mock_only':True})
    assert len({d['device_id'] for d in found})==2 and not any(c[0]=='umount' for c in calls)

@pytest.mark.parametrize('path',['../outside','/absolute','a/../../b','safe','safe\\..\\outside','safe∕..∕outside'])
def test_import_path_limits(tmp_path,monkeypatch,path):
    case,ev,data,db,ws=setup(tmp_path,'P5-C-path-'+hashlib.sha256(path.encode()).hexdigest()[:8],monkeypatch)
    root=case/'import-root';root.mkdir();(root/'safe').mkdir();monkeypatch.setattr(main,'IMPORT_ROOT',root)
    try:result=main.resolve_import_source(path);answer={'accepted':True,'resolved':str(result)}
    except Exception as e:answer={'accepted':False,'error':repr(e)}
    finish(case,ev,{'input':path,'answer':answer});assert answer['accepted']==(path=='safe')


def test_trash_component_swap(tmp_path,monkeypatch):
    case,ev,data,db,ws=setup(tmp_path,'P5-C-trash-symlink-swap-verified',monkeypatch)
    from app import trash_selective as ts
    outside=case/'outside-managed-workspace';outside.mkdir();sentinel=outside/'A.JPG';sentinel.write_bytes(b'synthetic-trash-A.JPG')
    snapshot(case,ev/'before-canary-swap.json')
    real=ts._move_checked;once=[True]
    def swap(source,target,*a,**kw):
        if once[0]:once[0]=False;(ws/'Papierkorb').rename(ws/'saved-original-trash');(ws/'Papierkorb').symlink_to(outside,target_is_directory=True)
        return real(source,target,*a,**kw)
    monkeypatch.setattr(ts,'_move_checked',swap)
    try:result={'ok':True,'value':ts.delete_selected_trash_files([Path(p) for p in data['databases']],ws,['A.JPG'])}
    except Exception as e:result={'ok':False,'error':repr(e)}
    finish(case,ev,{'operation':result,'outside_sentinel_exists':sentinel.exists(),'outside_path':str(sentinel),'scope':'outside configured workspace but inside synthetic case; all host writes sandboxed'})
    assert sentinel.is_file() and sentinel.read_bytes()==b'synthetic-trash-A.JPG'
