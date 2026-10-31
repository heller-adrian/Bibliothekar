"""Positive camera history for local General admission, never duplicate skipping.

The live catalogue may legitimately lose a row after confirmed external loss.
That does not erase immutable origins. These hashes only REFUSE implicit new
origin registration; they never authorize file ownership, deletion or recovery.
"""
from collections import defaultdict, deque
from contextlib import closing
from pathlib import Path
import sqlite3

from app.operation_health import read_connection
from app.private_storage_security import qualify_existing, RootOperationError


def known_camera_hashes(registry: Path) -> set[str]:
    from app.metadata_correction import MetadataCorrectionError
    try:
        qualify_existing(registry)
        with closing(read_connection(registry)) as connection:
            connection.execute('BEGIN')
            known={str(row[0]) for row in connection.execute('''
                SELECT DISTINCT media.sha256 FROM source_media media
                JOIN source_family_members member ON member.media_id=media.media_id
                JOIN source_families family ON family.source_family_key=member.source_family_key
            ''') if row[0]}
            databases={Path(row[0]).absolute() for row in connection.execute(
                'SELECT database_path FROM libraries WHERE COALESCE(is_registered,1)=1')}
        edges=defaultdict(list)
        for database in sorted(databases):
            qualify_existing(database)
            with closing(read_connection(database)) as connection:
                connection.execute('BEGIN')
                for original,current in connection.execute('SELECT sha256_original,sha256_current FROM files'):
                    known.update(str(value) for value in (original,current) if value)
                for source,output in connection.execute('''
                    SELECT source_sha256,output_sha256 FROM metadata_corrections
                    WHERE status='completed' AND COALESCE(output_sha256,'')<>''
                '''):
                    if source and output:edges[str(source)].append(str(output))
        # Follow all completed correction generations once, including work
        # copies corrected twice after their camera row was removed. No
        # filename search and no quadratic repeated full-history scans.
        pending=deque(known)
        while pending:
            for output in edges.get(pending.popleft(),()):
                if output not in known:
                    known.add(output);pending.append(output)
        return known
    except (OSError,ValueError,sqlite3.Error,RootOperationError) as error:
        raise MetadataCorrectionError(
            'Herkunftsnachweise konnten vor der Allgemein-Übernahme nicht vollständig geprüft werden: '+str(error)
        ) from error
