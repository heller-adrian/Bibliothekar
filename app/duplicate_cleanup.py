from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sqlite3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def manifest_fingerprint(rows: list[sqlite3.Row]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: str(item['original_relative_path'])):
        digest.update(str(row['original_relative_path']).encode('utf-8'))
        digest.update(b'\0')
        digest.update(str(int(row['size_bytes'])).encode('ascii'))
        digest.update(b'\0')
        digest.update(str(row['sha256_original']).encode('ascii'))
        digest.update(b'\n')
    return digest.hexdigest()


def quick_source_signature(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode('utf-8', 'surrogateescape'))
        digest.update(b'\0')
        digest.update(str(stat.st_size).encode('ascii'))
        digest.update(b'\0')
        digest.update(str(stat.st_mtime_ns).encode('ascii'))
        digest.update(b'\n')
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--logs', required=True)
    parser.add_argument('--keep-job', required=True)
    parser.add_argument('--delete-job', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    database = Path(args.database)
    workspace = Path(args.workspace) / 'Arbeitsbereich'
    logs = Path(args.logs)
    backup = database.with_name(database.name + '.before-duplicate-cleanup')

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        keep = connection.execute('SELECT * FROM jobs WHERE id = ?', (args.keep_job,)).fetchone()
        delete = connection.execute('SELECT * FROM jobs WHERE id = ?', (args.delete_job,)).fetchone()
        if keep is None or delete is None:
            raise SystemExit('ABBRUCH: Einer der beiden Aufträge fehlt.')
        for row in (keep, delete):
            if row['operation'] != 'folder_import' or row['state'] != 'completed':
                raise SystemExit('ABBRUCH: Beide Aufträge müssen abgeschlossene Ordnerimporte sein.')
        dependencies = connection.execute(
            'SELECT COUNT(*) FROM events WHERE job_id = ?', (args.delete_job,)
        ).fetchone()[0]
        if dependencies:
            raise SystemExit('ABBRUCH: Der zu löschende Import besitzt Ereignisse.')
        sort_dependencies = connection.execute(
            'SELECT COUNT(*) FROM sort_runs WHERE job_id = ?', (args.delete_job,)
        ).fetchone()[0]
        if sort_dependencies:
            raise SystemExit('ABBRUCH: Der zu löschende Import besitzt Sortierläufe.')

        keep_rows = connection.execute(
            'SELECT * FROM files WHERE job_id = ? ORDER BY original_relative_path', (args.keep_job,)
        ).fetchall()
        delete_rows = connection.execute(
            'SELECT * FROM files WHERE job_id = ? ORDER BY original_relative_path', (args.delete_job,)
        ).fetchall()
        if not keep_rows or len(keep_rows) != len(delete_rows):
            raise SystemExit('ABBRUCH: Dateizahlen der beiden Importe stimmen nicht überein.')
        keep_by_original = {row['original_relative_path']: row for row in keep_rows}
        checked: list[Path] = []
        for row in delete_rows:
            partner = keep_by_original.get(row['original_relative_path'])
            if partner is None:
                raise SystemExit('ABBRUCH: Keine Partnerdatei für ' + row['original_relative_path'])
            if int(partner['size_bytes']) != int(row['size_bytes']) or partner['sha256_original'] != row['sha256_original']:
                raise SystemExit('ABBRUCH: Inhalt unterscheidet sich bei ' + row['original_relative_path'])
            relative = Path(str(row['current_relative_path']))
            path = workspace / relative
            if not path.is_file():
                raise SystemExit('ABBRUCH: Datei fehlt: ' + str(path))
            if path.stat().st_size != int(row['size_bytes']) or sha256_file(path) != row['sha256_original']:
                raise SystemExit('ABBRUCH: SSD-Datei weicht ab: ' + str(path))
            checked.append(path)

        manifest_path = logs / 'backups' / args.keep_job / 'manifest.json'
        if manifest_path.is_file():
            manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest_entries = list(manifest_data.get('files') or [])
            if not manifest_entries:
                raise SystemExit('ABBRUCH: Manifest des zu behaltenden Imports ist leer.')
            digest = hashlib.sha256()
            for entry in sorted(manifest_entries, key=lambda item: str(item['relative_path'])):
                digest.update(str(entry['relative_path']).encode('utf-8', 'surrogateescape'))
                digest.update(b'\0')
                digest.update(str(int(entry['size_bytes'])).encode('ascii'))
                digest.update(b'\0')
                digest.update(str(entry['sha256']).encode('ascii'))
                digest.update(b'\n')
            fingerprint = digest.hexdigest()
        else:
            fingerprint = manifest_fingerprint(keep_rows)
        source_path = Path(str(keep['source_path']))
        signature = quick_source_signature(source_path) if source_path.is_dir() else None

        print('Bereinigung geprüft: PASS')
        print('Behalten:', args.keep_job)
        print('Entfernen:', args.delete_job)
        print('Dateien:', len(checked))
        print('Fingerabdruck:', fingerprint)
        if not args.apply:
            print('DRY-RUN: Es wurde nichts verändert.')
            return

        shutil.copy2(database, backup)
        for path in checked:
            path.unlink()
        for directory in sorted({path.parent for path in checked}, key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass

        connection.execute('BEGIN IMMEDIATE')
        connection.execute(
            'UPDATE jobs SET source_signature = ?, source_fingerprint = ?, duplicate_of_job_id = NULL WHERE id = ?',
            (signature, fingerprint, args.keep_job),
        )
        connection.execute('DELETE FROM jobs WHERE id = ?', (args.delete_job,))
        connection.commit()

        protocol = logs / 'backups' / args.delete_job
        if protocol.exists():
            shutil.rmtree(protocol)
        print('Bereinigung angewendet: PASS')
        print('Datenbankbackup:', backup)
    finally:
        connection.close()


if __name__ == '__main__':
    main()
