from pathlib import Path

p = Path(__file__).with_name("materialize_0212.py")
source = p.read_text(encoding="utf-8")
source = source.replace(
    "'''        const options = targets.map(t => {\n        const kind = t.event_kind === \\\"no_event\\\" ? \\\"Ohne Ereignis\\\" : \\\"Ereignis\\\";",
    "'''      const options = targets.map(t => {\n        const kind = t.event_kind === \\\"no_event\\\" ? \\\"Ohne Ereignis\\\" : \\\"Ereignis\\\";",
)
exec(compile(source, str(p), "exec"), {"__file__": str(p), "__name__": "__main__"})
