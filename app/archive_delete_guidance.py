"""Read-only qualification of a manual whole-event deletion instruction."""
import os
from pathlib import Path, PurePosixPath
import stat


def qualify_event_folder(database_path,archive_root,workspace_path,cr_id,release_stock):
    from app.archive_reversal import _manifest_path,_read_json
    from app.archive_release_stock import _verify_copy_row
    from app.archive_change_assistant import _sha256_file
    result={'qualified':False,'reason':'complete_event_inventory_not_verified'}
    manifest_path=_manifest_path(workspace_path,cr_id)
    if not manifest_path.is_file() or manifest_path.is_symlink():return result
    manifest=_read_json(manifest_path)
    if not manifest.get('delete_event') or manifest.get('change_request_id')!=cr_id:return result
    relative=PurePosixPath(str(manifest.get('original_root') or ''))
    if len(relative.parts)<2 or relative.is_absolute() or '..' in relative.parts:return result
    root=Path(archive_root)
    target=root.joinpath(*relative.parts)
    result['path']=str(target)
    current=root
    for part in relative.parts:
        current=current/part
        if current.is_symlink():return result
    rows=release_stock.get('rows') or []
    if not release_stock.get('copy_verified'):return result
    expected={str(row['old_path']):(int(row['expected_size_bytes']),str(row['expected_sha256'])) for row in rows}
    if len(expected)!=len(rows):return result
    for row in rows:
        state,*_=_verify_copy_row(row,Path(archive_root),Path(workspace_path),require_archive_source=False)
        if state!='release_copy_verified':return result
    document=manifest.get('event_json')
    if document:
        expected[str(document['relative_path'])]=(int(document['size_bytes']),str(document['sha256']))
    if set(manifest.get('original_file_paths') or [])!=set(expected):return result
    if any(not PurePosixPath(p).is_relative_to(relative) for p in expected):return result
    directories=set(manifest.get('original_directories') or [])
    if not target.exists():return {**result,'qualified':True,'reason':None}
    def failed(error):raise error
    try:
        for folder,names,files in os.walk(target,followlinks=False,onerror=failed):
            folder=Path(folder)
            if folder.relative_to(root).as_posix() not in directories:return {**result,'reason':'unknown_event_directory'}
            for name in names:
                if (folder/name).is_symlink():return {**result,'reason':'unsafe_event_entry'}
            for name in files:
                path=folder/name
                info=path.lstat();rel=path.relative_to(root).as_posix()
                if not stat.S_ISREG(info.st_mode) or rel not in expected:return {**result,'reason':'unknown_event_file'}
                size,sha=expected[rel]
                if info.st_size!=size or _sha256_file(path)!=sha:return {**result,'reason':'changed_event_file'}
    except OSError:return {**result,'reason':'event_scan_failed'}
    return {**result,'qualified':True,'reason':None}
