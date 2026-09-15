# Datenmodell – Verträge und belegte Regeln

Stand: 31. August 2026

Dies ist ein Arbeitsdokument. Es enthält nur Regeln, die durch vorhandenen Code, das Datenbankschema, stabile Tests oder ausdrückliche Nutzerentscheidungen belegt sind. Unsichere Punkte sind ausdrücklich als „ungeklärt“ markiert. Es gibt nichts erdichtetes wieder.

Legende:
- **Belegt:** durch Code, Schema, Migration, Stabil-Test oder Nutzer-Entscheidung gedeckt.
- **Ungeklärt:** noch nicht belegt; nicht als gültig annehmen.

## 1. Zentrale Tabellen und Beziehungen

Belegt durch `app/migrations/001_initial.sql` und Folgemigrationen:

### 1.1 `jobs` (Arbeitseinheit / SD-Kartenlauf)

- `id` (TEXT, PRIMARY KEY)
- `kind` mit CHECK: 'simulation', 'sd_import', 'archive_verification', 'hardlink_sync'
- `trigger_type`: 'manual', 'approved_sd', 'usb_key', 'system'
- `state`: 'queued', 'copying', 'verifying', 'backup_verified', 'analyzing_metadata', 'waiting_for_review', 'organizing', 'waiting_for_archive', 'archive_verified', 'deletion_approved', 'completed', 'failed', 'interrupted'
- `source_path`, `working_path`, `archive_target_path`
- Fortschritt: `progress_current`, `progress_total`, `progress_message` (Migration 002)
- `operation` (Migration 003), `source_signature`, `source_fingerprint`, `duplicate_of_job_id` (Migration 009)
- `created_at`, `updated_at`, `started_at`, `finished_at`

### 1.2 `file_families` (Medienfamilie)

Belegt durch `001_initial.sql`:

- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `job_id` → `jobs(id)`, ON DELETE CASCADE
- `family_key` (TEXT NOT NULL) – stabiler Schlüssel, z. B. aus Aufnahmezeitstempel + Geräte-ID
- `original_stem` (TEXT)
- `status`: 'detected', 'complete', 'incomplete', 'ambiguous', 'review_required'
- `selected_capture_time` (TEXT) – das ausgewählte Aufnahmezeit
- `capture_time_confidence`: 'high', 'medium', 'low', 'conflict', 'missing'
- UNIQUE(job_id, family_key)

Eine Familie gruppiert zusammengehörige Dateien (RAW, JPEG, XMP-Sidecar, Export, Video/Ableitungen). Die Zuordnung erfolgt über `files.family_id`.

### 1.3 `files` (einzelne Datei)

- `id`, `job_id` → `jobs(id)` CASCADE
- `family_id` → `file_families(id)` NULL ON DELETE SET NULL
- `original_relative_path`, `current_relative_path`
- `original_filename`, `extension`, `media_type` ('raw','jpeg','image','xmp','video','audio','other')
- `size_bytes`, `sha256_original`, `sha256_current`
- `selected_capture_time`, `selected_capture_source`, `capture_time_confidence`
- `review_status`: 'unreviewed','not_required','required','confirmed','corrected','rejected'
- `metadata_write_status`: 'not_requested','planned','confirmed','written','failed'
- `current_root_kind` (Migration 006): 'job_root','shared_workspace','camera_archive' – beschreibt in welcher Struktur sich die Datei aktuell befindet

Eine `files`-Zeile kann `family_id = NULL` haben (ON DELETE SET NULL). Ob das fachlich ein gültiger Zustand ist, ist **ungeklärt** – siehe Abschnitt 7.

### 1.4 `events` (Ereignis)

Belegt durch `001_initial.sql` + `004_event_planning.sql` + `010_event_followups.sql` + `011_event_editing.sql`:

- `id` (TEXT PRIMARY KEY, Format `EVENT_` + hex)
- `job_id` → `jobs(id)` CASCADE
- `parent_event_id` → `events(id)` CASCADE (selbstreferenziell)
- `event_level`: 'parent' oder 'child'
    - CHECK: `parent` ⇒ `parent_event_id IS NULL AND uses_time_range = 0`
    - CHECK: `child` ⇒ `parent_event_id IS NOT NULL AND uses_time_range = 1`
- `name` (TEXT NOT NULL)
- `start_datetime`, `end_datetime` (TEXT NOT NULL)
- `uses_time_range` (INTEGER 0/1)
- `folder_name` (TEXT NOT NULL) – der Zielordner im Arbeitsbereich
- `status`: 'draft', 'planned', 'applied', 'archived'
- `created_at`, `updated_at`
- `event_kind` (Migration 004): 'event' oder 'no_event'
- `preserve_day_folders` (Migration 004, INTEGER 0/1)
- `revision` (Migration 004, INTEGER ≥ 1)
- `applied_at` (Migration 004)
- `archived_at` (Migration 004)
- `linked_event_id` (Migration 010) → `events(id)` NULL ON DELETE SET NULL
- `linkage_kind` (Migration 010): 'planned_extension', 'applied_followup', 'archived_manual', oder NULL
- `notes` (Migration 011, TEXT, Default '')
- `edited_at` (Migration 011)

Ein Hauptereignis (`event_level = 'parent'`) kann maximal ein Unterereignis (`event_level = 'child'`) haben, das die Uhrzeiten trägt. Der `status` des Underereignisses wird in `database.py:update_event_definition` mit `is_applied` synchron gehalten.

### 1.5 `event_assignments` (Zuordnung Familien/Dateien zu Ereignissen)

- `event_id` → `events(id)` CASCADE
- `family_id` → `file_families(id)` CASCADE oder NULL
- `file_id` → `files(id)` CASCADE oder NULL
- CHECK: genau eines von `family_id` / `file_id` gesetzt (entweder Familie oder Datei)
- `assignment_source`: 'date_range', 'date_time_range', 'manual', 'calendar'
- UNIQUE(event_id, family_id), UNIQUE(event_id, file_id)

### 1.6 `sort_runs` / `sort_operations` (Sortierlauf)

Belegt durch `005_sort_application.sql` + `012_reapply_runs.sql`:

- `sort_runs`: Sortierlauf mit `status` ('queued','verifying','moving','finalizing','applied','rolling_back','rolled_back','failed','interrupted'), `phase`, `source_root`, `target_root`, Zähler, `plan_token`, `run_kind` (Migration 012: 'initial' oder 'reapply')
- `sort_operations`: Einzeloperation pro Datei in einem Lauf mit `sequence_number`, `file_id`, `source_relative_path`, `destination_relative_path`, `expected_size_bytes`, `expected_sha256`, `status`
- UNIQUE(sort_run_id, sequence_number), UNIQUE(sort_run_id, file_id)
- PARTIAL UNIQUE INDEX: nur ein aktiver Lauf pro Ereignis (Migration 005)

### 1.7 `archive_verifications` / `event_archive_verifications`

Belegt durch `001_initial.sql` (job-basiert) und `007_backup_archive_lifecycle.sql` (ereignisbasiert):

- `event_archive_verification_files` mit Status 'verified','missing','size_mismatch','sha256_mismatch','unsafe_path'

### 1.8 `event_ssd_releases` / `event_ssd_release_files` (SSD-Freigabe)

Belegt durch `008_ssd_release.sql`:

- `event_ssd_releases`: `job_id`, `event_id`, `verification_id` (RESTRICT), `workspace_root`, `archive_root`, Status, Zähler
- `event_ssd_release_files`: `release_id`, `file_id`, `source_relative_path`, `archive_relative_path`, `expected_size_bytes`, `expected_sha256`, Status
- UNIQUE(release_id, file_id)

### 1.9 `event_ssd_releases` und `archive_change_reviews`

- `archive_change_reviews` (Migration 004): Handverarbeitete Archivänderungen mit Status 'pending','manual_move_required','manually_moved','verified','missing','ambiguous','ignored'
- UNIQUE(event_id, file_id, expected_relative_path)

### 1.10 `audit_log`

- `job_id` NULL ON DELETE SET NULL, `action`, `entity_type`, `entity_id`, `details_json`, `created_at`
- Dient allen Modulen als Audit-Trail (belegt durch `event_reapply.py` und `database.py`)

## 2. Bedeutung von Familie, Datei und Familienmitglied

Belegt durch Schema und Code:

- **Familie** (`file_families`): Logische Sammlung zusammengehöriger Aufnahmen, identifiziert durch `family_key` innerhalb eines `job_id`. Eine Familie hat eine **selected_capture_time** (das vom Algorithmus ausgewählte Aufnahmezeit) und kann den Status 'detected','complete','incomplete','ambiguous','review_required' haben.
- **Datei** (`files`): Physikalische Datei mit relativen P相对于, Dateityp, Größe, Prüfsummen. Gehört über `family_id` zu einer Familie oder ist `NULL`.
- **Familienmitglied**: Jede Zeile in `files` mit `family_id` gesetzt ist ein Mitglied der jeweiligen Familie. Die Anzahl der Mitglieder und die Gesamtgröße werden in `event_document.py:_families_of_event` und `database.py:get_event_edit_context` als Aggregation berechnet.
- **Medienfamilie ohne Dateien**: Das Schema erlaubt `family_id = NULL` in `files` (ON DELETE SET NULL), und `files`-Zeilen können `family_id = NULL` haben. Ob eine **Familie ohne zugehörige Dateien** ein gültiger Zustand ist, ist **ungeklärt** – siehe Abschnitt 7.

## 3. Ereignisstatus: planned, applied, archived

Belegt durch `001_initial.sql` (CHECK) + `004_event_planning.sql` + Code in `database.py` + `event_document.py`:

- **planned**: Ereignis gespeichert, Struktur festgelegt, aber noch keine Dateien verschoben. `applied_at` ist NULL, `archived_at` ist NULL. Strukturell editierbar.
- **applied**: Änderungen wurden angewendet, Dateien im Arbeitsbereich verschoben. `applied_at` ist gesetzt, `archived_at` ist NULL. Strukturell editierbar (über `reapply`-Lauf). `event_document.py` baut ein `event.json` für applied-Events mit mindestens einer zugeordneten Familie.
- **archived**: Datei in Kamerabibliothek übernommen. `archived_at` ist gesetzt. Nur Name und Notizen editierbar (`database.py:update_event_definition`: „Archivierte Ereignisse können nicht mehr bearbeitet werden“).

`event_document.py` gibt NULL zurück (kein event.json), wenn das Ereignis `planned` oder `archived` ist:

```python
if str(event["status"]) != "applied" or event["archived_at"]:
    return None
```

## 4. Voraussetzungen für event.json

Belegt durch `app/event_document.py`:

- `event_level` muss 'parent' sein
- `status` muss 'applied' sein
- `archived_at` muss NULL sein
- Minimum eine zugeordnete Familie (`families` muss nicht leer sein)
- Minimum eine Datei mit `current_relative_path` (sonst `entries` leer → NULL)
- `folder_name` und `start_datetime` (Jahr) müssen vorhanden sein
- Zielpfad: `Arbeitsbereich/{JJJJ}/{folder_name}/event.json`
- `event.json` ist die **primäre** portable Beschreibung; SQLite ist der **sekundäre** Index
- Bei Abweichung: App regeneriert das Dokument aus SQLite
- `sync_event_document_after_change` schreibt neu nach jeder Änderung

## 5. Bekannte gültige Zustände (belegt)

- Ereignis mit `status = 'planned'`, mindestens eine Familie, `applied_at = NULL`
- Ereignis mit `status = 'applied'`, mindestens eine Familie, `applied_at` gesetzt, `archived_at = NULL`
- Event mit `event_kind = 'no_event'` (Ohne Ereignis)
- Unterereignis mit `uses_time_range = 1` und Uhrzeiten
- Sortierlauf mit `run_kind = 'initial'` und `run_kind = 'reapply'` (Migration 012)
- Familie mit `review_status = 'rejected'` (existiert im Schema, Verwendung in Produktion noch **ungeklärt**)
- `files.current_root_kind = 'job_root' | 'shared_workspace' | 'camera_archive'`

## 6. Bekannte ungültige Zustände (belegt)

- `event_level = 'parent'` mit `parent_event_id IS NOT NULL` (SQL CHECK)
- `event_level = 'child'` mit `parent_event_id IS NULL` (SQL CHECK)
- `event_level = 'parent'` mit `uses_time_range = 1` (SQL CHECK)
- `event_level = 'child'` mit `uses_time_range = 0` (SQL CHECK)
- `event_assignments` mit sowohl `family_id IS NULL AND file_id IS NULL` (SQL CHECK)
- `revision < 1` (SQL CHECK)
- `preserve_day_folders` außerhalb von 0/1 (SQL CHECK)
- Zwei aktive Sortierläufe für dasselbe Ereignis (partial unique index, Migration 005)
- `sort_runs.run_kind` außerhalb von 'initial'/'reapply' (Migration 012)
- `events.linkage_kind` außerhalb von 'planned_extension','applied_followup','archived_manual', NULL (Migration 010)

## 7. Noch ungeklärte fachliche Fragen

Die folgenden Punkte sind **nicht** aus Code, Schema, Tests oder Nutzer-Entscheidung belegt und werden hier ausdrücklich als ungeklärt markiert:

1. **Medienfamilie ohne Dateien**: `event_document.py` erfordert `families` nicht leer UND `entries` (Dateien) nicht leer – eine leere Familie erzeugt kein event.json. In der Anwendung ist jede Familie immer mit ≥ 1 Datei verbunden: `store_metadata_analysis` legt bei jeder Familie mindestens eine Datei an (jede Datei in `analysis.files` muss einer Familie zugeordnet sein, sonst `DatabaseError`). Die 0.15.0-Tests `test_event_document_matches_db` und `test_sync_event_document_after_change` bestätigen: eine Familie ohne Dateien liefert kein event.json (TESTFEHLER-Korrektur vom 31.08.2026). Ob eine leere Familie im Schema dennoch vorkommen kann (z. B. nach fehlerhafter Metadatenanalyse) und was dann passiert, bleibt **ungeklärt**.

2. **Bedeutung von `review_status = 'rejected'`** (0.18.0 „verworfen“): Existiert im Schema, aber es ist unklar, wie diese Werte aktuell in der Produktion gesetzt und abgefragt werden. Die 0.18.0-Regeln („verworfen → nicht verwenden“) sind eine zukünftige Fachentscheidung, nicht aktueller Code. **Ungeklärt**, bis 0.18.0 implementiert ist.

3. **Auswahlstatus für Familien** (0.18.0: ungeprüft, ausgewählt, sortiert, exportiert, verworfen, gelöscht): Kein Feld im aktuellen Schema. Geplanter Ausbau, nicht implementiert. **Ungeklärt**, bis 0.18.0 implementiert ist.

4. **`event_kind = 'no_event'` vs. fehlend**: Schema erlaubt 'event' und 'no_event' (Default 'event'). `event_structure.py` behandelt 'no_event' als „Ohne Ereignis“ mit festem Ordnername `{MM} - Ohne Ereignis`. Ob die Kombination `no_event` + `preserve_day_folders = 1` vorkommen kann (Code zwingt `preserve_day_folders = False` bei no_event), ist im Code gedeckt: `event_structure.py` setzt `preserve_day_folders = False` und `uses_time_range = False` bei no_event. **Belegt** für Preview/Payload, aber ob das auch im Speicherzustand so gehalten wird, ist **ungeklärt**.

5. **Ereignislöschung (0.17.0)**: Es existiert keine Löschfunktion im aktuellen Code. Die geplanten Zustandsabhängigkeiten (planned/applied/archived) sind eine zukünftige Fachentscheidung. **Ungeklärt**, bis 0.17.0 implementiert ist.

6. **Immich-Anbindung (0.19–0.21)**: Keine Implementierung vorhanden. Alle Details (Authentifizierung, Album-Struktur, manuelle Ausnahmen) sind noch zu klären. **Ungeklärt**, bis 0.19.0-Machbarkeitsphase abgeschlossen ist.

7. **Hardlink-Handhabung für Handyfotos (0.22.0)**: Konzept vorhanden in `PROJEKTKONTEXT.md` (Abschnitt 14.4), aber keine Implementierung. **Ungeklärt**, bis Konzeptphase abgeschlossen.

8. **Änderungszentrum (0.23.0)**: Keine Implementierung. **Ungeklärt**, bis 0.23.0 geplant.

9. **Beziehung `event_assignments` zu `files` (statt nur `file_families`)**: Schema erlaubt Zuordnung auf Dateiebene (`file_id`), aber `database.py:update_event_definition` setzt immer `family_id` und `file_id = NULL`. Ob Dateiebene-Zuordnungen in der Produktion verwendet werden, ist **ungeklärt**.

10. **`archive_change_reviews` (Migration 004)**: Tabelle existiert, aber es ist unklar, ob sie bereits in Produktion geschrieben wird. Statuswerte 'manual_move_required','manually_moved' deuten auf die 0.16.0-Funktion hin. **Ungeklärt**, bis 0.16.0 implementiert ist.

11. **`files.review_status` und `files.metadata_write_status`**: Werte existieren im Schema, aber die fachliche Semantik (besonders 'rejected' und 'confirmed') ist in den aktuellen Tests und Code-Pfaden nur teilweise belegt. Ob `review_status = 'rejected'` in der 0.14.0-Produktion bereits verwendet wird, ist **ungeklärt**.

12. **`event_ssd_releases` und `event_ssd_release_files`**: Schema vorhanden (Migration 008), Code in `app/ssd_release.py`. Die logische Sequenz (verifying → deleting → finalizing → completed) ist im Code belegt. Ob dieser Ablauf in der 0.14.0-Produktion aktiv genutzt wird, ist **ungeklärt**.

13. **`archive_change_reviews` vs. `event_ssd_releases`**: Zwei benachbarte Tabellen für verwandte Abläufe (Archivänderungen vs. SSD-Freigabe). Die genaue Abgrenzung ihrer Zuständigkeiten im Gesamtfluss ist **ungeklärt**.

## 8. Hinweise zum aktuellen Entwicklungsstand 0.15.0

Belegt durch `ARBEITSSTAND.md` und Code:

- `app/event_document.py`: Implementiert (build, write, read, sync, matches_db)
- `app/event_reapply.py`: Implementiert (prepare_reapply_sort_run)
- `app/migrations/012_reapply_runs.sql`: Angewendet
- `app/database.py:update_event_definition`: Implementiert
- `app/main.py`: Endpunkte für `api_update_event`, `api_event_reapply_plan`, `api_event_replay` vorhanden
- `app/event_structure.py`: `build_event_preview` implementiert
- **Unvollständig**: Verbindung der neuen Backendlogik mit `main.py` (ARBEITSSTAND.md)
- **Getestet**: `tests/backend/test_event_document.py` – 3 Tests (write/read, matches_db, sync_after_change) – alle bestanden (Stand 31.08.2026, nach TESTFEHLER-Korrektur: `assignment_source = 'db'` → `'date_range'`, fehlende Datei ergänzt, fehlende Felder `event_kind`/`uses_time_range`/`preserve_day_folders` im Test-Doc ergänzt)
- `tests/backend/test_replay.py`: 1 Test (prepare_replay_success) – bestanden
