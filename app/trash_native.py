"""One unprivileged, Landlock-confined filesystem mutation; no service/socket.
Executed with inherited directory FDs. Never elevates credentials or mounts.
"""
import ctypes,errno,json,os,sys,uuid


def install(root):
    if os.uname().machine not in {'x86_64','aarch64'}:
        raise OSError(errno.ENOSYS,'Unqualified Landlock syscall ABI')
    libc=ctypes.CDLL(None,use_errno=True)
    abi=libc.syscall(444,0,0,1)
    if abi<2:
        raise OSError(errno.ENOSYS,'Landlock ABI 2 or newer required')
    mask=(1<<1)|(1<<4)|(1<<5)|(1<<7)|(1<<8)|(1<<12)|(1<<13)
    class Ruleset(ctypes.Structure):_fields_=[('access',ctypes.c_uint64)]
    class Beneath(ctypes.Structure):
        _pack_=1
        _fields_=[('access',ctypes.c_uint64),('parent',ctypes.c_int)]
    attr=Ruleset(mask);fd=libc.syscall(444,ctypes.byref(attr),ctypes.sizeof(attr),0)
    if fd<0:raise OSError(ctypes.get_errno(),'Landlock ruleset unavailable')
    try:
        rule=Beneath(mask,root)
        if libc.syscall(445,fd,1,ctypes.byref(rule),0)<0:raise OSError(ctypes.get_errno(),'Landlock rule rejected')
        if libc.prctl(38,1,0,0,0)<0:raise OSError(ctypes.get_errno(),'No-new-privileges unavailable')
        if libc.syscall(446,fd,0)<0:raise OSError(ctypes.get_errno(),'Landlock restriction rejected')
    finally:os.close(fd)
    return abi


def name(value):
    if not isinstance(value,str) or not value or value in {'.','..'} or '/' in value or '\\' in value or '\0' in value:
        raise OSError(errno.EINVAL,'Not a single relative filename')
    return value


def rename(command):
    libc=ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'renameat2'):raise OSError(errno.ENOSYS,'Atomic rename unavailable')
    fn=libc.renameat2;fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];fn.restype=ctypes.c_int
    if fn(command['src'],os.fsencode(name(command['source'])),command['dst'],os.fsencode(name(command['target'])),0 if command.get('replace') else 1):
        raise OSError(ctypes.get_errno(),'Confined rename denied')
    os.fsync(command['src']);os.fsync(command['dst'])


def execute(c):
    op=c['op']
    if op=='probe':return
    if op=='rename':rename(c)
    elif op=='link':os.link(name(c['source']),name(c['target']),src_dir_fd=c['src'],dst_dir_fd=c['dst'],follow_symlinks=False)
    elif op=='mkdir':os.mkdir(name(c['target']),0o700,dir_fd=c['dst']);os.fsync(c['dst'])
    elif op in {'unlink','rmdir'}:
        n=name(c['target']);i=os.stat(n,dir_fd=c['dst'],follow_symlinks=False)
        if c.get('expected') is not None and [i.st_dev,i.st_ino]!=c['expected']:raise OSError(errno.ESTALE,'Changed private entry')
        (os.unlink if op=='unlink' else os.rmdir)(n,dir_fd=c['dst']);os.fsync(c['dst'])
    elif op=='copy':
        fd=os.open(name(c['target']),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=c['dst'])
        try:
            os.lseek(c['src'],0,os.SEEK_SET)
            while True:
                data=os.read(c['src'],1024*1024)
                if not data:break
                view=memoryview(data)
                while view:view=view[os.write(fd,view):]
            os.fsync(fd)
        finally:os.close(fd)
        os.fsync(c['dst'])
    elif op=='touch':
        fd=os.open(name(c['target']),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=c['dst'])
        try:os.fsync(fd)
        finally:os.close(fd)
        os.fsync(c['dst'])
    elif op=='json':
        temporary='.'+uuid.uuid4().hex+'.tmp';fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=c['dst'])
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                json.dump(c['value'],handle,ensure_ascii=False,sort_keys=True);handle.flush();os.fsync(handle.fileno())
            rename({'src':c['dst'],'source':temporary,'dst':c['dst'],'target':c['target'],'replace':True})
        finally:
            try:os.unlink(temporary,dir_fd=c['dst'])
            except FileNotFoundError:pass
    else:raise OSError(errno.EINVAL,'Unsupported confined mutation')


if __name__=='__main__':
    try:
        command=json.load(sys.stdin);abi=install(command['root']);execute(command)
        print(json.dumps({'ok':True,'landlock_abi':abi,'uid':os.geteuid()}))
    except OSError as error:
        print(json.dumps({'ok':False,'errno':error.errno,'error':str(error)}));sys.exit(1)
