from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path, old, new):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    if new in s:
        return
    if old not in s:
        raise SystemExit(f'missing anchor in {path}: {old[:100]!r}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')

# Capture old canonical event definition before structural edit.
replace_once('app/database.py', '''        old_assigned_ids = {int(row["family_id"]) for row in old_assigned_rows}

        placeholders = ",".join("?" for _ in requested_ids)
''', '''        old_assigned_ids = {int(row["family_id"]) for row in old_assigned_rows}

        # Preserve the old canonical time definition so every released family
        # can carry the exact free segment that produced the reassignment task.
        # This avoids reconstructing time truth from min/max capture timestamps.
        if str(event["event_kind"] or "event") == "no_event":
            old_definition_rows = connection.execute(
                "SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            old_definition_ranges = [(str(r["start_datetime"])[:19], str(r["end_datetime"])[:19]) for r in old_definition_rows]
        else:
            old_definition_rows = connection.execute(
                "SELECT start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            old_definition_ranges = (
                [(str(r["start_datetime"])[:19], str(r["end_datetime"])[:19]) for r in old_definition_rows]
                if old_definition_rows else
                [(str(event["start_datetime"])[:19], str(event["end_datetime"])[:19])]
            )

        placeholders = ",".join("?" for _ in requested_ids)
''')

# Compute exact released pieces from old minus new definitions.
replace_once('app/database.py', '''        if cascade_confirmed and str(preview.get("event_kind") or "event") == "event":
            from app.event_timeline import apply_cascade_for_interval
''', '''        if event_kind == "no_event":
            new_definition_ranges = [(seg["start_datetime"], seg["end_datetime"]) for seg in no_event_segments]
        elif multi_segments:
            new_definition_ranges = [
                (f"{start_date}T{str(seg.get('start_time') or '00:00')}:00",
                 f"{end_date}T{str(seg.get('end_time') or '23:59')}:59")
                for seg in multi_segments
            ]
        else:
            new_definition_ranges = [(assignment_start, assignment_end)]
        from app.released_ranges import subtract_intervals, split_intervals_by_day
        released_definition_ranges = split_intervals_by_day(
            subtract_intervals(old_definition_ranges, new_definition_ranges)
        )

        if cascade_confirmed and str(preview.get("event_kind") or "event") == "event":
            from app.event_timeline import apply_cascade_for_interval
''')

# Store exact released range with each pending row.
replace_once('app/database.py', '''        if removed_ids:
            connection.executemany(
                """INSERT INTO event_reapply_removed_families
                   (event_id, job_id, family_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                [(event_id, job_id, family_id, now) for family_id in removed_ids],
            )
''', '''        if removed_ids:
            rp = ",".join("?" for _ in removed_ids)
            removed_capture_rows = connection.execute(
                f"SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN ({rp})",
                (job_id,*removed_ids),
            ).fetchall()
            from app.released_ranges import range_for_capture
            released_by_family = {
                int(r["id"]): range_for_capture(str(r["selected_capture_time"] or "")[:19], released_definition_ranges)
                for r in removed_capture_rows
            }
            connection.executemany(
                """INSERT INTO event_reapply_removed_families
                   (event_id, job_id, family_id, created_at, released_start_datetime, released_end_datetime)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(
                    event_id, job_id, family_id, now,
                    released_by_family.get(family_id)[0] if released_by_family.get(family_id) else None,
                    released_by_family.get(family_id)[1] if released_by_family.get(family_id) else None,
                ) for family_id in removed_ids],
            )
''')

# Applied deletion releases the entire old definition; keep exact pieces.
replace_once('app/database.py', '''        if status == "applied" and event["applied_at"] is not None and event["archived_at"] is None:
            if int(event["resort_required"] or 0):
''', '''        if status == "applied" and event["applied_at"] is not None and event["archived_at"] is None:
            if int(event["resort_required"] or 0):
''')
replace_once('app/database.py', '''            connection.execute("DELETE FROM event_reapply_removed_families WHERE event_id=?", (event_id,))
            if family_ids:
                connection.executemany(
                    """INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at)
                       VALUES (?,?,?,?)""",
                    [(event_id, job_id, fid, now) for fid in family_ids],
                )
''', '''            connection.execute("DELETE FROM event_reapply_removed_families WHERE event_id=?", (event_id,))
            if family_ids:
                if str(event["event_kind"] or "event") == "no_event":
                    delete_definition_rows = connection.execute(
                        "SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                        (event_id,),
                    ).fetchall()
                else:
                    delete_definition_rows = connection.execute(
                        "SELECT start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                        (event_id,),
                    ).fetchall()
                delete_ranges = (
                    [(str(r["start_datetime"])[:19],str(r["end_datetime"])[:19]) for r in delete_definition_rows]
                    if delete_definition_rows else
                    [(str(event["start_datetime"])[:19],str(event["end_datetime"])[:19])]
                )
                from app.released_ranges import split_intervals_by_day, range_for_capture
                delete_ranges = split_intervals_by_day(delete_ranges)
                fp = ",".join("?" for _ in family_ids)
                delete_capture_rows = connection.execute(
                    f"SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN ({fp})",
                    (job_id,*family_ids),
                ).fetchall()
                delete_range_by_family = {
                    int(r["id"]): range_for_capture(str(r["selected_capture_time"] or "")[:19], delete_ranges)
                    for r in delete_capture_rows
                }
                connection.executemany(
                    """INSERT INTO event_reapply_removed_families(
                           event_id,job_id,family_id,created_at,released_start_datetime,released_end_datetime)
                       VALUES (?,?,?,?,?,?)""",
                    [(
                        event_id,job_id,fid,now,
                        delete_range_by_family.get(fid)[0] if delete_range_by_family.get(fid) else None,
                        delete_range_by_family.get(fid)[1] if delete_range_by_family.get(fid) else None,
                    ) for fid in family_ids],
                )
''')

# Reassignment listing returns atomic exact segments based on persisted released ranges.
replace_once('app/event_reassignment.py', '''    # Canonical released ranges come from the source definition, never
    # from family min/max capture times. This is especially important after
    # deleting or shortening a timed event.
    pending_days = sorted({str(r["selected_capture_time"] or "")[:10] for r in rows if r["selected_capture_time"]})
    reassignment_time_ranges: dict[str, dict[str, str]] = {}
    with database_connection(database_path) as connection:
        if str(source["event_kind"]) == "no_event":
            defined = connection.execute(
                "SELECT day_key,start_time,end_time FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            for seg in defined:
                day=str(seg["day_key"] or "")
                if day in pending_days:
                    reassignment_time_ranges[day]={"start_time":str(seg["start_time"]),"end_time":str(seg["end_time"])}
        else:
            children = connection.execute(
                "SELECT start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            definitions = list(children) if children else [source]
            for day in pending_days:
                day_start=f"{day}T00:00:00"; day_end=f"{day}T23:59:59"
                pieces=[]
                for definition in definitions:
                    a=max(day_start,str(definition["start_datetime"] or "")[:19])
                    b=min(day_end,str(definition["end_datetime"] or "")[:19])
                    if a <= b:
                        pieces.append((a,b))
                if pieces:
                    reassignment_time_ranges[day]={"start_time":min(a for a,_ in pieces)[11:16],"end_time":max(b for _,b in pieces)[11:16]}
''', '''    # 0.21.2: released time pieces are persisted when the source definition
    # changes. They are the canonical reassignment units; family capture times
    # decide membership only, never the displayed/created range boundaries.
    segment_groups: dict[tuple[str,str], list[Any]] = {}
    fallback_by_day: dict[str,list[Any]] = {}
    for row in rows:
        a=str(row["released_start_datetime"] or "")[:19]
        b=str(row["released_end_datetime"] or "")[:19]
        if a and b:
            segment_groups.setdefault((a,b),[]).append(row)
        else:
            day=str(row["selected_capture_time"] or "")[:10]
            fallback_by_day.setdefault(day,[]).append(row)
    reassignment_segments=[]
    for (a,b),items in sorted(segment_groups.items()):
        reassignment_segments.append({
            "segment_key": f"{a}/{b}", "day_key": a[:10],
            "start_time": a[11:16], "end_time": b[11:16],
            "start_datetime": a, "end_datetime": b,
            "family_ids": [int(item["family_id"]) for item in items],
            "family_count": len(items),
            "file_count": sum(int(item["file_count"] or 0) for item in items),
        })
    for day,items in sorted(fallback_by_day.items()):
        captures=[str(item["selected_capture_time"] or "")[:19] for item in items if item["selected_capture_time"]]
        if captures:
            a=min(captures); b=max(captures)
            reassignment_segments.append({
                "segment_key": f"fallback:{day}", "day_key": day,
                "start_time": a[11:16], "end_time": b[11:16],
                "start_datetime": a, "end_datetime": b,
                "family_ids": [int(item["family_id"]) for item in items],
                "family_count": len(items),
                "file_count": sum(int(item["file_count"] or 0) for item in items),
                "fallback": True,
            })
    reassignment_time_ranges = {
        seg["day_key"]: {"start_time":seg["start_time"],"end_time":seg["end_time"]}
        for seg in reassignment_segments
    }
''')
replace_once('app/event_reassignment.py', '''        "pending_months": pending_months,
        "reassignment_time_ranges": reassignment_time_ranges,
    }
''', '''        "pending_months": pending_months,
        "reassignment_time_ranges": reassignment_time_ranges,
        "reassignment_segments": reassignment_segments,
    }
''')

print('reassignment range persistence materialized')
