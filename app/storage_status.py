"""Only structural READY/UNAVAILABLE; operation fences have a separate authority."""
from enum import StrEnum


class State(StrEnum):
    READY = 'READY'
    UNAVAILABLE = 'UNAVAILABLE'


def describe(observation):
    result = dict(observation)
    issues = result.get('issues',[])
    state = State.READY if result.get('ready') else State.UNAVAILABLE
    result['state'] = state.value
    # Setup progress is not a third storage state.
    result['setup_phase'] = ('initializing' if result.get('initialization_evidence') == 'resumable_empty_structure' else 'not_started') if result.get('can_initialize') else None
    result['operations_allowed'] = state == State.READY
    result['recovery'] = {
        'authenticated':True, 'automatic_reset':False,
        'recheck':True,
        'expected_folders':[{'path':r['path'],'identity':r.get('expected_identity'),'status':r['status']}
                            for r in result.get('folders',[]) if r['status'] != 'available'],
        'history_restore_required':any(i['code'] in {'installation_history_missing','registry_unavailable','catalog_unavailable','catalog_identity_mismatch','registry_history_mismatch','workspace_claim_conflict'} for i in issues),
    }
    return result
