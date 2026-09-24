"""0.25 product invariants. Every database and file is isolated by tmp_path."""
import json
from pathlib import Path
import pytest
from app.database import database_connection, create_planned_event, update_event_definition, get_event_edit_context, assign_free_families_to_existing_no_event
from app.event_structure import build_event_preview, EventPreviewError
from app.planning import list_job_available_families, list_job_planning_overview
from app.event_timeline import continuous_event_overlaps, list_event_segments, apply_cascade_for_interval
from app.event_reassignment import list_event_reassignments, reconcile_stale_event_reassignments
from app.obsolete_structure import cleanup_obsolete_structure
from tests.backend.test_0165_timeline import seed_job, add_family


def setup(db, timestamps):
    seed_job(db)
    for i, ts in enumerate(timestamps):
        add_family(db,str(i),ts)


def payload(start='2026-07-23T13:00',end='2026-07-23T15:00',**extra):
    return dict(event_kind='event',event_name='Urlaub',start_date=start[:10],end_date=end[:10],start_time=start[11:16],end_time=end[11:16],uses_time_range=True,**extra)


def create(db,p):
    return create_planned_event(db,'j',build_event_preview(p,list_job_available_families(db,'j')))


@pytest.mark.parametrize('preserve',[False,True])
@pytest.mark.parametrize('multi',[False,True])
def test_parent_owns_exact_range_without_child(tmp_path,preserve,multi):
    db=tmp_path/'db'; timestamps=['2026-07-23T14:00:00'] if not multi else ['2026-07-24T23:30:00','2026-07-25T12:00:00','2026-07-26T14:00:00']
    setup(db,timestamps)
    p=payload('2026-07-24T23:00','2026-07-26T15:00',preserve_day_folders=preserve) if multi else payload(preserve_day_folders=preserve)
    result=create(db,p); event=result['parent_event']
    assert result['child_event'] is None
    assert event['start_datetime']==p['start_date']+'T'+p['start_time']+':00'
    assert event['end_datetime']==p['end_date']+'T'+p['end_time']+':59'
    with database_connection(db) as c:
        assert not c.execute('SELECT 1 FROM events WHERE parent_event_id=?',(event['id'],)).fetchone()
        intervals=continuous_event_overlaps(c,'j',timestamps[0],timestamps[-1])
        assert len(intervals)==1
        assert intervals[0]['effective_start']==event['start_datetime']


def split_day(db):
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload())['parent_event']
    cards=list_job_planning_overview(db,'j')['available_day_groups']
    return event,cards


def test_exact_cards_and_no_event_reload(tmp_path):
    db=tmp_path/'db';event,cards=split_day(db)
    assert [(c['start_time'],c['end_time']) for c in cards]==[('00:00','12:59'),('15:01','23:59')]
    assert len({c['card_key'] for c in cards})==2
    assert [c['family_count'] for c in cards]==[1,1]
    assert all(len(c['families'])==1 for c in cards)
    result=create(db,{'event_kind':'no_event','no_event_segments':cards})
    segments=list_event_segments(db,result['parent_event']['id'])
    assert [(s['start_datetime'],s['end_datetime']) for s in segments]==[(c['start_datetime'],c['end_datetime']) for c in cards]
    assert list_job_planning_overview(db,'j')['available_day_groups']==[]


def test_disjoint_normal_selection_rejected(tmp_path):
    db=tmp_path/'db';event,cards=split_day(db)
    with pytest.raises(EventPreviewError,match='durchgehend'):
        create(db,payload('2026-07-23T00:00','2026-07-23T23:59',selected_intervals=cards))


def test_extension_updates_parent_no_child(tmp_path):
    db=tmp_path/'db';event,cards=split_day(db)
    for card in reversed(cards):
        create(db,payload(card['start_datetime'],card['end_datetime'],existing_parent_event_id=event['id'],selected_intervals=[card]))
    context=get_event_edit_context(db,'j',event['id'])
    assert context['event']['start_datetime']=='2026-07-23T00:00:00'
    assert context['event']['end_datetime']=='2026-07-23T23:59:59'
    assert context['child_events']==[]
    assert len(context['assigned_family_ids'])==3


def test_nonadjacent_extension_rejected(tmp_path):
    db=tmp_path/'db';setup(db,['2026-07-23T14:00:00','2026-07-24T12:00:00'])
    event=create(db,payload())['parent_event']
    with pytest.raises(ValueError,match='unmittelbar'):
        create(db,payload('2026-07-24T00:00','2026-07-24T23:59',existing_parent_event_id=event['id']))


@pytest.mark.parametrize('cascade',[False,True])
def test_edit_conflict_never_mutates_other_event(tmp_path,cascade):
    db=tmp_path/'db';event,cards=split_day(db)
    other=create(db,payload('2026-07-23T15:01','2026-07-23T23:59'))['parent_event']
    with database_connection(db) as c:
        before=[tuple(r) for r in c.execute('SELECT * FROM events ORDER BY id')]
    families=get_event_edit_context(db,'j',event['id'])['families']
    preview=build_event_preview(payload('2026-07-23T13:00','2026-07-23T23:59'),families)
    with pytest.raises(ValueError):
        update_event_definition(db,'j',event['id'],preview,event_name='Urlaub',notes='',expected_revision=1,cascade_confirmed=cascade)
    with database_connection(db) as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM events ORDER BY id')]==before


@pytest.mark.parametrize('status',['planned','applied'])
def test_released_intervals_persist_and_manual_assignment_resolves(tmp_path,status):
    db=tmp_path/'db';setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    if status=='applied':
        with database_connection(db) as c:c.execute("UPDATE events SET status='applied',applied_at='2026-09-22' WHERE id=?",(event['id'],))
    preview=build_event_preview(payload(),get_event_edit_context(db,'j',event['id'])['families'])
    result=update_event_definition(db,'j',event['id'],preview,event_name='Urlaub',notes='',expected_revision=1)
    assert len(result['removed_family_ids'])==2
    for _ in range(2):
        cards=list_job_planning_overview(db,'j')['available_day_groups']
        assert len(cards)==2 and all(c['reassignment_pending'] for c in cards)
        task=list_event_reassignments(db,'j',event['id'])
        assert [(s['start_time'],s['end_time']) for s in task['reassignment_segments']]==[('00:00','12:59'),('15:01','23:59')]
    target=create(db,{'event_kind':'no_event','no_event_segments':cards})['parent_event']
    with database_connection(db) as c:
        reconcile_stale_event_reassignments(c,'j',event['id'])
        rows=c.execute('SELECT * FROM event_reapply_removed_families WHERE event_id=?',(event['id'],)).fetchall()
        assert len(rows)==(2 if status=='applied' else 0)
        if rows: assert all(r['target_event_id']==target['id'] for r in rows)


@pytest.mark.parametrize('foreign',['none','file','empty_directory','foreign_document'])
def test_cleanup_only_known_obsolete_empty_structure(tmp_path,foreign):
    old=tmp_path/'2026'/'old';dest=tmp_path/'2026'/'new'/'Alle'/'a.jpg';dest.parent.mkdir(parents=True);dest.write_text('photo')
    for name in ['Alle','Sortiert','Export']:(old/name).mkdir(parents=True)
    (old/'event.json').write_text(json.dumps({'source':'other' if foreign=='foreign_document' else 'kamera-automatisierung','event':{'id':'e'}}))
    if foreign=='file':(old/'Sortiert'/'unknown.txt').write_text('keep')
    if foreign=='empty_directory':(old/'unknown').mkdir()
    cleanup_obsolete_structure(tmp_path,[old/'Alle'/'a.jpg'],[dest],{'e'})
    assert dest.read_text()=='photo'
    assert old.exists()==(foreign!='none')
    if foreign!='none':assert (old/'event.json').exists()


def test_legacy_disjoint_remains_free_and_blocked(tmp_path):
    db=tmp_path/'db';setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    with database_connection(db) as c:
        c.execute('UPDATE events SET time_model_version=1 WHERE id=?',(event['id'],))
        for i,(a,b) in enumerate([('09:00','11:00'),('17:00','19:00')]):
            c.execute("INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at) VALUES (?,'j',?,'child','old',?,?,1,'old','planned','now','now')",(str(i),event['id'],'2026-07-23T'+a+':00','2026-07-23T'+b+':59'))
        assert not continuous_event_overlaps(c,'j','2026-07-23T14:00:00','2026-07-23T14:00:59')
    ctx=get_event_edit_context(db,'j',event['id']);assert ctx['legacy_disjoint']
    preview=build_event_preview(payload(),ctx['families'])
    with pytest.raises(ValueError,match='manuell'):
        update_event_definition(db,'j',event['id'],preview,event_name='Test',notes='',expected_revision=1)


def attach_files(db,workspace,event_id):
    from tests.backend.test_0168_deep_workflows import add_file
    with database_connection(db) as c:
        event=dict(c.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone())
        families=c.execute('SELECT id,selected_capture_time FROM file_families').fetchall()
        (workspace/'imports'/'j').mkdir(parents=True,exist_ok=True)
        c.execute("UPDATE jobs SET stage='event_sort_applied',operation='folder_import',working_path=? WHERE id='j'",(str(workspace/'imports'/'j'),))
    for f in families:
        rel=f"{str(event['start_datetime'])[:4]}/{event['folder_name']}/Alle/{f['id']}.JPG"
        content,digest=add_file(db,int(f['id']),rel,payload=str(f['id']).encode())
        path=workspace/'Arbeitsbereich'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    with database_connection(db) as c:
        c.execute("UPDATE files SET current_root_kind='shared_workspace'")
        c.execute("UPDATE events SET status='applied',applied_at='2026-09-22' WHERE id=?",(event_id,))


@pytest.mark.parametrize('rename',[False,True])
def test_manual_workspace_assignment_then_confirmed_reconcile(tmp_path,rename):
    from app.workspace_reconcile import build_workspace_reconcile_plan,prepare_workspace_reconcile_run,execute_workspace_reconcile_run
    from app.sort_apply import CONFIRMATION_PHRASE, SortApplyError
    from app.event_document import build_event_document_from_db,write_event_document
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    attach_files(db,workspace,event['id'])
    document_path=write_event_document(workspace,build_event_document_from_db(db,workspace,'j',event['id']))
    original_document=document_path.read_bytes()
    root=workspace/'Arbeitsbereich'
    with database_connection(db) as c:
        before_paths={int(r['id']):str(r['current_relative_path']) for r in c.execute("SELECT id,current_relative_path FROM files WHERE job_id='j' ORDER BY id")}
    before_bytes={fid:(root/rel).read_bytes() for fid,rel in before_paths.items()}
    new_name='Neuer Urlaub' if rename else 'Urlaub'
    edited_payload=payload();edited_payload['event_name']=new_name
    preview=build_event_preview(edited_payload,get_event_edit_context(db,'j',event['id'])['families'])
    edited=update_event_definition(db,'j',event['id'],preview,event_name=new_name,notes='',expected_revision=1,workspace_path=workspace)
    assert edited['neutralized_file_count']==0
    assert edited['neutralized_files']==[]
    with database_connection(db) as c:
        after_edit_paths={int(r['id']):str(r['current_relative_path']) for r in c.execute("SELECT id,current_relative_path FROM files WHERE job_id='j' ORDER BY id")}
    assert after_edit_paths==before_paths
    assert all((root/rel).read_bytes()==before_bytes[fid] for fid,rel in before_paths.items())
    assert not (root/'Nicht zugeordnet').exists()
    assert document_path.read_bytes()==original_document
    new_document_path=root/'2026'/edited['event']['folder_name']/'event.json'
    if rename:
        assert not new_document_path.exists()
    plan=build_workspace_reconcile_plan(db,'j',event['id'],workspace)
    assert plan['summary']['ready'],plan['blockers']
    from app.event_reassignment import assign_event_reassignments,EventReassignmentError
    with pytest.raises(EventReassignmentError,match='Nachsortierung des Quellereignisses'):
        assign_event_reassignments(
            db,'j',event['id'],edited['removed_family_ids'],target_mode='new_no_event'
        )
    assert sorted(
        f['destination_relative_path'] for f in plan['files']
        if f['family_id'] in edited['removed_family_ids']
    ) == [
        '2026/2026-07-23 · 00-00–12-59/1.JPG',
        '2026/2026-07-23 · 15-01–23-59/3.JPG',
    ]
    with pytest.raises(SortApplyError,match='Bestätigung'):
        prepare_workspace_reconcile_run(db,'j',event['id'],workspace,expected_plan_token=plan['plan_token'],confirmation_phrase='')
    run=prepare_workspace_reconcile_run(db,'j',event['id'],workspace,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
    execute_workspace_reconcile_run(db,run['id'],workspace)
    assert new_document_path.exists()
    if rename:
        assert not document_path.exists()
    else:
        assert document_path.read_bytes()!=original_document
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM event_reapply_removed_families WHERE target_event_id IS NULL').fetchone()[0]==2
    assert len(list((root/'2026'/'2026-07-23 · 00-00–12-59').glob('*.JPG')))==1
    assert len(list((root/'2026'/'2026-07-23 · 15-01–23-59').glob('*.JPG')))==1
    cards=list_job_planning_overview(db,'j')['available_day_groups']
    target=create(db,{'event_kind':'no_event','no_event_segments':cards})['parent_event']
    # Merely creating the next plan still leaves its files in free stock.
    assert len(list((root/'2026'/'2026-07-23 · 00-00–12-59').glob('*.JPG')))==1
    assert len(list((root/'2026'/'2026-07-23 · 15-01–23-59').glob('*.JPG')))==1
    assert list_event_reassignments(db,'j',event['id'])['reassignment_segments']==[]
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM event_reapply_removed_families WHERE target_event_id=?',(target['id'],)).fetchone()[0]==2
        assert c.execute('SELECT status FROM events WHERE id=?',(target['id'],)).fetchone()[0]=='planned'


@pytest.mark.parametrize('preserve',[False,True])
def test_0260_applied_delete_releases_files_and_keeps_open_task(tmp_path,preserve):
    from app.database import delete_planned_event
    from app.workspace_reconcile import build_workspace_reconcile_plan,prepare_workspace_reconcile_run,execute_workspace_reconcile_run
    from app.sort_apply import CONFIRMATION_PHRASE
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    attach_files(db,workspace,event['id'])
    delete_planned_event(db,'j',event['id'])
    plan=build_workspace_reconcile_plan(db,'j',event['id'],workspace)
    assert plan['summary']['ready'],plan['blockers']
    run=prepare_workspace_reconcile_run(
        db,'j',event['id'],workspace,
        expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db,run['id'],workspace)
    with database_connection(db) as c:
        row=c.execute('SELECT pending_delete,resort_required FROM events WHERE id=?',(event['id'],)).fetchone()
        assert tuple(row)==(1,0)
        assert c.execute(
            'SELECT COUNT(*) FROM event_reapply_removed_families '
            'WHERE event_id=? AND target_event_id IS NULL',(event['id'],),
        ).fetchone()[0]==1
    assert len(list_event_reassignments(db,'j',event['id'])['families'])==1
    assert (workspace/'Arbeitsbereich'/'2026'/'2026-07-23'/'1.JPG').read_bytes()==b'1'
    from app.event_reassignment import assign_event_reassignments
    from app.sort_plan import build_event_sort_plan
    from app.sort_apply import prepare_sort_run,execute_sort_run
    state=list_event_reassignments(db,'j',event['id'])
    reassigned=assign_event_reassignments(
        db,'j',event['id'],[item['family_id'] for item in state['families']],target_mode='new_event',
        new_event_name='Neues Ereignis',segments=state['reassignment_segments'],
        preserve_day_folders=preserve,
    )
    target_id=reassigned['target']['event_id']
    assert reassigned['target']['preserve_day_folders'] is preserve
    with database_connection(db) as c:
        assert c.execute('SELECT pending_delete FROM events WHERE id=?',(event['id'],)).fetchone()[0]==1
    target_plan=build_event_sort_plan(db,'j',target_id,workspace)
    assert target_plan['summary']['ready'],target_plan['blockers']
    target_run=prepare_sort_run(
        db,'j',target_id,workspace,
        expected_plan_token=target_plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(db,target_run['id'],workspace)
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM events WHERE id=?',(event['id'],)).fetchone()[0]==0
        assert c.execute('SELECT status FROM events WHERE id=?',(target_id,)).fetchone()[0]=='applied'
        assert c.execute(
            'SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id=?',(event['id'],),
        ).fetchone()[0]==0
        assert c.execute(
            "SELECT status FROM event_mutations WHERE anchor_event_id=? ORDER BY created_at DESC LIMIT 1",
            (event['id'],),
        ).fetchone()[0]=='completed'
        assert c.execute(
            "SELECT COUNT(*) FROM audit_log WHERE entity_id=? AND action='event_deleted_after_target_apply'",
            (event['id'],),
        ).fetchone()[0]==1
    assert any(
        (workspace/'Arbeitsbereich'/item['destination_relative_path']).read_bytes()==b'1'
        for item in target_plan['files'] if item['status'] in {'move','already_sorted'}
    )
    with database_connection(db) as c:
        target_path=c.execute('SELECT current_relative_path FROM files WHERE family_id=?',(state['families'][0]['family_id'],)).fetchone()[0]
        assert bool(c.execute('SELECT preserve_day_folders FROM events WHERE id=?',(target_id,)).fetchone()[0]) is preserve
    assert ('/2026-07-23/Alle/' in target_path) is preserve


@pytest.mark.parametrize('preserve',[False,True])
def test_0260_workspace_free_card_new_event_finishes_reassignment(tmp_path,preserve):
    from app.database import delete_planned_event,list_global_tasks
    from app.workspace_reconcile import build_workspace_reconcile_plan,prepare_workspace_reconcile_run,execute_workspace_reconcile_run
    from app.sort_plan import build_event_sort_plan
    from app.sort_apply import CONFIRMATION_PHRASE,prepare_sort_run,execute_sort_run
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00'])
    source=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    attach_files(db,workspace,source['id'])
    delete_planned_event(db,'j',source['id'])
    source_plan=build_workspace_reconcile_plan(db,'j',source['id'],workspace)
    assert source_plan['summary']['ready'],source_plan['blockers']
    source_run=prepare_workspace_reconcile_run(
        db,'j',source['id'],workspace,expected_plan_token=source_plan['plan_token'],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db,source_run['id'],workspace)
    assert list_event_reassignments(db,'j',source['id'])['family_count']==1

    target_payload=payload('2026-07-23T00:00','2026-07-23T23:59',preserve_day_folders=preserve)
    target_payload['event_name']='Ziel'
    target=create(db,target_payload)['parent_event']  # normal free-card API path
    list_global_tasks(db)
    assert list_event_reassignments(db,'j',source['id'])['family_count']==0
    target_plan=build_event_sort_plan(db,'j',target['id'],workspace)
    assert target_plan['summary']['ready'],target_plan['blockers']
    target_run=prepare_sort_run(
        db,'j',target['id'],workspace,expected_plan_token=target_plan['plan_token'],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(db,target_run['id'],workspace)
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM events WHERE id=?',(source['id'],)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id=?',(source['id'],)).fetchone()[0]==0
        event=c.execute('SELECT status,preserve_day_folders FROM events WHERE id=?',(target['id'],)).fetchone()
        assert event['status']=='applied' and bool(event['preserve_day_folders']) is preserve
        file=c.execute('SELECT current_relative_path,sha256_current FROM files WHERE job_id=?',('j',)).fetchone()
    path=workspace/'Arbeitsbereich'/file['current_relative_path']
    assert path.read_bytes()==b'1'
    assert ('/2026-07-23/Alle/' in file['current_relative_path']) is preserve
    assert len(list((workspace/'Arbeitsbereich').rglob('1.JPG')))==1


@pytest.mark.parametrize('cancel',[False,True])
def test_0260_applied_year_change_document_lifecycle(tmp_path,cancel):
    from app.event_document import build_event_document_from_db,write_event_document
    from app.event_mutation import cancel_mutation
    from app.workspace_reconcile import build_workspace_reconcile_plan,prepare_workspace_reconcile_run,execute_workspace_reconcile_run
    from app.sort_apply import CONFIRMATION_PHRASE
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2025-12-31T10:00:00','2026-01-01T14:00:00'])
    event=create(db,payload('2025-12-31T00:00','2026-01-01T23:59'))['parent_event']
    attach_files(db,workspace,event['id'])
    old_document=write_event_document(
        workspace,build_event_document_from_db(db,workspace,'j',event['id'])
    )
    old_bytes=old_document.read_bytes()
    preview=build_event_preview(
        payload('2026-01-01T13:00','2026-01-01T15:00'),
        get_event_edit_context(db,'j',event['id'])['families'],
    )
    edited=update_event_definition(
        db,'j',event['id'],preview,event_name='Urlaub',notes='',
        expected_revision=1,workspace_path=workspace,
    )
    root=workspace/'Arbeitsbereich'
    new_document=root/'2026'/edited['event']['folder_name']/'event.json'
    assert old_document.read_bytes()==old_bytes
    assert not new_document.exists()
    if cancel:
        with database_connection(db) as connection:
            connection.execute('BEGIN IMMEDIATE')
            cancel_mutation(connection,edited['mutation_id'],'j',workspace_path=workspace)
            connection.commit()
        assert old_document.read_bytes()==old_bytes
        assert not new_document.exists()
        with database_connection(db) as connection:
            restored=connection.execute(
                'SELECT start_datetime,resort_required FROM events WHERE id=?',(event['id'],)
            ).fetchone()
            assert restored['start_datetime']=='2025-12-31T00:00:00'
            assert restored['resort_required']==0
        return
    plan=build_workspace_reconcile_plan(db,'j',event['id'],workspace)
    assert plan['summary']['ready'],plan['blockers']
    run=prepare_workspace_reconcile_run(
        db,'j',event['id'],workspace,
        expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db,run['id'],workspace)
    assert not old_document.exists()
    assert new_document.exists()
    assert (root/'2025'/'2025-12-31'/'1.JPG').read_bytes()==b'1'


def test_archive_parent_preview_keeps_files_read_only_and_cards_exact(tmp_path):
    from app.event_change_request import propose_event_change,get_event_change_files
    from app.archive_reassignment import assign_archive_reassignments
    from app.event_change_apply import confirm_event_change,verify_event_change,finish_event_change
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event'];attach_files(db,workspace,event['id'])
    with database_connection(db) as c:c.execute("UPDATE events SET status='archived',archived_at='2026-09-22' WHERE id=?",(event['id'],))
    before={str(p):p.read_bytes() for p in workspace.rglob('*') if p.is_file()}
    preview=build_event_preview(payload(),get_event_edit_context(db,'j',event['id'])['families'])
    cr=propose_event_change(db,'j',event['id'],preview,event_name='Urlaub')
    cards=list_job_planning_overview(db,'j')['available_day_groups']
    assert [(x['start_time'],x['end_time']) for x in cards]==[('00:00','12:59'),('15:01','23:59')]
    assert all(x['archive_change_request_id']==cr['change_request_id'] for x in cards)
    with pytest.raises(ValueError,match='durchgehenden'):
        assign_archive_reassignments(db,cr['change_request_id'],[f for x in cards for f in x['family_ids']],target_mode='new_event',new_event_name='disjoint')
    assign_archive_reassignments(db,cr['change_request_id'],[f for x in cards for f in x['family_ids']],target_mode='new_no_event')
    assert before=={str(p):p.read_bytes() for p in workspace.rglob('*') if p.is_file()}
    assert list_job_planning_overview(db,'j')['available_day_groups']==[]
    archive_root=workspace/'Arbeitsbereich'
    reviews=get_event_change_files(db,cr['change_request_id'])
    assert sum(row['action']=='move' for row in reviews)==2
    assert sum(row['action']=='keep' for row in reviews)==1
    assert all('Später zuordnen' not in row['new_path'] for row in reviews)
    confirm_event_change(db,cr['change_request_id'])
    assert not verify_event_change(db,cr['change_request_id'],archive_root)['complete']
    for review in reviews:
        if review['action']=='move':
            source=archive_root/review['old_path']
            target=archive_root/review['new_path']
            target.parent.mkdir(parents=True,exist_ok=True)
            source.rename(target)
    assert verify_event_change(db,cr['change_request_id'],archive_root)['complete']
    result=finish_event_change(db,cr['change_request_id'],archive_root)
    assert result['files_changed_by_app']==0
    remaining=next(row for row in reviews if row['action']=='keep')
    assert (archive_root/remaining['old_path']).read_bytes()==b'2'
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM event_assignments WHERE event_id=?',(event['id'],)).fetchone()[0]==1


def test_0260_archived_extension_conflict_does_not_cascade(tmp_path):
    from app.event_change_request import EventChangeRequestError,propose_event_change
    from tests.backend.test_0168_deep_workflows import add_file
    db=tmp_path/'db'
    setup(db,['2026-07-23T14:00:00','2026-07-23T18:00:00'])
    first=create(db,payload('2026-07-23T13:00','2026-07-23T15:00'))['parent_event']
    second=create(db,payload('2026-07-23T17:00','2026-07-23T19:00'))['parent_event']
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE events SET status='archived',archived_at='now',applied_at='now' "
            "WHERE id IN (?,?)",(first['id'],second['id']),
        )
        family_ids=[int(row[0]) for row in connection.execute('SELECT id FROM file_families ORDER BY id')]
    for family_id in family_ids:
        add_file(db,family_id,f'2026/archive/Alle/{family_id}.JPG')
    with database_connection(db) as connection:
        before=[tuple(row) for row in connection.execute('SELECT * FROM events ORDER BY id')]
    preview=build_event_preview(
        payload('2026-07-23T13:00','2026-07-23T19:00'),
        get_event_edit_context(db,'j',first['id'])['families'],
    )
    with pytest.raises(EventChangeRequestError,match='überschneidet'):
        propose_event_change(db,'j',first['id'],preview,event_name='Urlaub')
    with database_connection(db) as connection:
        assert [tuple(row) for row in connection.execute('SELECT * FROM events ORDER BY id')]==before
        assert connection.execute('SELECT COUNT(*) FROM event_change_requests').fetchone()[0]==0


@pytest.mark.parametrize('start,end,remaining',[
    ('09:00','11:00',1),
    ('13:00','15:00',2),
    ('17:00','19:00',3),
])
@pytest.mark.parametrize('preserve',[False,True])
def test_0260_archived_partial_day_paths_and_open_families(tmp_path,start,end,remaining,preserve):
    from app.event_change_request import propose_event_change,get_event_change_files
    from app.archive_reassignment import list_archive_reassignments
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    attach_files(db,workspace,event['id'])
    with database_connection(db) as connection:
        connection.execute("UPDATE events SET status='archived',archived_at='now' WHERE id=?",(event['id'],))
    before={str(path):path.read_bytes() for path in workspace.rglob('*') if path.is_file()}
    preview=build_event_preview(
        payload(f'2026-07-23T{start}',f'2026-07-23T{end}',preserve_day_folders=preserve),
        get_event_edit_context(db,'j',event['id'])['families'],
    )
    cr=propose_event_change(db,'j',event['id'],preview,event_name='Urlaub')
    reviews=get_event_change_files(db,cr['change_request_id'])
    retained=[row for row in reviews if row['family_id']==remaining]
    removed=[row for row in reviews if row['family_id']!=remaining]
    assert len(retained)==1 and len(removed)==2
    assert all(row['action']=='delete' and row['new_path']=='' for row in removed)
    assert retained[0]['new_path'].endswith(
        ('/2026-07-23/Alle/' if preserve else '/Alle/')+f'{remaining}.JPG'
    )
    assert list_archive_reassignments(db,cr['change_request_id'])['family_count']==2
    assert before=={str(path):path.read_bytes() for path in workspace.rglob('*') if path.is_file()}


def test_0260_archived_no_event_two_same_day_segments_reassigns_removed_segment(tmp_path):
    from app.event_change_request import propose_event_change,get_event_change_files
    from app.archive_reassignment import assign_archive_reassignments,list_archive_reassignments
    from app.event_change_apply import confirm_event_change,verify_event_change,finish_event_change
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T18:00:00'])
    original_segments=[
        {'day_key':'2026-07-23','start_time':'09:00','end_time':'11:00'},
        {'day_key':'2026-07-23','start_time':'17:00','end_time':'19:00'},
    ]
    event=create(db,{'event_kind':'no_event','no_event_segments':original_segments})['parent_event']
    attach_files(db,workspace,event['id'])
    with database_connection(db) as connection:
        connection.execute("UPDATE events SET status='archived',archived_at='now' WHERE id=?",(event['id'],))
    preview=build_event_preview(
        {'event_kind':'no_event','no_event_segments':original_segments[:1]},
        get_event_edit_context(db,'j',event['id'])['families'],
    )
    cr=propose_event_change(db,'j',event['id'],preview,event_name='Ohne Ereignis')
    state=list_archive_reassignments(db,cr['change_request_id'])
    assert state['family_count']==1
    assert [(segment['start_time'],segment['end_time']) for segment in state['reassignment_segments']]==[('17:00','19:00')]
    assign_archive_reassignments(
        db,cr['change_request_id'],[state['families'][0]['family_id']],
        target_mode='new_event',new_event_name='Abend',
    )
    archive_root=workspace/'Arbeitsbereich'
    reviews=get_event_change_files(db,cr['change_request_id'])
    moving=[review for review in reviews if review['action']=='move']
    assert len(moving)==1
    assert (archive_root/moving[0]['old_path']).read_bytes()==b'2'
    assert not (archive_root/moving[0]['new_path']).exists()
    confirm_event_change(db,cr['change_request_id'])
    assert not verify_event_change(db,cr['change_request_id'],archive_root)['complete']
    destination=archive_root/moving[0]['new_path']
    destination.parent.mkdir(parents=True,exist_ok=True)
    (archive_root/moving[0]['old_path']).rename(destination)
    assert verify_event_change(db,cr['change_request_id'],archive_root)['complete']
    result=finish_event_change(db,cr['change_request_id'],archive_root)
    assert result['files_changed_by_app']==0
    with database_connection(db) as connection:
        segments=connection.execute(
            'SELECT start_time,end_time FROM event_time_segments WHERE event_id=?',(event['id'],)
        ).fetchall()
        assert [tuple(row) for row in segments]==[('09:00','11:00')]
        assert connection.execute('SELECT COUNT(*) FROM event_assignments WHERE event_id=?',(event['id'],)).fetchone()[0]==1


def test_no_event_extension_uses_segment_dates_not_capture_bounds(tmp_path):
    db=tmp_path/'db';setup(db,['2026-07-24T14:00:00','2026-07-25T10:00:00'])
    event=create(db,{'event_kind':'no_event','no_event_segments':[{'day_key':'2026-07-24','start_time':'13:01','end_time':'22:59'}]})['parent_event']
    assign_free_families_to_existing_no_event(db,'j',event['id'],[{'day_key':'2026-07-25','start_time':'00:00','end_time':'23:59'}])
    context=get_event_edit_context(db,'j',event['id'])
    assert context['event']['start_datetime']=='2026-07-24T13:01:00'
    assert context['event']['end_datetime']=='2026-07-25T23:59:59'
    assert len(context['time_segments'])==2


def test_selection_passes_exact_bounds_in_executable_ui():
    import subprocess
    from app.workspace_ui import WORKSPACE_HTML
    a=WORKSPACE_HTML.index('    function applyAutomaticFreeTimeSuggestion')
    b=WORKSPACE_HTML.index('    async function openTaskReassignment',a)
    script="""const eventStartTime={},eventEndTime={},useTimeRange={};let visible=false;function setParentTimeFieldsVisible(value){visible=value;}\n"""+WORKSPACE_HTML[a:b]+"""
applyAutomaticFreeTimeSuggestion([{start_datetime:'2026-07-23T15:01:00',start_time:'15:01',end_time:'23:59'}]);
if(eventStartTime.value!=='15:01'||eventEndTime.value!=='23:59'||!useTimeRange.checked||!visible) process.exit(1);
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True)


def test_optional_children_do_not_open_parent_gaps_and_document_is_complete(tmp_path):
    from app.event_document import build_event_document_from_db
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    parts=[{'name':'Morgen','start_datetime':'2026-07-23T09:00','end_datetime':'2026-07-23T11:00'},
           {'name':'Abend','start_datetime':'2026-07-23T17:00','end_datetime':'2026-07-23T19:00'}]
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59',subevents=parts))['parent_event']
    attach_files(db,workspace,event['id'])
    with database_connection(db) as c:
        intervals=continuous_event_overlaps(c,'j','2026-07-23T14:00:00','2026-07-23T14:00:59')
        assert len(intervals)==1 and intervals[0]['id']==event['id']
        assert c.execute("SELECT a.event_id FROM event_assignments a JOIN file_families f ON f.id=a.family_id WHERE f.selected_capture_time='2026-07-23T14:00:00'").fetchone()[0]==event['id']
    doc=build_event_document_from_db(db,workspace,'j',event['id'])
    assert [x['name'] for x in doc['child_events']]==['Morgen','Abend']
    assert len(doc['event']['occupied_intervals'])==1
    assert all(x['folder_name'] in doc['structure'] for x in doc['child_events'])
    context=get_event_edit_context(db,'j',event['id'])
    new=build_event_preview(payload('2026-07-23T00:00','2026-07-23T23:59',subevents=context['child_events']),context['families'])
    update_event_definition(db,'j',event['id'],new,event_name='Urlaub',notes='',expected_revision=1)
    context=get_event_edit_context(db,'j',event['id'])
    assert len(context['child_events'])==2 and len(context['assigned_family_ids'])==3


def test_applied_adjacent_extension_requires_reconcile(tmp_path):
    db=tmp_path/'db';event,cards=split_day(db)
    with database_connection(db) as c:
        c.execute("UPDATE events SET status='applied',applied_at='2026-09-22' WHERE id=?",(event['id'],))
    result=create(db,payload('2026-07-23T15:01','2026-07-23T23:59',existing_parent_event_id=event['id'],selected_intervals=[cards[1]]))
    assert result['parent_event']['start_datetime']=='2026-07-23T13:00:00'
    assert result['parent_event']['end_datetime']=='2026-07-23T23:59:59'
    assert result['resort_required']
    assert result['parent_event']['resort_required']==1
    assert result['child_event'] is None
