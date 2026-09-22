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
        rel=f"2026/{event['folder_name']}/Alle/{f['id']}.JPG"
        content,digest=add_file(db,int(f['id']),rel,payload=str(f['id']).encode())
        path=workspace/'Arbeitsbereich'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    with database_connection(db) as c:
        c.execute("UPDATE files SET current_root_kind='shared_workspace'")
        c.execute("UPDATE events SET status='applied',applied_at='2026-09-22' WHERE id=?",(event_id,))


def test_manual_workspace_assignment_then_confirmed_reconcile(tmp_path):
    from app.workspace_reconcile import build_workspace_reconcile_plan,prepare_workspace_reconcile_run,execute_workspace_reconcile_run
    from app.sort_apply import CONFIRMATION_PHRASE, SortApplyError
    from app.event_document import build_event_document_from_db,write_event_document
    db=tmp_path/'db';workspace=tmp_path/'workspace'
    setup(db,['2026-07-23T10:00:00','2026-07-23T14:00:00','2026-07-23T18:00:00'])
    event=create(db,payload('2026-07-23T00:00','2026-07-23T23:59'))['parent_event']
    attach_files(db,workspace,event['id'])
    write_event_document(workspace,build_event_document_from_db(db,workspace,'j',event['id']))
    root=workspace/'Arbeitsbereich'
    with database_connection(db) as c:
        before_paths={int(r['id']):str(r['current_relative_path']) for r in c.execute("SELECT id,current_relative_path FROM files WHERE job_id='j' ORDER BY id")}
    before_bytes={fid:(root/rel).read_bytes() for fid,rel in before_paths.items()}
    preview=build_event_preview(payload(),get_event_edit_context(db,'j',event['id'])['families'])
    edited=update_event_definition(db,'j',event['id'],preview,event_name='Urlaub',notes='',expected_revision=1,workspace_path=workspace)
    assert edited['neutralized_file_count']==0
    assert edited['neutralized_files']==[]
    with database_connection(db) as c:
        after_edit_paths={int(r['id']):str(r['current_relative_path']) for r in c.execute("SELECT id,current_relative_path FROM files WHERE job_id='j' ORDER BY id")}
    assert after_edit_paths==before_paths
    assert all((root/rel).read_bytes()==before_bytes[fid] for fid,rel in before_paths.items())
    assert not (root/'Nicht zugeordnet').exists()
    blocked=build_workspace_reconcile_plan(db,'j',event['id'],workspace)
    assert not blocked['summary']['ready']
    cards=list_job_planning_overview(db,'j')['available_day_groups']
    target=create(db,{'event_kind':'no_event','no_event_segments':cards})['parent_event']
    with database_connection(db) as c:
        before_reconcile_paths={int(r['id']):str(r['current_relative_path']) for r in c.execute("SELECT id,current_relative_path FROM files WHERE job_id='j' ORDER BY id")}
    assert before_reconcile_paths==before_paths
    assert all((root/rel).read_bytes()==before_bytes[fid] for fid,rel in before_paths.items())
    plan=build_workspace_reconcile_plan(db,'j',event['id'],workspace)
    assert plan['summary']['ready'],plan['blockers']
    with pytest.raises(SortApplyError,match='Bestätigung'):
        prepare_workspace_reconcile_run(db,'j',event['id'],workspace,expected_plan_token=plan['plan_token'],confirmation_phrase='')
    run=prepare_workspace_reconcile_run(db,'j',event['id'],workspace,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
    execute_workspace_reconcile_run(db,run['id'],workspace)
    assert len(list((workspace/'Arbeitsbereich'/'2026'/'07 - Ohne Ereignis'/'Alle').glob('*.JPG')))==2
    doc=json.loads((workspace/'Arbeitsbereich'/'2026'/'07 - Ohne Ereignis'/'event.json').read_text())
    assert len(doc['no_event_segments'])==2
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM event_reapply_removed_families').fetchone()[0]==0
        assert c.execute('SELECT status FROM events WHERE id=?',(target['id'],)).fetchone()[0]=='applied'


def test_archive_parent_preview_keeps_files_read_only_and_cards_exact(tmp_path):
    from app.event_change_request import propose_event_change,get_event_change_files
    from app.archive_reassignment import assign_archive_reassignments
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
    script="""const eventStartTime={},eventEndTime={},useTimeRange={},timeFields={},childEventName={};\n"""+WORKSPACE_HTML[a:b]+"""
applyAutomaticFreeTimeSuggestion([{start_datetime:'2026-07-23T15:01:00',start_time:'15:01',end_time:'23:59'}]);
if(eventStartTime.value!=='15:01'||eventEndTime.value!=='23:59'||!useTimeRange.checked||childEventName.required) process.exit(1);
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
