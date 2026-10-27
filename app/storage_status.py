"""Five public storage states, independent of host ACL hardening policy.

Only FRESH/INITIALIZING permit technical setup. DEGRADED needs an original
binding or explicit role-specific loss confirmation. AMBIGUOUS never resets.
"""
from enum import StrEnum


class State(StrEnum):
    FRESH = 'FRESH'
    INITIALIZING = 'INITIALIZING'
    READY = 'READY'
    DEGRADED = 'DEGRADED'
    AMBIGUOUS = 'AMBIGUOUS'


def describe(observation):
    result = dict(observation)
    issues = result.get('issues',[])
    if result.get('can_initialize'):
        state = State.INITIALIZING if result.get('initialization_evidence') == 'resumable_empty_structure' else State.FRESH
    elif result.get('ready'):
        state = State.READY
    elif any(i['code'] in {'workspace_unknown_entry','workspace_scan_error','workspace_scan_changed',
                           'legacy_lock_not_migrated','legacy_lock_without_control_state',
                           'bootstrap_reservation_mismatch','bootstrap_additional_operation',
                           'workspace_claim_conflict','configuration_invalid','evidence_unreadable',
                           'legacy_layout_requires_explicit_migration'} for i in issues):
        state = State.AMBIGUOUS
    elif any(i['code'] in {'missing','identity_changed','workspace_identity_changed',
                          'workspace_unavailable','mount_identity_changed',
                          'installation_history_missing','registry_unavailable','catalog_unavailable','catalog_identity_mismatch','registry_history_mismatch',
                          'storage_read_only','private_path_unavailable','appdata_identity_changed'} for i in issues):
        state = State.DEGRADED
    else:
        state = State.AMBIGUOUS
    result['state'] = state.value
    result['operations_allowed'] = state == State.READY
    result['recovery'] = {
        'authenticated':True, 'automatic_reset':False,
        'recheck':True,
        'expected_folders':[{'path':r['path'],'identity':r.get('expected_identity'),'status':r['status']}
                            for r in result.get('folders',[]) if r['status'] != 'available'],
        'history_restore_required':any(i['code'] in {'installation_history_missing','registry_unavailable','catalog_unavailable','catalog_identity_mismatch','registry_history_mismatch','workspace_claim_conflict'} for i in issues),
    }
    return result
