"""Gemeinsamer Arbeitsbereich-Abgleich nach strukturellen Änderungen.

0.16.10 ersetzt den ereignisweisen Reapply für angewendete Ereignisse durch
EINE zusammenhängende, prüfsummensichere Reconciliation über alle direkt
betroffenen applied-Ereignisse. Archivierte Ereignisse werden niemals
physisch verändert; sie werden als manueller Anteil gemeldet.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import uuid

from app.database import database_connection
from app.sort_plan import build_event_sort_plan, SortPlanError, _build_family_target_groups
from app.sort_apply import (
    CONFIRMATION_PHRASE, SortApplyError, _now, _json_details, _sha256_file,
    _assert_source_identity, _move_without_overwrite, _rollback_one,
    _fsync_directory,
)

ACTIVE = ("queued","verifying","moving","finalizing","rolling_back","interrupted")


def _recover_missing_workspace_sources(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover stale SQLite IST paths inside the shared workspace safely.

    Older app versions could leave ``files.current_relative_path`` behind after
    some reassignment flows.  A reconciliation must not guess.  For every
    missing source we therefore accept a replacement only if exactly one file
    in the shared workspace has the expected basename, byte size and SHA-256.
    The database is not changed here; successful execution later persists the
    final SOLL path as usual.
    """
    missing: list[tuple[dict[str, Any], dict[str, Any]]] = []
    roots: set[Path] = set()
    wanted_names: set[str] = set()
    wanted_sizes: set[int] = set()
    for plan in plans:
        root_text = str(plan.get("target_root") or "").strip()
        if not root_text:
            continue
        root = Path(root_text).resolve(strict=False)
        roots.add(root)
        for entry in plan.get("files", []):
            if entry.get("source_exists"):
                continue
            name = Path(str(entry.get("source_relative_path") or "")).name
            if not name:
                continue
            missing.append((plan, entry))
            wanted_names.add(name)
            wanted_sizes.add(int(entry.get("expected_size_bytes") or 0))
    if not missing or len(roots) != 1:
        return plans

    root = next(iter(roots))
    candidates: dict[str, list[Path]] = {name: [] for name in wanted_names}
    candidates_by_size: dict[int, list[Path]] = {size: [] for size in wanted_sizes if size >= 0}
    # A single walk is important for large SSD workspaces.  First prefer the
    # original basename.  0.17.0 additionally retains candidates with a
    # matching byte size, so files renamed by an older sort can still be
    # recovered uniquely by SHA-256 instead of producing a stale-path blocker.
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        # Never follow symlinked directory components.
        kept=[]
        for d in dirnames:
            q=base/d
            try:
                if not q.is_symlink(): kept.append(d)
            except OSError:
                continue
        dirnames[:] = kept
        for name in filenames:
            candidate = base / name
            if name in candidates:
                candidates[name].append(candidate)
            try:
                st = candidate.stat(follow_symlinks=False)
            except OSError:
                continue
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if int(st.st_size) in candidates_by_size:
                candidates_by_size[int(st.st_size)].append(candidate)

    recovered_ids: set[int] = set()
    for plan, entry in missing:
        fid = int(entry["file_id"])
        name = Path(str(entry.get("source_relative_path") or "")).name
        expected_size = int(entry.get("expected_size_bytes") or 0)
        expected_sha = str(entry.get("stored_sha256") or "").strip()
        exact: list[tuple[Path, os.stat_result, str]] = []
        preferred = list(candidates.get(name, []))
        # If the old basename no longer exists, or does not hash correctly,
        # use every same-size workspace file as a second-stage candidate.
        candidate_pool = preferred + [
            q for q in candidates_by_size.get(expected_size, []) if q not in preferred
        ]
        for candidate in candidate_pool:
            try:
                st = candidate.stat(follow_symlinks=False)
            except OSError:
                continue
            if not candidate.is_file() or candidate.is_symlink() or int(st.st_size) != expected_size:
                continue
            if not expected_sha:
                continue
            try:
                digest = _sha256_file(candidate)
            except OSError:
                continue
            if digest == expected_sha:
                exact.append((candidate.resolve(strict=False), st, digest))
        if len(exact) != 1:
            if len(exact) > 1:
                plan.setdefault("blockers", []).append({
                    "code": "source_recovery_ambiguous",
                    "file_id": fid,
                    "message": "Der gespeicherte IST-Pfad ist veraltet; mehrere byteidentische Dateien wurden im Arbeitsbereich gefunden. Automatische Zuordnung ist deshalb absichtlich blockiert.",
                })
            continue
        candidate, st, digest = exact[0]
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        destination = Path(str(entry["destination_absolute_path"])).resolve(strict=False)
        same_path = candidate == destination
        target_exists = destination.exists()
        entry.update({
            "source_relative_path": relative.as_posix(),
            "source_absolute_path": str(candidate),
            "current_root_kind": "shared_workspace",
            "source_size_bytes": int(st.st_size),
            "source_device": int(st.st_dev),
            "source_inode": int(st.st_ino),
            "source_mtime_ns": int(st.st_mtime_ns),
            "size_matches": True,
            "source_exists": True,
            "source_readable": os.access(candidate, os.R_OK),
            "source_is_regular_file": True,
            "same_path": same_path,
            "target_exists": target_exists,
            "target_is_directory": destination.is_dir() if target_exists else False,
            "calculated_sha256": digest,
            "sha256_matches": True,
            "status": "already_at_target" if same_path else ("blocked_target_exists" if target_exists else "move"),
        })
        recovered_ids.add(fid)
        plan.setdefault("warnings", []).append({
            "code": "stale_current_path_recovered",
            "file_id": fid,
            "message": "Ein veralteter SQLite-IST-Pfad wurde anhand von Dateigröße und SHA-256 eindeutig im SSD-Arbeitsbereich wiedergefunden: " + relative.as_posix(),
        })

    if recovered_ids:
        for plan in plans:
            cleaned=[]
            for blocker in plan.get("blockers", []):
                fid = blocker.get("file_id")
                code = str(blocker.get("code") or "")
                if fid is not None and int(fid) in recovered_ids and code in {"source_missing", "target_exists"}:
                    # target_exists is only stale when the recovered source is
                    # already exactly at that destination; preserve it otherwise.
                    ent=next((f for f in plan.get("files",[]) if int(f["file_id"])==int(fid)),None)
                    if code == "source_missing" or (ent and ent.get("same_path")):
                        continue
                cleaned.append(blocker)
            plan["blockers"] = cleaned
    return plans


def _workspace_structure_text(
    directory_rows: list[dict[str, Any]],
    archived_impacts: list[dict[str, Any]] | None = None,
) -> str:
    """Render the actual planned folder tree for the shared reconciliation."""
    tree: dict[str, Any] = {}
    for row in directory_rows:
        raw = str(row.get("relative_path") or "").strip()
        if not raw:
            continue
        node = tree
        for part in PurePosixPath(raw).parts:
            node = node.setdefault(part, {})

    lines: list[str] = []

    branch_order = {"Alle": 0, "Sortiert": 1, "Export": 2}

    def sort_key(item: tuple[str, Any]) -> tuple[int, Any]:
        name = item[0]
        if name in branch_order:
            return (0, branch_order[name])
        return (1, name.casefold())

    def render(node: dict[str, Any], prefix: str = "") -> None:
        items = sorted(node.items(), key=sort_key)
        for index, (name, children) in enumerate(items):
            last = index == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name)
            render(children, prefix + ("    " if last else "│   "))

    for name, children in sorted(tree.items(), key=lambda item: item[0].casefold()):
        lines.append(name)
        render(children)

    for item in archived_impacts or []:
        if lines:
            lines.append("")
        lines.append(f"ARCHIVIERT · {item['name']} · nur manueller Auftrag")
    return "\n".join(lines) or "Keine Zielstruktur vorhanden."


def _event_interval(row: Any) -> tuple[str, str]:
    return (str(row["start_datetime"] or "")[:19], str(row["end_datetime"] or "")[:19])


def _overlap(a: tuple[str,str], b: tuple[str,str]) -> bool:
    return bool(a[0] and a[1] and b[0] and b[1] and a[0] <= b[1] and b[0] <= a[1])


def _connected_applied_events(connection: Any, job_id: str, anchor_event_id: str) -> tuple[list[str], list[dict[str,Any]]]:
    rows = connection.execute(
        """SELECT id,job_id,name,status,start_datetime,end_datetime,resort_required,archived_at
           FROM events WHERE parent_event_id IS NULL
             AND COALESCE(TRIM(linkage_kind),'')=''
             AND status IN ('planned','applied','archived')"""
    ).fetchall()
    by_id={str(r['id']):r for r in rows}
    anchor=by_id.get(anchor_event_id)
    if anchor is None or str(anchor['job_id']) != str(job_id):
        raise SortPlanError("Ereignis wurde nicht gefunden.")
    if str(anchor['status']) != 'applied' or int(anchor['resort_required'] or 0) != 1:
        raise SortPlanError("Für dieses Ereignis ist keine gemeinsame Nachsortierung offen.")

    edges: dict[str,set[str]]={eid:set() for eid in by_id}
    # Durable family transitions are the strongest connection signal.
    qrows=connection.execute(
        """SELECT event_id,target_event_id FROM event_reapply_removed_families
           WHERE target_event_id IS NOT NULL"""
    ).fetchall()
    for q in qrows:
        a,b=str(q['event_id']),str(q['target_event_id'])
        if a in edges and b in edges:
            edges[a].add(b); edges[b].add(a)

    # Time-overlap joins edited applied events even when no family fell out.
    changed=[r for r in rows if str(r['status'])=='applied' and int(r['resort_required'] or 0)==1]
    for i,a in enumerate(changed):
        for b in changed[i+1:]:
            if _overlap(_event_interval(a),_event_interval(b)):
                edges[str(a['id'])].add(str(b['id'])); edges[str(b['id'])].add(str(a['id']))

    seen={anchor_event_id}; todo=deque([anchor_event_id])
    while todo:
        cur=todo.popleft()
        for nxt in edges.get(cur,set()):
            if nxt not in seen:
                seen.add(nxt); todo.append(nxt)

    applied=sorted(eid for eid in seen if eid in by_id and (str(by_id[eid]['status'])=='planned' or (str(by_id[eid]['status'])=='applied' and int(by_id[eid]['resort_required'] or 0)==1)))
    archived=[]
    # Archived targets touched by a reassignment are explicitly surfaced.
    for eid in sorted(seen):
        r=by_id.get(eid)
        if r is not None and str(r['status'])=='archived':
            archived.append({"event_id":eid,"name":str(r['name']),"status":"archived"})
    # Also include direct archived targets from queued family transitions.
    for q in connection.execute(
        """SELECT DISTINCT r.target_event_id,e.name,e.status FROM event_reapply_removed_families r
           JOIN events e ON e.id=r.target_event_id
           WHERE r.event_id IN (%s) AND e.status='archived'""" % ",".join("?" for _ in applied),
        tuple(applied),
    ).fetchall() if applied else []:
        item={"event_id":str(q['target_event_id']),"name":str(q['name']),"status":"archived"}
        if item not in archived: archived.append(item)
    return applied, archived


def build_workspace_reconcile_plan(database_path: Path, job_id: str, anchor_event_id: str, workspace_path: Path, *, verify_sha256: bool=False) -> dict[str,Any]:
    with database_connection(database_path) as c:
        from app.event_reassignment import reconcile_stale_event_reassignments
        reconcile_stale_event_reassignments(c,event_id=anchor_event_id)
        event_ids, archived_impacts = _connected_applied_events(c,job_id,anchor_event_id)
    blockers=[]

    with database_connection(database_path) as c:
        owner_rows = c.execute(
            """SELECT ea.family_id, COALESCE(e.parent_event_id,e.id) AS root_event_id
               FROM event_assignments ea JOIN events e ON e.id=ea.event_id
               WHERE ea.family_id IS NOT NULL
                 AND e.status IN ('draft','planned','applied','archived')"""
        ).fetchall()
    owner_by_family={int(r['family_id']):str(r['root_event_id']) for r in owner_rows}

    plans=[]; by_file: dict[int,dict[str,Any]]={}; by_file_source: dict[int,str]={}; directories: dict[str,dict[str,Any]]={}
    by_asset: dict[str,dict[str,Any]] = {}
    managed_event_roots: set[str] = set()
    warnings=[]
    for eid in event_ids:
        try:
            with database_connection(database_path) as c:
                event_row=c.execute('SELECT status,job_id FROM events WHERE id=?',(eid,)).fetchone()
                event_status=event_row['status']
                event_job_id=str(event_row['job_id'])
            p=build_event_sort_plan(database_path,event_job_id,eid,workspace_path,verify_sha256=verify_sha256,allow_reapply=event_status=='applied')
        except SortPlanError as exc:
            blockers.append({"code":"event_plan_failed","event_id":eid,"message":str(exc)})
            continue
        plans.append(p)

    _recover_missing_workspace_sources(plans)

    for p in plans:
        event_info = dict(p.get("event") or {})
        eid=str(event_info.get('id') or '')
        target_root_raw = str(p.get("target_root") or "")
        year = str(event_info.get("start_datetime") or "")[:4]
        physical_parts = [str(part) for part in (event_info.get("physical_folder_parts") or []) if str(part)]
        if not physical_parts and event_info.get("folder_name"):
            physical_parts = [str(event_info.get("folder_name"))]
        if target_root_raw and len(year) == 4 and physical_parts:
            managed_event_roots.add(
                str(Path(target_root_raw).joinpath(year, *physical_parts).resolve(strict=False))
            )
        for b in p.get('blockers',[]): blockers.append({**b,"event_id":eid})
        for w in p.get('warnings',[]): warnings.append({**w,"event_id":eid})
        for d in p.get('directories',[]): directories[str(d['relative_path'])]=d
        for f in p.get('files',[]):
            fid=int(f['file_id']); family_id=int(f['family_id']) if f.get('family_id') is not None else None
            prior=by_file.get(fid)
            if prior is not None and str(prior['destination_relative_path']) != str(f['destination_relative_path']):
                owner = owner_by_family.get(family_id) if family_id is not None else None
                prior_source = by_file_source.get(fid)
                # The current assignment is the canonical desired state. A source
                # event may still carry a durable removed-family row with an older,
                # less specific folder hint; that must not override the live target.
                if owner == eid:
                    by_file[fid]=f; by_file_source[fid]=eid
                    continue
                if owner == prior_source:
                    continue
                blockers.append({"code":"conflicting_destination","file_id":fid,"message":"Eine Datei erhält innerhalb der gemeinsamen Änderung zwei verschiedene SOLL-Pfade, ohne eindeutige Zielzuordnung."})
                continue
            by_file[fid]=f; by_file_source[fid]=eid
        for asset in p.get('assets',[]) or []:
            key=str(asset.get('source_relative_path') or '')
            if not key:
                blockers.append({
                    "code":"asset_source_missing_path",
                    "event_id":eid,
                    "message":"Eine Zusatzdatei besitzt keinen eindeutigen Quellpfad."
                })
                continue
            prior_asset=by_asset.get(key)
            if prior_asset is not None and str(prior_asset.get('destination_relative_path')) != str(asset.get('destination_relative_path')):
                blockers.append({
                    "code":"conflicting_asset_destination",
                    "event_id":eid,
                    "path":key,
                    "message":"Eine Zusatzdatei erhält innerhalb der gemeinsamen Änderung zwei verschiedene SOLL-Pfade."
                })
                continue
            by_asset[key]=asset

    files=sorted(by_file.values(),key=lambda x:(str(x['destination_relative_path']),int(x['file_id'])))
    assets=sorted(by_asset.values(),key=lambda x:(str(x['destination_relative_path']),str(x['source_relative_path'])))
    families, target_groups = _build_family_target_groups(files, assets)
    total=sum(int(f.get('expected_size_bytes') or 0) for f in [*files,*assets])
    move_count=sum(1 for f in [*files,*assets] if f.get('status')=='move')
    anchor_plan = next((p for p in plans if str(p.get("event",{}).get("id")) == anchor_event_id), plans[0] if plans else None)
    event_obj = dict(anchor_plan.get("event") or {}) if anchor_plan else {"id":anchor_event_id,"name":"Gemeinsame Änderung"}
    job_obj = dict(anchor_plan.get("job") or {}) if anchor_plan else {"id":job_id}
    structure_text = _workspace_structure_text(
        list(directories.values()),
        archived_impacts,
    )
    payload={
        "job_id":job_id,"anchor_event_id":anchor_event_id,"event_ids":event_ids,
        "archived_impacts":archived_impacts,
        "managed_event_roots":sorted(managed_event_roots),
        "files":[[int(f['file_id']),str(f['source_relative_path']),str(f['destination_relative_path']),str(f.get('destination_root_kind') or 'target_root'),str(f.get('stored_sha256') or '')] for f in files],
        "assets":[[str(a.get('asset_kind') or 'other'),str(a['source_relative_path']),str(a['destination_relative_path']),str(a.get('destination_root_kind') or 'target_root'),str(a.get('stored_sha256') or '')] for a in assets],
    }
    token=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {
        "kind":"workspace_reconciliation","job_id":job_id,"anchor_event_id":anchor_event_id,
        "event_ids":event_ids,"archived_impacts":archived_impacts,"files":files,"assets":assets,
        "managed_event_roots":sorted(managed_event_roots),
        "event":event_obj,"job":job_obj,"families":families,"target_groups":target_groups,
        "workspace_root":str(anchor_plan.get("workspace_root") or "") if anchor_plan else "",
        "source_root":str(anchor_plan.get("target_root") or "") if anchor_plan else "",
        "target_root":str(anchor_plan.get("target_root") or "") if anchor_plan else "",
        "central_stock_root":str(
            anchor_plan.get("central_stock_root")
            or anchor_plan.get("target_root")
            or ""
        ) if anchor_plan else "",
        "directories":list(directories.values()),"blockers":blockers,"warnings":warnings,
        "structure_text":structure_text,
        "plan_token":token,"apply_confirmation_phrase":CONFIRMATION_PHRASE,
        "summary":{"ready":not blockers and not archived_impacts,"event_count":len(event_ids),"file_count":len(files)+len(assets),"camera_file_count":len(files),"asset_count":len(assets),"family_count":len(families),"target_group_count":len(target_groups),"move_count":move_count,"directory_count":len(directories),"directory_create_count":sum(1 for d in directories.values() if not d.get('exists')),"total_size_bytes":total,"available_bytes":int((anchor_plan.get("summary") or {}).get("available_bytes") or 0) if anchor_plan else 0,"required_extra_bytes":0,"same_filesystem":True if anchor_plan else False,"archived_event_count":len(archived_impacts),"blocker_count":len(blockers)},
        "manual_archive_required":bool(archived_impacts),
        "message":("Archivierte Ereignisse sind betroffen. Zuerst Neu-Zuordnungen abschließen und den manuellen Archivauftrag bestätigen." if archived_impacts else "Gemeinsamer Arbeitsbereich-Abgleich bereit."),
    }


def prepare_workspace_reconcile_run(database_path: Path,job_id:str,anchor_event_id:str,workspace_path:Path,*,expected_plan_token:str,confirmation_phrase:str)->dict[str,Any]:
    if confirmation_phrase != CONFIRMATION_PHRASE: raise SortApplyError("Die ausdrückliche Bestätigung für den Arbeitsbereich-Abgleich fehlt.")
    plan=build_workspace_reconcile_plan(database_path,job_id,anchor_event_id,workspace_path)
    if not plan['summary']['ready']: raise SortApplyError("Der gemeinsame Änderungsplan besitzt Blocker und darf nicht angewendet werden.")
    if str(expected_plan_token)!=str(plan['plan_token']): raise SortApplyError("Der gemeinsame Änderungsplan ist nicht mehr aktuell. Bitte erneut prüfen.")
    run_id='RECON_'+uuid.uuid4().hex.upper(); now=_now(); root=str(Path(plan['target_root']).resolve(strict=False)); central=str(Path(plan.get('central_stock_root') or plan['target_root']).resolve(strict=False))
    with database_connection(database_path) as c:
        c.execute('BEGIN IMMEDIATE')
        for eid in plan['event_ids']:
            active=c.execute("SELECT id FROM sort_runs WHERE event_id=? AND status IN (?,?,?,?,?,?) LIMIT 1",(eid,*ACTIVE)).fetchone()
            if active: raise SortApplyError("Für mindestens ein betroffenes Ereignis läuft bereits eine Sortierung.")
        details={"event_ids":plan['event_ids'],"archived_impacts":plan['archived_impacts'],"planned_directories":[str(d['relative_path']) for d in plan['directories']],"managed_event_roots":plan.get('managed_event_roots',[])}
        c.execute("""INSERT INTO sort_runs(id,job_id,event_id,plan_token,status,phase,source_root,target_root,central_root,file_count,verified_file_count,move_count,moved_file_count,directory_count,created_directory_count,total_size_bytes,verified_bytes,moved_bytes,error_message,details_json,created_at,started_at,updated_at,completed_at,run_kind)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (run_id,job_id,anchor_event_id,plan['plan_token'],'queued',
                   'Gemeinsamer Arbeitsbereich-Abgleich wartet auf SHA-256-Prüfung',root,root,central,
                   plan['summary']['file_count'],0,plan['summary']['move_count'],0,
                   plan['summary']['directory_count'],0,plan['summary']['total_size_bytes'],0,0,None,
                   _json_details(details),now,None,now,None,'reapply'))
        ops=[]
        for seq,f in enumerate(plan['files'],1):
            ops.append((run_id,seq,int(f['file_id']),str(f['source_relative_path']),str(f['destination_relative_path']),int(f['expected_size_bytes']),str(f['stored_sha256']),str(f.get('current_root_kind') or 'shared_workspace'),str(f.get('destination_root_kind') or 'target_root'),'already_at_target' if f['status']=='already_at_target' else 'planned'))
        c.executemany("""INSERT INTO sort_operations(sort_run_id,sequence_number,file_id,source_relative_path,destination_relative_path,expected_size_bytes,expected_sha256,source_root_kind,destination_root_kind,status) VALUES (?,?,?,?,?,?,?,?,?,?)""",ops)
        asset_ops=[]
        offset=len(plan['files'])
        for index,a in enumerate(plan.get('assets') or [],1):
            asset_ops.append((
                run_id,offset+index,str(a.get('asset_kind') or 'other'),
                a.get('family_id'),a.get('source_file_id'),
                str(a['source_relative_path']),str(a['destination_relative_path']),
                int(a['expected_size_bytes']),str(a.get('stored_sha256') or ''),
                str(a.get('source_root_kind') or a.get('current_root_kind') or 'shared_workspace'),
                str(a.get('destination_root_kind') or 'target_root'),
                'already_at_target' if a.get('status')=='already_at_target' else 'planned'
            ))
        c.executemany(
            """INSERT INTO sort_asset_operations(
                   sort_run_id,sequence_number,asset_kind,family_id,source_file_id,
                   source_relative_path,destination_relative_path,expected_size_bytes,
                   expected_sha256,source_root_kind,destination_root_kind,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            asset_ops,
        )
        c.execute("INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'workspace_reconciliation_queued','sort_run',?,?,?)",(job_id,run_id,_json_details(details),now))
        c.commit()
    from app.sort_apply import get_sort_run
    return get_sort_run(database_path,job_id,run_id)


def execute_workspace_reconcile_run(database_path:Path,run_id:str,workspace_path:Path)->None:
    moved=[]; created=[]
    try:
        with database_connection(database_path) as c:
            run=c.execute("SELECT * FROM sort_runs WHERE id=?",(run_id,)).fetchone()
            if run is None: raise SortApplyError("Abgleichslauf wurde nicht gefunden.")
            details=json.loads(str(run['details_json'] or '{}')); job_id=str(run['job_id']); anchor=str(run['event_id'])
        plan=build_workspace_reconcile_plan(database_path,job_id,anchor,workspace_path)
        if not bool(plan['summary']['ready']):
            messages='; '.join(
                str(item.get('message') or item.get('code'))
                for item in (plan.get('blockers') or [])[:5]
            )
            raise SortApplyError(
                "Die erneute Prüfung des Änderungsplans erkannte Blocker"
                + (": " + messages if messages else ".")
            )
        if str(plan['plan_token'])!=str(run['plan_token']):
            raise SortApplyError("Der Änderungsplan hat sich seit der Bestätigung verändert.")
        root=Path(plan['files'][0]['source_absolute_path']).parents[0] if False else Path(run['source_root']).resolve(strict=False)
        # Create all required directories safely.
        for d in sorted({Path(x['absolute_path']).resolve(strict=False) for x in plan['directories']},key=lambda p:len(p.parts)):
            if not d.exists(): d.mkdir(parents=True,exist_ok=True); created.append(d)
        with database_connection(database_path) as c: c.execute("UPDATE sort_runs SET status='verifying',phase='SHA-256-Prüfung aller betroffenen Dateien',started_at=?,updated_at=? WHERE id=?",(_now(),_now(),run_id))
        for f in plan['files']:
            src=Path(f['source_absolute_path']); _assert_source_identity(src,f)
            digest=_sha256_file(src)
            if digest != str(f['stored_sha256']): raise SortApplyError("SHA-256-Prüfung fehlgeschlagen: "+str(src))
            with database_connection(database_path) as c:
                c.execute("UPDATE sort_operations SET status=CASE WHEN status='planned' THEN 'verified' ELSE status END,verified_at=? WHERE sort_run_id=? AND file_id=?",(_now(),run_id,int(f['file_id'])))
                c.execute("UPDATE sort_runs SET verified_file_count=verified_file_count+1,verified_bytes=verified_bytes+?,updated_at=? WHERE id=?",(int(f['expected_size_bytes']),_now(),run_id))
        for a in plan.get('assets') or []:
            src=Path(a['source_absolute_path']); _assert_source_identity(src,a)
            digest=_sha256_file(src)
            if digest != str(a.get('stored_sha256') or ''): raise SortApplyError("SHA-256-Prüfung der Zusatzdatei fehlgeschlagen: "+str(src))
            with database_connection(database_path) as c:
                c.execute("UPDATE sort_asset_operations SET status=CASE WHEN status='planned' THEN 'verified' ELSE status END,verified_at=? WHERE sort_run_id=? AND source_relative_path=?",(_now(),run_id,str(a['source_relative_path'])))
                c.execute("UPDATE sort_runs SET verified_file_count=verified_file_count+1,verified_bytes=verified_bytes+?,updated_at=? WHERE id=?",(int(a['expected_size_bytes']),_now(),run_id))
        with database_connection(database_path) as c: c.execute("UPDATE sort_runs SET status='moving',phase='Direkter IST→SOLL-Abgleich im SSD-Arbeitsbereich',updated_at=? WHERE id=?",(_now(),run_id))
        for f in plan['files']:
            if f['status']!='move': continue
            src=Path(f['source_absolute_path']); dst=Path(f['destination_absolute_path']); dst.parent.mkdir(parents=True,exist_ok=True)
            _move_without_overwrite(src,dst,f); moved.append((src,dst,int(f['file_id']),int(f['expected_size_bytes']),str(f['stored_sha256'])))
            if _sha256_file(dst)!=str(f['stored_sha256']): raise SortApplyError("Zielprüfung fehlgeschlagen: "+str(dst))
            with database_connection(database_path) as c:
                c.execute("UPDATE sort_operations SET status='destination_verified',moved_at=?,destination_verified_at=? WHERE sort_run_id=? AND file_id=?",(_now(),_now(),run_id,int(f['file_id'])))
                c.execute("UPDATE sort_runs SET moved_file_count=moved_file_count+1,moved_bytes=moved_bytes+?,updated_at=? WHERE id=?",(int(f['expected_size_bytes']),_now(),run_id))
        for a in plan.get('assets') or []:
            if a.get('status')!='move': continue
            src=Path(a['source_absolute_path']); dst=Path(a['destination_absolute_path']); dst.parent.mkdir(parents=True,exist_ok=True)
            _move_without_overwrite(src,dst,a); moved.append((src,dst,None,int(a['expected_size_bytes']),str(a.get('stored_sha256') or '')))
            if _sha256_file(dst)!=str(a.get('stored_sha256') or ''): raise SortApplyError("Zielprüfung der Zusatzdatei fehlgeschlagen: "+str(dst))
            with database_connection(database_path) as c:
                c.execute("UPDATE sort_asset_operations SET status='destination_verified',moved_at=?,destination_verified_at=? WHERE sort_run_id=? AND source_relative_path=?",(_now(),_now(),run_id,str(a['source_relative_path'])))
                c.execute("UPDATE sort_runs SET moved_file_count=moved_file_count+1,moved_bytes=moved_bytes+?,updated_at=? WHERE id=?",(int(a['expected_size_bytes']),_now(),run_id))
        with database_connection(database_path) as c:
            c.execute("UPDATE sort_runs SET status='finalizing',phase='Ordnerstruktur und Ereignisdokument werden abgeschlossen',updated_at=? WHERE id=?",(_now(),run_id))
        with database_connection(database_path) as c:
            c.execute('BEGIN IMMEDIATE'); now=_now()
            for f in plan['files']:
                c.execute("UPDATE files SET current_relative_path=?,current_root_kind='shared_workspace',updated_at=? WHERE id=?",(str(f['destination_relative_path']),now,int(f['file_id'])))
            for eid in plan['event_ids']:
                row = c.execute("SELECT pending_delete FROM events WHERE id=? AND job_id=?", (eid,job_id)).fetchone()
                # 0.26.9: unresolved rows at this point are no longer user
                # work.  The confirmed transaction has already moved those files
                # into canonical free stock. Persist a lightweight marker that
                # survives even when the source event itself is deleted.
                c.execute(
                    """INSERT INTO released_free_families(
                           job_id,family_id,released_start_datetime,
                           released_end_datetime,created_at,archive_origin
                       )
                       SELECT r.job_id,r.family_id,r.released_start_datetime,
                              r.released_end_datetime,?,
                              COALESCE((
                                  SELECT marker.archive_origin
                                  FROM released_free_families marker
                                  WHERE marker.job_id=r.job_id
                                    AND marker.family_id=r.family_id
                              ),0)
                       FROM event_reapply_removed_families r
                       WHERE r.event_id=? AND r.target_event_id IS NULL
                       ON CONFLICT(job_id,family_id) DO UPDATE SET
                           released_start_datetime=excluded.released_start_datetime,
                           released_end_datetime=excluded.released_end_datetime,
                           created_at=excluded.created_at,
                           archive_origin=MAX(
                               released_free_families.archive_origin,
                               excluded.archive_origin
                           )""",
                    (now,eid),
                )
                c.execute(
                    "DELETE FROM event_reapply_removed_families WHERE event_id=?",
                    (eid,),
                )
                is_pending_delete = row is not None and int(row['pending_delete'] or 0)
                if is_pending_delete:
                    c.execute(
                        "INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'event_deleted_after_reconcile','event',?,?,?)",
                        (job_id,eid,_json_details({'run_id':run_id}),now),
                    )
                    c.execute("DELETE FROM events WHERE id=? AND job_id=?", (eid,job_id))
                else:
                    c.execute("UPDATE events SET resort_required=0,status='applied',applied_at=COALESCE(applied_at,?),updated_at=? WHERE id=?",(now,now,eid))
            for a in plan.get('assets') or []:
                released_asset_id=a.get('released_archive_asset_id')
                if released_asset_id is not None:
                    c.execute("DELETE FROM released_archive_assets WHERE id=?",(int(released_asset_id),))
            receipt = {
                'anchor_event_id': anchor,
                'event_ids': plan['event_ids'],
                'file_count': len(plan['files']) + len(plan.get('assets') or []),
                'camera_file_count': len(plan['files']),
                'asset_count': len(plan.get('assets') or []),
                'verified_file_count': len(plan['files']) + len(plan.get('assets') or []),
                'move_count': int(plan['summary'].get('move_count') or 0),
                'moved_file_count': int(plan['summary'].get('move_count') or 0),
                'directory_count': len(plan['directories']),
                'created_directory_count': len(created),
                'total_size_bytes': int(plan['summary'].get('total_size_bytes') or 0),
                'verified_bytes': int(plan['summary'].get('total_size_bytes') or 0),
                'moved_bytes': sum(
                    int(f.get('expected_size_bytes') or 0)
                    for f in [*plan['files'],*(plan.get('assets') or [])] if f.get('status') == 'move'
                ),
                'source_root': str(run['source_root']),
                'target_root': str(run['target_root']),
                'plan_token': str(run['plan_token']),
                'run_kind': str(run['run_kind'] or 'reapply'),
            }
            c.commit()
        # Solange diese Nacharbeiten laufen, bleibt der Run absichtlich
        # "finalizing". Dadurch ignoriert der Strukturwächter Bibliothekars
        # eigene, noch nicht vollständig abgeschlossene Dateisystemänderung.
        metadata_error=None
        try:
            from app.event_document import build_event_document_from_db, write_event_document
            from app.obsolete_structure import cleanup_obsolete_structure
            # Read the OLD event.json before overwriting it: it is the ownership
            # proof for removed empty subevents such as a deleted "Teil B".
            cleanup_obsolete_structure(
                root,
                [src for src,_,_,_,_ in moved],
                [f['destination_absolute_path'] for f in [*plan['files'],*(plan.get('assets') or [])]],
                set(plan['event_ids']),
                managed_event_roots=plan.get('managed_event_roots') or [],
                desired_directories=[d['absolute_path'] for d in plan['directories']],
            )
            for eid in plan['event_ids']:
                document=build_event_document_from_db(database_path,workspace_path,job_id,eid)
                if document:
                    write_event_document(workspace_path,document)
        except Exception as exc:
            metadata_error=exc

        done=_now()
        with database_connection(database_path) as c:
            phase=(
                'Gemeinsamer Arbeitsbereich-Abgleich abgeschlossen'
                if metadata_error is None
                else 'Abgleich abgeschlossen; Strukturmetadaten prüfen'
            )
            c.execute(
                "UPDATE sort_runs SET status='applied',phase=?,error_message=?,completed_at=?,updated_at=? WHERE id=?",
                (phase,str(metadata_error) if metadata_error is not None else None,done,done,run_id),
            )
            # The source event may be deleted above. sort_runs.event_id still has
            # the historical ON DELETE CASCADE FK, so the run row can vanish in
            # the same transaction. This audit receipt is intentionally event-
            # independent and lets polling report the verified success.
            c.execute(
                "INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'workspace_reconciliation_applied','sort_run',?,?,?)",
                (job_id,run_id,_json_details({**receipt,'metadata_error':str(metadata_error) if metadata_error is not None else None}),done),
            )
            from app.event_mutation import mark_job_mutation_completed
            mark_job_mutation_completed(c, job_id)
            c.commit()
    except Exception as exc:
        # Roll back physical moves in reverse order. Database paths are only finalized after all moves succeed.
        for src,dst,_,expected_size,expected_sha in reversed(moved):
            try:
                _rollback_one(
                    src,
                    dst,
                    expected_size=expected_size,
                    expected_sha256=expected_sha,
                )
            except Exception:
                pass

        # Auch Ordner, die ausschließlich dieser fehlgeschlagene Lauf erzeugt
        # hat, gehören zur App-Transaktion. Bleiben sie leer zurück, würde der
        # Strukturwächter sie nach einem späteren Verwerfen fälschlich als
        # manuell angelegte Ordner sehen.
        for directory in sorted(set(created), key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
                if directory.parent.exists():
                    _fsync_directory(directory.parent)
            except OSError:
                # Nur leere, von diesem Lauf erzeugte Verzeichnisse entfernen.
                # Fremde oder inzwischen belegte Inhalte bleiben unangetastet.
                pass

        with database_connection(database_path) as c:
            c.execute("UPDATE sort_runs SET status='failed',phase='Arbeitsbereich-Abgleich fehlgeschlagen',error_message=?,updated_at=?,completed_at=? WHERE id=?",(str(exc),_now(),_now(),run_id))
        raise
