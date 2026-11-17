"""Read-only optional guidance. It never replaces archive completion checks."""
from pathlib import Path,PurePosixPath
import os,stat,hashlib
from app.import_publication import _parent,_verified


def _relative(raw):
    p=PurePosixPath(str(raw))
    if not raw or p.is_absolute() or any(x in ('','.','..') for x in str(raw).split('/')) or '\\' in str(raw):raise ValueError('unsafe path')
    return p


def qualify_rename(archive,rows,*,current_document,replacement,replacement_meta,document_target,archive_label,work_root,work_label,known_directories=()):
    """Require a single prefix rename, every known byte and no unknown entry."""
    try:
        files=[r for r in rows if str(r.get('action'))!='keep' or r.get('old_path')!=r.get('new_path')]
        if not files or any(r.get('action')!='move' or r.get('source_root_kind','camera_archive')!='camera_archive' for r in files):return None
        roots=set()
        for row in files:
            old=_relative(row['old_path']);new=_relative(row['new_path'])
            if len(old.parts)!=len(new.parts):return None
            changed=[i for i,(a,b) in enumerate(zip(old.parts,new.parts)) if a!=b]
            if len(changed)!=1 or changed[0]==len(old.parts)-1:return None
            i=changed[0];roots.add((PurePosixPath(*old.parts[:i+1]),PurePosixPath(*new.parts[:i+1])))
        if len(roots)!=1:return None
        old,new=next(iter(roots))
        if old.parent!=new.parent:return None
        archive=Path(archive);source=archive/str(old);target=archive/str(new)
        if not source.is_dir() or source.is_symlink() or target.exists() or target.is_symlink():return None
        if not current_document or not replacement_meta:return None
        def verify(path,meta):
            with _parent(path) as (fd,name):_verified(fd,name,{'size_bytes':int(meta['size_bytes']),'sha256':str(meta['sha256'])})
        replacement=Path(replacement)
        # Reversal deliberately hardlinks its private Original and Restoration
        # copies. This read-only proof allows those links; import publication's
        # exclusive single-link ownership rule is unchanged.
        with _parent(replacement) as (parent_fd,name):
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=parent_fd)
            try:
                before=os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_size!=int(replacement_meta['size_bytes']):return None
                digest=hashlib.sha256()
                while block:=os.read(fd,1024*1024):digest.update(block)
                after=os.fstat(fd)
                fields=lambda info:(info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
                if digest.hexdigest()!=replacement_meta['sha256'] or fields(before)!=fields(after):return None
            finally:
                os.close(fd)
        old_doc=archive/str(_relative(current_document['relative_path']))
        verify(old_doc,current_document)
        expected=set()
        for row in rows:
            old_path=_relative(row['old_path'])
            if not old_path.is_relative_to(old):continue
            new_path=_relative(row['new_path'])
            if new_path!=new/old_path.relative_to(old):return None
            verify(archive/str(old_path),{'size_bytes':row['expected_size_bytes'],'sha256':row['expected_sha256']})
            expected.add(str(old_path.relative_to(old)))
        if _relative(current_document['relative_path']).is_relative_to(old):expected.add(str(_relative(current_document['relative_path']).relative_to(old)))
        allowed_dirs=set()
        for value in expected:
            allowed_dirs.update(str(p) for p in PurePosixPath(value).parents if str(p)!='.')
        for value in known_directories:
            rel=_relative(value)
            if rel.is_relative_to(old) and rel!=old:allowed_dirs.add(str(rel.relative_to(old)))
        identity_before=source.stat(follow_symlinks=False)
        actual=set()
        def failed(error):
            raise error
        for parent,dirs,names in os.walk(source,followlinks=False,onerror=failed):
            for name in dirs+names:
                path=Path(parent)/name;info=path.lstat()
                if stat.S_ISDIR(info.st_mode) and str(path.relative_to(source)) not in allowed_dirs:return None
                if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):return None
            actual.update(str((Path(parent)/name).relative_to(source)) for name in names)
        if actual!=expected:return None
        identity=source.stat(follow_symlinks=False)
        if (identity.st_dev,identity.st_ino)!=(identity_before.st_dev,identity_before.st_ino) or target.exists() or target.is_symlink():return None
        return [
          {'kind':'rename_archive_folder','title':'Geprüften Ordner umbenennen','source':archive_label+'/'+str(old),'target':archive_label+'/'+str(new),'items':[old.name],
           'detail':'Ordner umbenennen, danach die geprüfte event.json ersetzen. Keine weiteren Archivdateien verändern.','state':'pending','identity':[identity.st_dev,identity.st_ino]},
          {'kind':'replace_event_document','title':'Aktuelle event.json ins Archiv übernehmen','source':work_label+'/'+replacement.relative_to(work_root).as_posix(),
           'target':archive_label+'/'+str(_relative(document_target)),'items':['event.json'],'file_count':1,'state':'pending','detail':'Die bestehende event.json im Archiv durch die vorbereitete neue event.json ersetzen.'}]
    except (KeyError,ValueError,OSError,RuntimeError):return None


def qualify_layout_renames(archive_root, pairs, original_directories, original_files, desired, rows):
    """Use a directory rename only where it exactly implements the reviewed move rows."""
    from app.archive_locations import archive_target_lookup

    existing = archive_target_lookup(archive_root)
    before = {PurePosixPath(path) for path in original_directories}
    after = {PurePosixPath(path) for path in desired}
    files = [PurePosixPath(path) for path in original_files]
    moves = {PurePosixPath(row["old_path"]): row for row in rows
             if row.get("old_path") and row.get("source_root_kind") != "shared_workspace"}
    result = []
    for source, target in sorted(set(pairs)):
        if (source.parent != target.parent or source not in before or source in after
                or target not in after or existing(target.as_posix()) is not None):
            continue
        if (any(source.is_relative_to(PurePosixPath(item["source"])) for item in result)
                or any(target.is_relative_to(PurePosixPath(item["target"])) for item in result)):
            continue
        if {target / path.relative_to(source) for path in before if path.is_relative_to(source)} != {
            path for path in after if path.is_relative_to(target)
        }:
            continue
        members = {}
        for path in files:
            if not path.is_relative_to(source):
                continue
            row = moves.get(path, {})
            relative = path.relative_to(source).as_posix()
            if row.get("action") == "delete":
                continue
            elif (row.get("action") == "move" and row.get("expected_sha256")
                    and row.get("new_path") == (target / relative).as_posix()):
                members[relative] = (row["expected_size_bytes"], row["expected_sha256"])
            else:
                break
        else:
            destinations = {row["new_path"] for row in rows if row.get("new_path")
                            and PurePosixPath(row["new_path"]).is_relative_to(target)}
            if destinations != {(target / relative).as_posix() for relative in members}:
                continue
            info = (archive_root / source).stat(follow_symlinks=False)
            result.append({"source": source.as_posix(), "target": target.as_posix(),
                           "identity": [info.st_dev, info.st_ino], "members": members,
                           "directories": sorted(path.relative_to(source).as_posix()
                                                 for path in before if path != source and path.is_relative_to(source))})
    return result


def layout_rename_state(archive_root, rename):
    """Recheck the directory's identity and contents before suggesting a rename."""
    from app.archive_locations import ArchiveLocationError, archive_target_lookup
    from app.archive_reversal import _matches

    lookup = archive_target_lookup(archive_root)
    try:
        source, target = (lookup(rename[key]) for key in ("source", "target"))
        if (source is None) == (target is None):
            return "blocked"
        root = source or target
        assert root is not None
        info = root.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode) or [info.st_dev, info.st_ino] != rename["identity"]
                or root.relative_to(archive_root.resolve()).as_posix() != rename["source" if source else "target"]):
            return "blocked"
        directories, files = set(), set()
        def walk_error(error):
            raise error
        for directory, names, entries in os.walk(root, followlinks=False, onerror=walk_error):
            for name in names:
                path = Path(directory) / name
                if path.is_symlink():
                    return "blocked"
                directories.add(path.relative_to(root).as_posix())
            for name in entries:
                path = Path(directory) / name
                key = path.relative_to(root).as_posix()
                proof = rename["members"].get(key)
                if not proof or not _matches(path, *proof):
                    return "blocked"
                files.add(key)
        if directories == set(rename["directories"]) and files == set(rename["members"]):
            return "pending" if source else "done"
    except (ArchiveLocationError, OSError, RuntimeError, ValueError):
        pass
    return "blocked"
