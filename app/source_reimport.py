"""Explicit reimports retain verified catalogued copies; uncertainty blocks.

No archive scan/adoption, deletion, or catalogue rewrite. Missing copies can
only become new import candidates after every registered projection is checked.
The normal source SHA/family pipeline and exclusive publication still decide.
"""
from pathlib import Path
import hashlib
import os
import stat

from app.database import database_connection
from app.library_registry import list_libraries
from app.storage_config import storage_paths
from app.import_publication import _parent
from app.pipeline import PipelineError


def catalogued_copy_presence(registry, origins):
    """Fast, non-mutating presence hint, never a content-integrity proof.

    Explicit reimport continues through retained_origins and its full hashes.
    """
    return _retained_origins(registry, origins, verify_contents=False)


def retained_origins(registry, origins, *, progress_callback=None):
    return _retained_origins(registry, origins, verify_contents=True, progress_callback=progress_callback)


def _retained_origins(registry, origins, *, verify_contents, progress_callback=None):
    libraries = list_libraries(registry, active_only=False)
    if not libraries:
        raise PipelineError('Erneute Sicherung benötigt eine eindeutig registrierte Bibliothek.')
    wanted = {str(row['sha256']) for row in origins}
    present = set()
    seen = set()
    for library in libraries:
        database = Path(library['database_path'])
        if not database.is_file():
            raise PipelineError('Bibliotheksdatenbank für erneute Sicherungsprüfung fehlt.')
        paths = storage_paths(Path(library['workspace_root']))
        with database_connection(database) as c:
            rows = [dict(r) for r in c.execute('''SELECT f.sha256_original,f.sha256_current,f.size_bytes,
                f.current_relative_path,f.current_root_kind,j.working_path FROM files f
                JOIN jobs j ON j.id=f.job_id WHERE j.state='completed' ''')]
        for row in rows:
            digest = str(row['sha256_original'] or '')
            if digest not in wanted:
                continue
            roots = {'camera_archive': [Path(library['archive_root'])],
                     'shared_workspace': [paths['backup_root'], Path(library['work_root'])],
                     'trash': [paths['trash_root']],
                     'job_root': [Path(row['working_path'])] if row['working_path'] else []}.get(row['current_root_kind'], [])
            seen.add(digest)
            relative = str(row['current_relative_path'] or '')
            if not roots or not relative or Path(relative).is_absolute() or any(p in ('', '.', '..') for p in relative.replace('\\','/').split('/')) or '\\' in relative:
                raise PipelineError('Sicherungsort ist nicht eindeutig; erneute Sicherung bleibt gesperrt.')
            for root in roots:
                # An unavailable mount/root must not masquerade as an absent file.
                try:
                    with _parent(root/'probe'):
                        pass
                    try:
                        with _parent(root/relative) as (fd,name):
                            handle = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                            try:
                                before=os.fstat(handle)
                                if not stat.S_ISREG(before.st_mode):
                                    raise PipelineError('Sicherungspfad ist keine reguläre Datei.')
                                h=hashlib.sha256()
                                if verify_contents:
                                    while block:=os.read(handle,1024*1024):
                                        h.update(block)
                                        if progress_callback is not None: progress_callback(len(block))
                                after=os.fstat(handle);bound=os.stat(name,dir_fd=fd,follow_symlinks=False)
                                fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
                                if (fields(before)!=fields(after) or fields(after)!=fields(bound)
                                    or after.st_size!=int(row['size_bytes']) or (verify_contents and h.hexdigest()!=str(row['sha256_current'] or digest))):
                                    raise PipelineError('Vorhandene Sicherung ist verändert oder nicht integre; erneute Sicherung sicher gesperrt.')
                                present.add(digest)
                            finally:os.close(handle)
                    except FileNotFoundError:
                        pass
                except OSError as error:
                    raise PipelineError('Sicherungswurzel nicht sicher erreichbar; Abwesenheit nicht nachgewiesen.') from error
    if wanted - seen:
        raise PipelineError('Katalogherkunft ist keiner registrierten Bibliothek zugeordnet; erneute Sicherung gesperrt.')
    return [row for row in origins if str(row['sha256']) in present]
