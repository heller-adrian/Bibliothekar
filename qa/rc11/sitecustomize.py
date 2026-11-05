"""QA-only fault observer, mounted read-only; never copied into the image.
The original supervisor and web command remain unchanged.
"""
import json
import os
from pathlib import Path
import signal
import sys

boundary=os.environ.get('RC11_QA_BOUNDARY','')
marker=Path('/qa-evidence/checkpoint.json')
is_web = 'app.main:app' in sys.argv
if boundary and is_web and not marker.exists():
    def stop(publication=None):
        with marker.open('w') as stream:
            json.dump({'boundary':boundary,'pid':os.getpid(),'uid':os.getuid(),'gid':os.getgid(),'publication':str(publication) if publication else None},stream)
            stream.flush();os.fsync(stream.fileno())
        os.kill(os.getpid(),signal.SIGKILL)
    original_mkdir=Path.mkdir
    def mkdir(self,*a,**kw):
        result=original_mkdir(self,*a,**kw)
        if boundary=='folders' and self==Path('/workspace/Trash'):stop()
        return result
    if boundary=='folders':Path.mkdir=mkdir
    original_replace=os.replace
    def replace(src,dst,*a,**kw):
        if boundary=='uncommitted-state' and str(dst)=='state.json':
            fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=kw.get('src_dir_fd'))
            with os.fdopen(fd) as stream:value=json.load(stream)
            if value.get('storage_initialization',{}).get('phase')=='prepared':stop()
        return original_replace(src,dst,*a,**kw)
    if boundary=='uncommitted-state':os.replace=replace
    original_link=os.link
    def link(src,dst,*a,**kw):
        result=original_link(src,dst,*a,**kw)
        if boundary=='claim-linked' and str(dst)=='.bibliothekar-instance.json':stop()
        return result
    if boundary=='claim-linked':os.link=link
    original_unlink=os.unlink
    def unlink(path,*a,**kw):
        result=original_unlink(path,*a,**kw)
        if boundary=='claim-unlinked' and str(path).split('/')[-1].startswith('.bibliothekar-claim-'):stop()
        if boundary=='operation-unlink' and str(path).split('/')[-1].startswith('operation-') and str(path).endswith('.json'):stop()
        return result
    if boundary in {'operation-unlink','claim-unlinked'}:os.unlink=unlink
    def trace(frame,event,arg):
        if event=='call':
            return trace if frame.f_code.co_name in {'ensure_schema_version_table','_ensure_registry_schema_table','ensure_settings_file','initialize_database','initialize_library_registry','recover_trash_restores','_lock','_write'} else None
        if event!='return':return trace
        name=frame.f_code.co_name;filename=Path(frame.f_code.co_filename).name
        targets={'ensure_schema_version_table':'database-header','_ensure_registry_schema_table':'registry-header','ensure_settings_file':'config','initialize_database':'database','initialize_library_registry':'registry','recover_trash_restores':'recovery'}
        if targets.get(name)==boundary:stop()
        if filename=='root_operations.py' and name=='_lock' and boundary=='private-lock' and Path(frame.f_locals['path']).name=='trash-recovery.lock':stop()
        if filename=='root_operations.py' and name=='_write':
            path=Path(frame.f_locals['path']);value=frame.f_locals['value'];phase=value.get('storage_initialization',{}).get('phase')
            if (boundary=='instance-intent' and path.name=='instance.json' and value.get('phase')=='initializing'
                or boundary=='instance-ready' and path.name=='instance.json' and value.get('phase')=='ready'
                or boundary=='reservation' and path.name.startswith('operation-') and value.get('kind')=='startup'
                or boundary=='prepared' and path.name=='state.json' and phase=='prepared'
                or boundary=='completed' and path.name=='state.json' and phase=='completed'
                or boundary=='completion-receipt' and path.name.startswith('bootstrap-completed-')
                or boundary=='operation-archive' and path.name.startswith('bootstrap-operation-')
                or boundary=='finished-receipt' and path.name.startswith('finished-')
                or boundary=='control-format' and path.name=='state.json' and value.get('control_migration')
                or boundary=='adoption-receipt' and path.name.startswith('rc11-adoption-')):stop(path)
        return trace
    sys.settrace(trace)
