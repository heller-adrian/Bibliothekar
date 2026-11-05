# Noch fehlende reale Einzeldateinachweise

Der vorliegende Auftrag greift nicht auf TrueNAS zu. Die folgende rein lesende Diagnose ist **nicht ausgeführt** und nur erforderlich, wenn die tatsächlichen vier Kollisionsdateien unabhängig klassifiziert werden sollen. Keine pauschale Dublettenannahme aus Namen. Die16 synthetischen Gegenstücke werden im Linux-Testartefakt dokumentiert, ersetzen die tatsächlichen NAS-Daten nicht.

Nach Bestätigung des richtigen App-Containers kann in dessen Shell als Web-UID568 der folgende Pythoncode ausgeführt und die Ausgabe bereitgestellt werden. Den Datenbankpfad zuerst mit der eigenen Konfiguration abgleichen; bei anderem Pfad nicht raten. Der Code öffnet ausschließlich die bestehende SQLite mit mode=ro, erzeugt keine neue Datenbank und führt keine Reparatur aus. Bei Fehler abbrechen.

```python
from pathlib import Path
import sqlite3, json
p = Path('/appdata/database/kamera.sqlite3')
assert p.is_file() and not p.is_symlink(), str(p)
c = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
c.row_factory = sqlite3.Row
c.execute('PRAGMA query_only=ON')
queries = {
 'files': '''SELECT f.id,f.job_id,f.family_id,f.original_relative_path,
 f.current_relative_path,f.current_root_kind,f.original_filename,f.size_bytes,
 f.sha256_original,f.sha256_current,ff.selected_capture_time,j.operation,j.state
 FROM files f JOIN file_families ff ON ff.id=f.family_id
 JOIN jobs j ON j.id=f.job_id
 WHERE substr(ff.selected_capture_time,1,10) BETWEEN '2026-07-19' AND '2026-07-24'
 ORDER BY ff.selected_capture_time,f.id''',
 'events': '''SELECT id,job_id,parent_event_id,event_kind,status,folder_name,
 start_datetime,end_datetime,resort_required FROM events
 WHERE start_datetime<'2026-07-25' AND end_datetime>='2026-07-19' ORDER BY id''',
 'assignments': 'SELECT event_id,family_id,file_id,assignment_source FROM event_assignments ORDER BY event_id,family_id,file_id',
 'mutations': '''SELECT id,job_id,anchor_event_id,status,original_state_json,
 target_state_json FROM event_mutations WHERE status!='completed' ORDER BY created_at''',
 'notices': '''SELECT id,file_id,kind,status,relative_path,details_json
 FROM external_change_notices WHERE kind='placement_conflict' ORDER BY id''',
}
for key,sql in queries.items():
 print(json.dumps({key:[dict(r) for r in c.execute(sql)]},ensure_ascii=False))
c.close()
```

Damit lassen sich Datei-/Familien-IDs, Ist-/Sollpfade, Original-/aktuelle Hashes, Herkunftsauftrag und Mutation abgleichen. Tatsächliche Bytegleichheit und physische Identität müssen anschließend ausschließlich an den dadurch konkret belegten Pfaden lesend geprüft werden, einschließlich lstat, Symlink-/Hardlinkeigenschaften und SHA256. Keine Namenssuche als Eigentumsnachweis und keine Schreibaktion auf Archiven. Diese Diagnose ist kein automatisches Reparaturrezept.
