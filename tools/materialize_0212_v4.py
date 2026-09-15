from pathlib import Path

p = Path(__file__).with_name("materialize_0212.py")
source = p.read_text(encoding="utf-8")
source = source.replace("'''        const options = targets.map(t => {", "'''      const options = targets.map(t => {")
source = source.replace(
    '            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN (SELECT id FROM events WHERE parent_event_id = ?)",\n',
    '            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN "\n            "(SELECT id FROM events WHERE parent_event_id = ?)",\n',
)
source = source.replace(
    '''        connection.executemany(\n            "INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at) VALUES (?, ?, NULL, 'date_time_range', ?)",\n            [(assignment_event_id, family_id, now) for family_id in selected_ids],\n        )\n''',
    '''        connection.executemany(\n            """\n            INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at)\n            VALUES (?, ?, NULL, 'manual', ?)\n            """,\n            [(assignment_event_id, family_id, now) for family_id in selected_ids],\n        )\n''',
)
exec(compile(source, str(p), "exec"), {"__file__": str(p), "__name__": "__main__"})
