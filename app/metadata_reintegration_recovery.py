"""Qualify access to retry a verified RC14 reintegration; never finish its intent.

RC14 omitted family_id from the reservation key. Therefore no family is inferred
from that key and no operation is automatically replayed or acknowledged.
"""
from pathlib import Path
from datetime import datetime
from app.database import database_connection
from app.root_operations import _control_location, _read, _lock, _check, generation, RootOperationError
from app.storage_bootstrap import key_for
from app.library_registry import list_libraries
from app.storage_config import load_storage_settings, storage_paths
from app.managed_directory_names import is_undated_name


def _pending_reservations(workspace, registry):
    from app.metadata_correction import _reintegration_capture, verify_metadata_datetime, _sha256, _safe_relative
    from app.metadata_swap_recovery import assert_no_pending_swaps, metadata_write_guard
    workspace=Path(workspace).absolute()
    parent=_control_location(workspace)
    state=_read(parent/'state.json',{})
    owners={r['library_id']:r for r in list_libraries(registry)}
    accepted=set()
    for path in parent.glob('operation-*.json'):
        record=_read(path,{})
        if (record.get('kind')!='metadata' or record.get('ids')!={
                'function':'app.metadata_correction.reintegrate_library_metadata_family'}):
            continue
        with _lock(path.with_suffix('.lock'),exclusive=True):
            owner=owners.get(record.get('library'))
            if owner is None or owner['workspace_root']!=str(workspace):
                raise RootOperationError('metadata_retry_owner_changed: '+str(path))
            database=Path(owner['database_path']).absolute()
            bindings=record.get('bindings',{})
            nonce=str(record.get('reservation_id') or '')
            required={str(workspace),owner['work_root'],owner['archive_root'],
                      *(str(workspace/n) for n in load_storage_settings(workspace_root=workspace).values())}
            if (_read(path,{})!=record or path.name!='operation-'+key_for(record)+'.json'
                or record.get('format')!=1 or record.get('shared') is not False
                or record.get('database')!=str(database) or record.get('workspace')!=str(workspace)
                or record.get('generation')!=list(generation(workspace,owner['library_id']))
                or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce)
                or not required<=set(bindings)
                or any(i is None or state.get('bindings',{}).get(p)!=i for p,i in bindings.items())):
                raise RootOperationError('metadata_retry_reservation_changed: '+str(path))
            _check(bindings)
            metadata=storage_paths(workspace)['metadata_root']
            with metadata_write_guard(metadata):
                assert_no_pending_swaps(metadata)
                work=metadata/'.reintegrate'
                if work.exists() and (work.is_symlink() or any(work.iterdir())):
                    raise RootOperationError('metadata_retry_unrecovered_work: '+str(work))
                with database_connection(database) as c:
                    families=c.execute("SELECT * FROM file_families WHERE selected_capture_time IS NOT NULL").fetchall()
                    all_rows=[dict(r) for r in c.execute('SELECT *,id AS file_id FROM files')]
                central=storage_paths(workspace)['backup_root']
                qualified=0
                for family in families:
                    rows=[r for r in all_rows if r['family_id']==family['id'] and r['job_id']==family['job_id']]
                    if not rows or not any(_undated(r.get('current_relative_path')) for r in rows):
                        continue
                    # Every remaining corrected Undated family must be intact;
                    # an unknown family cannot be hidden by one successful proof.
                    if any(r['review_status']!='corrected' or r['metadata_write_status']!='written' for r in rows):
                        raise RootOperationError('metadata_retry_unqualified_family: '+str(family['id']))
                    stored=str(family['selected_capture_time'])
                    proposed=_reintegration_capture(database,family['id'],rows,stored,
                        job_id=family['job_id'],family_key=family['family_key'])
                    if datetime.fromisoformat(stored).tzinfo is not None or proposed==stored:
                        raise RootOperationError('metadata_retry_missing_legacy_receipt: '+str(family['id']))
                    for row in rows:
                        relative=_safe_relative(row['current_relative_path'])
                        source=central/relative
                        if (not is_undated_name(relative.parts[0]) or source.is_symlink()
                            or source.resolve()!=source.absolute() or row['selected_capture_time']!=stored
                            or not source.is_file() or source.stat().st_size!=row['size_bytes']
                            or _sha256(source)!=(row['sha256_current'] or row['sha256_original'])):
                            raise RootOperationError('metadata_retry_file_changed: '+str(source))
                        verify_metadata_datetime(source,proposed)
                    qualified+=1
                if not qualified:
                    raise RootOperationError('metadata_retry_no_qualified_family: '+str(path))
                _check(bindings)
                # Keep original nonce, bindings, generations and operation file.
                # The normal protected user retry must resume this exact intent.
                accepted.add(str(path))
    return accepted


def _undated(value):
    parts=Path(str(value or '')).parts
    return bool(parts) and is_undated_name(parts[0])


def pending_reservations(workspace, registry):
    from app.metadata_correction import MetadataCorrectionError
    from app.metadata_swap_recovery import MetadataSwapRecoveryError
    try:
        return _pending_reservations(workspace,registry)
    except (MetadataCorrectionError,MetadataSwapRecoveryError,ValueError,KeyError,TypeError,IndexError) as error:
        raise RootOperationError('metadata_retry_unverified: '+str(error)) from error
