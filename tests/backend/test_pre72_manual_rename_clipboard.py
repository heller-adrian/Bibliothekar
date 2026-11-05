"""Pre.7.2 regression: archived No Event rename → later day removal.

All evidence is synthetic and kept inside pytest tmp_path. No TrueNAS media or
live archive is read or changed. The tests also execute the clipboard helper in
a mocked modal DOM with Node, without assuming browser clipboard privileges.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.database import initialize_database, database_connection
from app.event_naming import (
    normalize_event_naming, protect_existing_no_event_folder,
)
from app.event_structure import build_event_preview
from app.event_document import build_event_document_from_db
from app.event_layout import ensure_event_layout_snapshot
from app.event_inventory import scan_event_inventory
from app.event_change_request import propose_event_change, get_event_change_files
from app.archive_change_assistant import build_archive_change_assistant
from app.event_structure_changes import (
    detect_event_structure_change, prepare_archived_structure_change,
    verify_archived_structure_change,
)
from app.manual_archive_structure_undo import set_archived_structure_review_mode
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW, seed_job, seed_event, seed_family, seed_file_for_family,
)


def _archived_no_event(tmp_path, *, renamed: bool):
    db=tmp_path/"catalog.sqlite3"
    workspace=tmp_path/"workspace"
    archive=tmp_path/"archive"
    workspace.mkdir()
    archive.mkdir()
    ensure_workspace_layout(workspace)
    initialize_database(db)
    root_name="07 - No Event" if renamed else "07 - Ohne Ereignis"
    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn,status="archived",folder=root_name)
        # Reproduce the old snapshot carried forward from the creation date.
        naming=normalize_event_naming({"no_event_label":"No Event"})
        conn.execute(
            """UPDATE events
                SET name='No Event',event_kind='no_event',
                    folder_naming_json=?,end_datetime='2026-07-24T23:59:59',
                    timeline_model='segments'
                WHERE id='e'""",
            (json.dumps(naming),),
        )
        kept, _ = seed_family(
            conn, content=b"kept-JPG",
            current_path=f"2026/{root_name}/Alle/A.JPG",
        )
        released = int(conn.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
                ) VALUES ('j','B','B','complete','2026-07-24T12:00:00','high')"""
        ).lastrowid)
        released_file=seed_file_for_family(
            conn,family_id=released,content=b"released-JPG",
            current_path=f"2026/{root_name}/Alle/B.JPG",filename="B.JPG",
        )
        conn.execute(
            "UPDATE files SET selected_capture_time='2026-07-24T12:00:00' WHERE id=?",
            (released_file,),
        )
        conn.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('e',?,NULL,'manual',?)",
            (released,NOW),
        )
        for day in ("2026-07-23","2026-07-24"):
            conn.execute(
                """INSERT INTO event_time_segments(
                    event_id,job_id,day_key,start_time,end_time,
                    start_datetime,end_datetime,source,created_at,updated_at
                ) VALUES ('e','j',?,'00:00','23:59',?,?,'user',?,?)""",
                (day,f"{day}T00:00:00",f"{day}T23:59:59",NOW,NOW),
            )
        ensure_event_layout_snapshot(conn,"e",now=NOW)
    event_dir=archive/"2026"/root_name
    for branch in ("Alle","Sortiert","Export"):
        (event_dir/branch).mkdir(parents=True,exist_ok=True)
    (event_dir/"Alle"/"A.JPG").write_bytes(b"kept-JPG")
    (event_dir/"Alle"/"B.JPG").write_bytes(b"released-JPG")
    document=build_event_document_from_db(
        db,workspace,"j","e",include_archived=True,
    )
    assert document is not None
    (event_dir/"event.json").write_text(json.dumps(document),encoding="utf-8")
    scan_event_inventory(
        db,archive,"j","e",root_kind="camera_archive",
        persist=True,fast_refresh=False,update_known_file_locations=False,
    )
    if renamed:
        changed=event_dir.with_name("07 - Ohne Ereignis")
        event_dir.rename(changed)
        scan_event_inventory(
            db,archive,"j","e",root_kind="camera_archive",
            persist=True,fast_refresh=False,update_known_file_locations=False,
        )
        task=detect_event_structure_change(db,"e")
        assert task is not None and task["detected"]["root_rename"], task
        set_archived_structure_review_mode(
            db,workspace,shared_work_root(workspace),task["id"],"accept",
        )
        prepared=prepare_archived_structure_change(
            db,workspace,task["id"],input_path="Alle",
            app_version="1.0.0-pre.7.2",work_root=shared_work_root(workspace),
        )
        shutil.copy2(prepared["prepared_event_json_path"],changed/"event.json")
        result=verify_archived_structure_change(
            db,archive,workspace,task["id"],work_root=shared_work_root(workspace),
        )
        assert result["status"]=="completed"
    return db,workspace,archive,kept,released


def test_pre72_name_policy_keeps_existing_custom_folder_but_does_not_change_new_events():
    naming=normalize_event_naming({"no_event_label":"No Event"})
    custom=protect_existing_no_event_folder(
        folder_name="07 - Ohne Ereignis",month_key="2026-07",naming=naming,
    )
    assert custom["mode"]=="locked"
    assert custom["locked_folder_name"]=="07 - Ohne Ereignis"
    assert protect_existing_no_event_folder(
        folder_name="07 - No Event",month_key="2026-07",naming=naming,
    )==naming
    assert build_event_preview({
        "event_kind":"no_event","event_name":"No Event",
        "no_event_segments":[
            {"day_key":"2026-07-23","start_time":"00:00","end_time":"23:59"}
        ],
        "preserve_day_folders":False,
        "folder_naming":naming,
    },[{
        "family_id":1,"selected_capture_time":"2026-07-23T12:00:00",
        "day_key":"2026-07-23","file_count":1,
    }])["parent_folder"]=="07 - No Event"


@pytest.mark.parametrize("confirmed_this_version",[False,True])
def test_pre72_remove_only_one_day_does_not_reinstate_no_event_root(
    tmp_path,monkeypatch,confirmed_this_version,
):
    db,workspace,archive,kept,released=_archived_no_event(
        tmp_path,renamed=confirmed_this_version,
    )
    from app import main
    monkeypatch.setattr(main,"current_database_file",lambda:db)
    # Existing Pre.7.1 data may carry a stale snapshot, while a newly
    # accepted manual rename must now persist a matching explicit override.
    with database_connection(db) as conn:
        event=conn.execute(
            "SELECT folder_name,folder_naming_json,name FROM events WHERE id='e'"
        ).fetchone()
        assert event["folder_name"]=="07 - Ohne Ereignis"
        naming=json.loads(event["folder_naming_json"])
        if confirmed_this_version:
            assert naming["mode"]=="locked"
            assert naming["locked_folder_name"]=="07 - Ohne Ereignis"
        else:
            assert naming["no_event_label"]=="No Event"

    edited=main._event_payload_with_folder_layout({
        "event_kind":"no_event",
        "event_name":event["name"],
        "no_event_segments":[
            {"day_key":"2026-07-23","start_time":"00:00","end_time":"23:59"}
        ],
        "preserve_day_folders":False,
    },event_id="e")
    assert edited["folder_naming"]["locked_folder_name"]=="07 - Ohne Ereignis"
    available=[
        {"family_id":kept,"selected_capture_time":"2026-07-23T12:00:00",
         "day_key":"2026-07-23","file_count":1},
        {"family_id":released,"selected_capture_time":"2026-07-24T12:00:00",
         "day_key":"2026-07-24","file_count":1},
    ]
    preview=build_event_preview(edited,available)
    assert preview["parent_folder"]=="07 - Ohne Ereignis"
    proposed=propose_event_change(
        db,"j","e",preview,event_name=event["name"],
        archive_root=archive,workspace_path=workspace,
    )
    requests=get_event_change_files(db,proposed["change_request_id"])
    assert requests
    assert any(r["action"]=="delete" for r in requests)
    assert not [r for r in requests if r["action"]=="move"], requests
    assistant=build_archive_change_assistant(
        db,archive,workspace,proposed["change_request_id"],
    )
    assert assistant["target_structure"]["root"].endswith("/2026/07 - Ohne Ereignis")
    assert not [
        op for op in assistant["operations"]
        if op["kind"] in {"move_archive_files","copy_helper_folders"}
    ],assistant["operations"]
    # The legitimate edit still requires the new event.json and explicit
    # release of the family removed from the No Event month.
    assert assistant["release_stock"]["required"]


def test_pre72_clipboard_executed_in_modal_with_truthful_status():
    from app.events_ui import EVENTS_HTML
    source=EVENTS_HTML
    start=source.index("      async function bkPre72CopyArchiveName(")
    end=source.index('      if(archiveMode==="undo"){',start)
    helper=source[start:end]
    script=r"""
const assert=require('node:assert/strict');
const clipboardHelper = __HELPER__;
const name='07 - Ohne Ereignis';
const state={copied:null,execCalls:0,appendedTo:null};
const document={
  activeElement:null,
  createElement:()=>({
    value:'',style:{},selectionStart:0,selectionEnd:0,
    setAttribute(){},focus(){document.activeElement=this},
    select(){this.selectionStart=0;this.selectionEnd=this.value.length},
    setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b},
    remove(){},
  }),
  execCommand(command){
    assert.equal(command,'copy');
    state.execCalls++;
    if(document.activeElement && document.activeElement.value===name)
      state.copied=name;
    return true;
  }
};
const dialog={
  open:true,contains:()=>true,
  appendChild(field){state.appendedTo=this;field.parent=this}
};
const feedback={textContent:''};
const manual={hidden:true};
const manualField={focus(){},select(){},setSelectionRange(){}};
const bk0511EventLabel=(de,en)=>en;
let window={isSecureContext:false};
let navigator={};
async function run(){
  let result=await clipboardHelper({text:name,dialog,feedback,manual,manualField});
  assert.equal(result,'legacy-unverified');
  assert.equal(state.appendedTo,dialog);
  assert.equal(state.copied,name);
  assert.equal(state.execCalls,1);
  assert.match(feedback.textContent,/Paste to confirm/);
  state.execCalls=0;state.copied=null;
  window.isSecureContext=true;
  navigator.clipboard={writeText:async(text)=>{state.copied=text}};
  result=await clipboardHelper({text:name,dialog,feedback,manual,manualField});
  assert.equal(result,'modern-confirmed');
  assert.equal(state.execCalls,0);
  assert.equal(state.copied,name);
  assert.equal(feedback.textContent,'Copied to clipboard.');
  window.isSecureContext=false;
  dialog.open=false;
  result=await clipboardHelper({text:name,dialog,feedback,manual,manualField});
  assert.equal(result,'manual');
  assert.equal(manual.hidden,false);
  assert.match(feedback.textContent,/Automatic copy unavailable/);
  // Even if execCommand falsely returns true, a non-focused field must
  // never lead to a claimed success or a call to execCommand.
  dialog.open=true;
  document.createElement=()=>({
    value:'',style:{},selectionStart:0,selectionEnd:0,setAttribute(){},
    focus(){},select(){},setSelectionRange(){},remove(){}
  });
  state.execCalls=0;
  result=await clipboardHelper({text:name,dialog,feedback,manual,manualField});
  assert.equal(result,'manual');
  assert.equal(state.execCalls,0);
}
run().catch(e=>{console.error(e);process.exitCode=1});
""".replace("__HELPER__",helper)
    subprocess.run(["node","-e",script],check=True,capture_output=True,text=True)
