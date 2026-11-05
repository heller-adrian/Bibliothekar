"""Display availability is physical presence, never a replacement for mutation guards."""
from pathlib import Path
import os
import stat
from app.database import database_connection
from app.import_publication import _parent
from app.storage_config import storage_paths


def available_families(database, workspace, *, blocked=()):
    central=storage_paths(Path(workspace))['backup_root']
    with database_connection(Path(database)) as c:
        rows=[dict(r) for r in c.execute('''SELECT f.family_id,f.current_relative_path,
            f.current_root_kind,f.size_bytes,j.state FROM files f JOIN jobs j ON j.id=f.job_id''')]
    family={}
    for row in rows:
        ident=row['family_id']
        if ident is None:continue
        valid=False
        raw=str(row['current_relative_path'] or '')
        if (ident not in blocked and row['state']=='completed' and row['current_root_kind']=='shared_workspace'
            and raw and not Path(raw).is_absolute() and '\\' not in raw
            and all(p not in ('','.','..') for p in raw.split('/'))):
            try:
                with _parent(central/raw) as (parent,name):
                    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
                    try:
                        info=os.fstat(fd)
                        valid=stat.S_ISREG(info.st_mode) and info.st_size==row['size_bytes']
                    finally:os.close(fd)
            except OSError:pass
        family[ident]=family.get(ident,True) and valid
    return {int(k) for k,v in family.items() if v}
