"""Original library swap, interrupted replay, and untouched conflicting evidence."""
from pathlib import Path
import json,os
import pytest
from tests.backend import test_0562_process_recovery as recovery
from tests.backend.test_0562_process_recovery import isolated_process_environment
from tests.backend.external_sql import external_edit


def operations(case):
    return {str(p):p.read_bytes() for p in case.rglob('operation-*.json')}


@pytest.mark.parametrize('boundary',['meta.recover_original','meta.recover_task','library.before-outcome','library.outcome'])
def test_library_original_rollback_survives_recovery_sigkill(tmp_path,boundary):
    evidence,case,data=recovery.new_case(tmp_path,'library_metadata','library-recovery-'+boundary)
    recovery.invoke(case,'operate','meta.backup',evidence/'kill',kill=True)
    original=operations(case);assert len(original)==1
    record=json.loads(next(iter(original.values())))
    for n in range(1 if boundary=='library.outcome' else 2):
        recovery.invoke(case,'startup',boundary,evidence/('replay-kill'+str(n)),kill=True)
    recovery.three_restarts(case,evidence)
    assert not operations(case) and not list(case.rglob('.swap-journals/*.json'))
    source=Path(data['source']);assert recovery.hash_file(source)==data['expected'][source.name]
    receipt,=case.rglob('library-metadata-outcome-'+record['reservation_id']+'.json')
    proof=json.loads(receipt.read_text());assert proof['reservation']==record
    (evidence/'f14-proof.json').write_text(json.dumps({'original':record,'verified_outcome':proof,'source_sha256':recovery.hash_file(source)},indent=2))
    assert proof['disposition']=='verified_original_library_swap_rolled_back'
    assert recovery.invoke(case,'retry','none',evidence/'retry')['returncode']==0


@pytest.mark.parametrize('fault',['foreign_source','foreign_backup','foreign_incoming','foreign_work','missing_backup','hardlink','task','generation','same_backup_new_inode','same_work_new_inode','missing_native_proof','database_inode','database_owner'])
def test_library_swap_unknown_evidence_keeps_original_fence(tmp_path,fault):
    evidence,case,data=recovery.new_case(tmp_path,'library_metadata','library-blocked-'+fault)
    recovery.invoke(case,'operate','meta.backup',evidence/'kill',kill=True)
    original=operations(case);assert len(original)==1
    journal,=case.rglob('.swap-journals/*.json');swap=json.loads(journal.read_text());item=swap['files'][0]
    (evidence/'f14-proof.json').write_text(json.dumps({'original_reservations':{p:json.loads(raw) for p,raw in original.items()},'fault':fault,'original_swap':swap},indent=2))
    if fault.startswith('foreign_'):
        role=fault.removeprefix('foreign_')
        if role=='work':
            target=journal.parent.parent/'.work'/data['task']/'unknown.JPG'
        else:target=Path(item[role if role!='source' else 'source'])
        target.write_bytes(b'foreign bytes must remain untouched')
    elif fault=='missing_backup':Path(item['backup']).rename(case/'retained-original-backup.JPG')
    elif fault=='hardlink':os.link(item['incoming'],case/'retained-hardlink.JPG')
    elif fault in {'same_backup_new_inode','same_work_new_inode'}:
        if fault=='same_backup_new_inode':target=Path(item['backup'])
        else:
            native,=case.rglob('metadata-swap-ownership-*.json')
            proof=json.loads(native.read_text())
            target=next(Path(p) for p in proof['owned_identities'] if '/.work/' in p)
        replacement=target.with_suffix('.foreign-copy');replacement.write_bytes(target.read_bytes());replacement.replace(target)
    elif fault=='missing_native_proof':
        native,=case.rglob('metadata-swap-ownership-*.json');native.rename(case/'retained-uncertified-ownership.json')
    elif fault=='database_inode':
        import sqlite3
        database=Path(data['db']);copy=database.with_suffix('.copy')
        from contextlib import closing
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(copy)) as destination:
            source.backup(destination)
        copy.replace(database)
    elif fault=='database_owner':
        with external_edit(Path(data['db']),fixture_root=case) as c:
            c.execute("UPDATE library_identity SET library_id='different-synthetic-owner'")
    elif fault=='task':
        with external_edit(Path(data['db']),fixture_root=case) as c:
            c.execute("UPDATE metadata_corrections SET proposed_datetime='2026-12-30T12:00:00'")
    else:
        state=Path(next(iter(original))).parent/'state.json'
        value=json.loads(state.read_text());value['generation']+=1;state.write_text(json.dumps(value))
    retained={str(p):p.read_bytes() for p in case.rglob('*') if p.is_file() and p.suffix.upper() in {'.JPG','.XMP'}}
    retained.update({str(Path(item[k])):Path(item[k]).read_bytes() for k in ('source','backup','incoming') if Path(item[k]).is_file()})
    for n in range(2):
        result=recovery.invoke(case,'startup','none',evidence/('restart'+str(n)))
        recovery.assert_preserved_write_fence(case,evidence/('probe'+str(n)),result,'metadata')
        assert operations(case)==original and journal.exists()
        assert all(Path(p).read_bytes()==raw for p,raw in retained.items())
