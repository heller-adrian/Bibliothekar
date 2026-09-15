from pathlib import Path

p = Path(__file__).with_name("materialize_archive_structure_0212.py")
source = p.read_text(encoding="utf-8")
source = source.replace(
    "'''            target_event_id=body.get(\"target_event_id\"),\n            workspace_path=WORKSPACE_PATH,\n        )\n''',",
    "'''            target_event_id=payload.get(\"target_event_id\"),\n            workspace_path=WORKSPACE_PATH,\n        )\n''',",
).replace(
    "'''            target_event_id=body.get(\"target_event_id\"),\n            target_child_event_id=body.get(\"target_child_event_id\"),\n            new_child_start=body.get(\"new_child_start\"),\n            new_child_end=body.get(\"new_child_end\"),\n            workspace_path=WORKSPACE_PATH,\n        )\n''',",
    "'''            target_event_id=payload.get(\"target_event_id\"),\n            target_child_event_id=payload.get(\"target_child_event_id\"),\n            new_child_start=payload.get(\"new_child_start\"),\n            new_child_end=payload.get(\"new_child_end\"),\n            workspace_path=WORKSPACE_PATH,\n        )\n''',",
)
exec(compile(source, str(p), "exec"), {"__file__": str(p), "__name__": "__main__"})
