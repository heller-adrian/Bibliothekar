"""Fingerprint-anchored failure completion in the existing SQLite job journal."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from app import trash_fd, trash_retention as retention
from app.database import database_connection, utc_now_iso
from app.storage_config import storage_paths
from app.trash import TrashError

KEY = 'failure_finalization'
VERSION = 'private-retention-v1'


def has_anchor(value):
    return (isinstance(value,str) and bool(re.fullmatch('[0-9a-f]{64}',value))
            and value!=hashlib.sha256(b'').hexdigest())


def _context(database, workspace):
    from app.trash_failure import scopes
    registry = Path(os.environ.get('KAMERA_REGISTRY_DATABASE', str(Path(os.environ.get('KAMERA_DATABASE_DIR', '/database'))/'bibliothekar-global.sqlite3'))).absolute()
    root, users = retention.authority(registry, workspace)
    paths = [registry]
    with ExitStack() as stack:
        stack.enter_context(retention.qualified(registry, users))
        databases = scopes(database, workspace)
        if any(p.parent != root for p in databases):
            raise TrashError('Registrierte Kataloge liegen außerhalb der privaten App-Ablage.')
        paths += databases
        for path in paths:
            stack.enter_context(retention.qualified(path, users))
            for suffix in ('-wal', '-shm', '-journal'):
                side = Path(str(path)+suffix)
                if side.exists() or side.is_symlink(): stack.enter_context(retention.qualified(side, users))
    return root, users, databases, paths


def recorded(database, workspace, job_id):
    """Lookup is not validation. The SQLite record alone never releases a file."""
    from app.trash_failure import scopes
    for path in scopes(database, workspace):
        with database_connection(path) as c:
            row = c.execute('SELECT result_json FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row:
                result = json.loads(row[0] or '{}')
                if not isinstance(result,dict): raise TrashError('Ungeklärtes Auftragsergebnis bleibt geschützt.')
                value = result.get(KEY)
                return value if isinstance(value, dict) and value.get('version') == VERSION else None
    return None


def _job(database, workspace, job_id, data, connections, *, rescue=False):
    from app.trash_failure import _jobs, digest
    from app.trash_import import stage_parent
    from app.trash_restore import _relative, restore_reservations
    stage = stage_parent(workspace)/job_id
    (owner, job), ids = _jobs(connections, job_id, stage)
    files = data.get('files'); paths = data.get('relative_paths')
    if (data.get('status') != 'known_restored' or data.get('cleanup_completed')
        or data.get('known_paths') != [] or not isinstance(files, list) or not files
        or not isinstance(paths, list) or len(paths) != len(set(paths))
        or len(files) != len(paths) or {_relative(r['relative_path']).as_posix() for r in files} != set(paths)):
        raise TrashError('Unvollständige Restorepartition; Reservierung bleibt bestehen.')
    if any(set(r['relative_paths']) & set(paths) for r in restore_reservations(workspace)):
        raise TrashError('Andere Restore-Recovery schützt diese Dateien.')
    fp = job['source_fingerprint']
    anchored = has_anchor(fp)
    if not anchored and not rescue:
        raise TrashError('Vertrauenswürdiger Quellenfingerprint fehlt; bestätigte Variantenrettung erforderlich.')
    if anchored and rescue:
        raise TrashError('Vorhandener Quellenfingerprint muss regulär geprüft werden; keine Umgehung durch Variantenrettung.')
    if not isinstance(json.loads(job['result_json'] or '{}'), dict): raise TrashError('Ungeklärtes Auftragsergebnis.')
    return owner, job, ids, stage, fp, digest({k:v for k,v in data.items() if k != KEY})


def _incoming(workspace, job_id):
    """Diagnostic attachment only. Never authorizes release; allow reported 0770."""
    incoming = storage_paths(workspace)['backup_root']/'.incoming'/job_id
    if not incoming.exists() and not incoming.is_symlink(): return None
    # Reuse all structural/status checks, without asserting exclusivity of this
    # deliberately shared tree. Private retention and DB fingerprint authorize.
    with trash_fd.parent(incoming/'.binding') as (root, _, check):
        names = os.listdir(root)
        if len(names) != 1 or names[0] not in {'Protocol', 'Protokoll'}:
            raise TrashError('Unbekannte Import-Zwischendaten bleiben geschützt.')
        with trash_fd.parent(incoming/names[0]/'status.json') as (fd, name, binding):
            if os.listdir(fd) != ['status.json']: raise TrashError('Unbekannte Protokollreste.')
            with trash_fd.file_at(fd, name) as (source, before):
                if before.st_nlink != 1 or before.st_size > 1024*1024: raise TrashError('Unklarer Protokollrest.')
                raw = os.read(source, 1024*1024+1); data = json.loads(raw)
                if not isinstance(data,dict) or not isinstance(data.get('lifecycle'),dict):
                    raise TrashError('Ungültiges Protokolldokument bleibt geschützt.')
                stage = storage_paths(workspace)['metadata_root']/'.trash-import'/job_id
                if (data.get('schema_version') != 3 or data.get('job_id') != job_id
                    or data.get('state') != 'failed' or data.get('stage') != 'failed'
                    or data.get('simulation') is not False or data.get('import_mode') != 'folder'
                    or data.get('source_path') != str(stage)
                    or data.get('lifecycle', {}).get('temporary_backup') != str(incoming/'Original')
                    or data.get('lifecycle', {}).get('central_stock') != str(incoming.parent.parent)
                    or any(k in data for k in ('organization', 'source', 'snapshot', 'outputs'))):
                    raise TrashError('Protokoll widerspricht dem fehlgeschlagenen Auftrag.')
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != tuple(getattr(os.fstat(source), k) for k in ('st_size','st_mtime_ns','st_ctime_ns')):
                    raise TrashError('Protokoll während der Prüfung verändert.')
                trash_fd.verify_entry(fd, name, before); binding(); check()
                if os.listdir(root) != names or os.listdir(fd) != ['status.json']:
                    raise TrashError('Import-Zwischenbestand während der Prüfung verändert.')
                return {'sha256': hashlib.sha256(raw).hexdigest(), 'raw': raw.decode('utf-8'),
                        'identity': list(trash_fd.identity(before))}


def validate(database, workspace, job_id, data):
    from app.trash_failure import digest, _jobs
    root, users, databases, paths = _context(database, workspace)
    receipt = recorded(database, workspace, job_id)
    if not receipt or receipt.get('phase') != 'committed' or receipt.get('proof_digest') != digest(receipt.get('proof')):
        raise TrashError('Privater Abschlussbeleg fehlt oder widerspricht sich.')
    if not re.fullmatch('[0-9a-f]{32}',str(receipt.get('receipt_id',''))):
        raise TrashError('Ungültige private Belegidentität.')
    proof = receipt['proof']
    if (proof['job_id'] != job_id or proof['trust'] != {'users':sorted(users),'admin_groups':sorted(retention.ADMIN_GROUPS)}
        or proof['workspace'] != str(Path(workspace).absolute()) or proof['journal_digest'] != digest({k:v for k,v in data.items() if k != KEY})
        or proof['paths'] != data['relative_paths']): raise TrashError('Restorejournal seit Abschluss verändert.')
    with ExitStack() as stack:
        bindings = [stack.enter_context(retention.qualified(p, users))[1] for p in paths]
        connections = [(p, stack.enter_context(database_connection(p))) for p in databases]
        (owner, job), ids = _jobs(connections, job_id, Path(proof['source_path']))
        if (str(owner) != proof['owner'] or ids != proof['databases'] or job['source_fingerprint'] != proof['source_fingerprint']
            or job['error_message'] != proof['job_error'] or job['stage'] != proof['job_stage']):
            raise TrashError('Privater Auftragsnachweis verändert.')
        c = next(c for p,c in connections if p==owner)
        audits = list(c.execute("SELECT details_json FROM audit_log WHERE job_id=? AND action='trash_restore_failed_finalized' AND entity_id=?",(job_id,receipt['receipt_id'])))
        expected_audit = {'proof_digest':receipt['proof_digest'],'retained_copies':proof['retention_path']}
        if len(audits)!=1 or json.loads(audits[0][0])!=expected_audit:
            raise TrashError('Transaktionaler Abschlussbeleg und Audit widersprechen sich.')
        location = root/'.bibliothekar-restore-retention'/receipt['receipt_id']
        with retention.qualified(location, users, directory=True) as (fd, check):
            if list(trash_fd.identity(os.fstat(fd))) != proof['retention_identity']: raise TrashError('Retentionsordner ersetzt.')
            for item in proof['files']:
                with retention.qualified(location/'media'/item['relative_path'], users) as (copy, bound):
                    info = os.fstat(copy)
                    if (list(trash_fd.identity(info)) != item['retention_identity'] or info.st_size != item['size_bytes']
                        or retention.hash_fd(copy) != item['sha256']): raise TrashError('Private Rückfallkopie verändert oder fehlt.')
                    bound()
            with retention.qualified(location/'evidence.json', users) as (evidence, bound):
                if retention.hash_fd(evidence) != proof['evidence_sha256']: raise TrashError('Private Diagnosebelege verändert.')
                bound()
            check()
        for binding in bindings: binding()
    return receipt


def _variants(stage, trash, paths):
    """Explicit rescue preserves current variants; it authenticates no history."""
    try: staged = retention.manifest(stage)
    except FileNotFoundError: staged = []
    files = [{**r, 'source_relative_path':r['relative_path'], 'origin':'staging',
              'relative_path':'staging/'+r['relative_path']} for r in staged]
    available = {r['relative_path'] for r in staged}
    for rel in paths:
        try:
            with trash_fd.parent(trash/rel) as (fd, name, check):
                with trash_fd.file_at(fd, name) as (source, info):
                    sha = retention.hash_fd(source); after = os.fstat(source)
                    if (info.st_size,info.st_mtime_ns,info.st_ctime_ns) != (after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                        raise TrashError('Original während Variantenrettung verändert.')
                    trash_fd.verify_entry(fd,name,info);check()
                    files.append({'relative_path':'trash/'+rel, 'source_relative_path':rel, 'origin':'trash',
                                  'sha256':sha, 'size_bytes':info.st_size, 'identity':list(trash_fd.identity(info))})
                    available.add(rel)
        except FileNotFoundError: pass
    if not set(paths).issubset(available): raise TrashError('Mindestens eine Aufnahme hat keine erhaltene Variante; Reservierung bleibt bestehen.')
    return files


def finalize(database, workspace, job_id, *, rescue=False):
    """Called inside F14/F11 locks; source is never removed or rewritten."""
    from app.trash_failure import read_journal, digest, checkpoint, _jobs
    from app.folder_import import manifest_fingerprint
    data = read_journal(workspace, job_id)
    prior = recorded(database, workspace, job_id)
    if prior:
        receipt = validate(database, workspace, job_id, data)
        return {'job_id':job_id, 'status':'finalized', 'recovery_path':receipt['proof']['retention_path']}
    root, users, databases, paths = _context(database, workspace)
    with ExitStack() as stack:
        bindings = [stack.enter_context(retention.qualified(p, users))[1] for p in paths]
        connections = []
        for path in databases:
            c = stack.enter_context(database_connection(path)); c.execute('BEGIN IMMEDIATE'); connections.append((path,c))
        owner, job, ids, stage, fp, journal_digest = _job(database, workspace, job_id, data, connections, rescue=rescue)
        trash = storage_paths(workspace)['trash_root']
        manifest = _variants(stage,trash,data['relative_paths']) if rescue else retention.manifest(stage)
        if not rescue and (manifest_fingerprint(manifest) != fp or manifest_fingerprint(data['files']) != fp):
            raise TrashError('Quellenfingerprint stimmt nicht mit vollständigem Restorebestand überein.')
        incoming = _incoming(workspace, job_id)
        for item in ([] if rescue else manifest):
            with trash_fd.parent(trash/item['relative_path']) as (fd,name,check):
                with trash_fd.file_at(fd,name,item['sha256']) as (_, info):
                    if info.st_size != item['size_bytes'] or list(trash_fd.identity(info)) == item['identity']:
                        raise TrashError('Papierkorboriginal fehlt oder ist nicht unabhängig.')
                    check()
        checkpoint('private_verified')
        base = root/'.bibliothekar-restore-retention'; retention.ensure_directory(base, users)
        receipt_id = uuid.uuid4().hex; location = base/receipt_id
        retention.ensure_directory(location, users)
        with retention.qualified(location, users, directory=True) as (fd, check):
            capacity = os.fstatvfs(fd)
            if capacity.f_bavail*capacity.f_frsize < sum(r['size_bytes'] for r in manifest) + 64*1024*1024:
                raise TrashError('Nicht genügend privater Retentionsspeicher einschließlich SQLite-Reserve.')
            location_id = list(trash_fd.identity(os.fstat(fd))); check()
        media = location/'media'; retention.ensure_directory(media, users)
        copies = []
        for item in manifest:
            target = media/item['relative_path']
            relative = Path(item['relative_path']).parent
            parent = media
            for name in relative.parts:
                parent /= name; retention.ensure_directory(parent, users)
            source = (trash if item.get('origin') == 'trash' else stage)/item.get('source_relative_path',item['relative_path'])
            copies.append(retention.retain(source, target, item, users, checkpoint))
        evidence = {'job_id':job_id, 'journal':data, 'incoming_protocol':incoming}
        trash_fd.atomic_json(location/'evidence.json', evidence)
        with retention.qualified(location/'evidence.json', users) as (fd, check): evidence_hash = retention.hash_fd(fd); check()
        # Re-enumerate every source and original, not just the names from a
        # mutable workspace journal. Persist only after copied bytes are durable.
        current = _variants(stage,trash,data['relative_paths']) if rescue else retention.manifest(stage)
        if current != manifest or read_journal(workspace,job_id) != data or _incoming(workspace,job_id) != incoming:
            raise TrashError('Gemeinsamer Restorebestand während Retention verändert.')
        for item in ([] if rescue else manifest):
            with trash_fd.parent(trash/item['relative_path']) as (fd,name,check):
                with trash_fd.file_at(fd,name,item['sha256']) as (_, info):
                    if info.st_size != item['size_bytes']: raise TrashError('Originalgröße verändert.')
                    check()
        (now_owner, now_job), now_ids = _jobs(connections, job_id, stage)
        if (now_owner != owner or now_ids != ids or now_job != job): raise TrashError('Auftragszustand während Retention verändert.')
        proof = {'job_id':job_id,'trust':{'users':sorted(users),'admin_groups':sorted(retention.ADMIN_GROUPS)},'mode':'confirmed-current-variants' if rescue else 'historical-fingerprint', 'workspace':str(Path(workspace).absolute()), 'owner':str(owner), 'databases':ids,
                 'source_path':str(stage), 'source_fingerprint':fp, 'journal_digest':journal_digest,
                 'job_error':job['error_message'], 'job_stage':job['stage'], 'paths':data['relative_paths'],
                 'retention_path':str(location), 'retention_identity':location_id,
                 'files':copies, 'evidence_sha256':evidence_hash}
        receipt = {'version':VERSION, 'phase':'committed', 'receipt_id':receipt_id,
                   'created_at':utc_now_iso(), 'proof':proof, 'proof_digest':digest(proof)}
        for binding in bindings: binding()
        # Check new WAL/SHM permissions, too; connections may have created them.
        _context(database, workspace)
        c = next(c for p,c in connections if p == owner)
        result = json.loads(job['result_json'] or '{}'); result[KEY] = receipt
        c.execute('UPDATE jobs SET result_json=? WHERE id=? AND state=\'failed\'', (json.dumps(result,ensure_ascii=False),job_id))
        c.execute("INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'trash_restore_failed_finalized','restore_failure',?,?,?)",
                  (job_id,receipt_id,json.dumps({'proof_digest':receipt['proof_digest'],'retained_copies':str(location)}),receipt['created_at']))
        checkpoint('private_before_db_commit')
    checkpoint('private_db_committed')
    validate(database, workspace, job_id, data)
    return {'job_id':job_id, 'status':'finalized', 'recovery_path':str(location)}
