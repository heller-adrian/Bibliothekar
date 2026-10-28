# RC14 Screenshotmatrix 01–17

Alle 17 Originalbilder wurden einzeln vollständig gesichtet und mit dem Code
abgeglichen. Linux-Gesamtabnahme und finale Statusfreigabe stehen noch aus.
„Lokal PASS“ bezeichnet jeweils nur den genannten isolierten Test.

| Bild | Befund / Entscheidung | Codestelle | Nachweis / Status |
|---|---|---|---|
| 01 | freie Familien EN, Zahl dynamisch | ui_rc14.PATTERNS | Chromium rc14 cases 01, EN/DE/EN; lokal PASS |
| 02 | fehlgeschlagener Job EN | ui_rc14.TRANSLATIONS | Chromium 02; lokal PASS |
| 03 | gleiche Fehlermeldung mobil | ui_rc14.TRANSLATIONS | Chromium 03, 320/390/1280 px; lokal PASS |
| 04 | IST/SOLL-Phase ohne Gerätebehauptung EN | ui_rc14.TRANSLATIONS | Chromium 04; lokal PASS |
| 05 | Phantomfamilien und Open Tasks | inventory_availability, database.list_global_tasks, global_workspace | test_tasks_exclude_failed_and_missing_physical_families, Größenfixture; lokale Tests PASS; Container ausstehend |
| 06 | Release-/Metadatenbadges angleichen | workspace_ui.renderDays / day-statuses | tatsächlicher Renderer in Chromium; gleiche Schrift/Padding, kein Überlauf bei 320/390/1280 px; lokal PASS |
| 07 | manuell umbenannter Workspace bleibt blockiert | main._new_workspace_name, unveränderte F14-Prüfung | Namens-/Traversal-/Kollisionstests und HTTP-Identitätsgegenprobe; lokal PASS |
| 08 | Bibliotheksliste bei Speicherfehler weiter lesbar | main.library_context_middleware GET /api/libraries | test_library_listing_survives_storage_fault_without_enabling_mutation; lokal PASS |
| 09 | abgenommene Ordnerreparatur erhalten | storage_replacement funktional unverändert | vollständige historische Backend-/Containerabnahme ausstehend |
| 10 | gelöschtes Ereignis EN, dynamischer Name/Zahl | ui_rc14.PATTERNS | Chromium 10; lokal PASS |
| 11 | Technical ID, Prüfhinweis, Business, Remove library | ui_shell, ui_rc14, library_retirement | Chromium 11; Lebenszyklus-Gegenproben, Archive erhalten; lokal PASS; echter Container ausstehend |
| 12 | relativer Workspacepfad verständlich EN | ui_rc14.TRANSLATIONS, bestehende Pfadprüfung | Chromium 12; Traversaltests; lokal PASS |
| 13 | fehlender Pfad ohne irreführende main-Klausel, Overlap EN | workspace_layout, ui_rc14.PATTERNS | Chromium 07/13; bisherige Overlapguards bleiben; lokale Darstellung PASS |
| 14 | Staging erklären, unabhängige Registrierung nur mit Nachweis | import_recovery.retained_staging_is_qualified, root_operations.mutate | Chromium 14; Recoverygegenproben lokal PASS; vollständige Ressourcenabnahme ausstehend |
| 15 | Resttext neben dynamischem Arbeitsordner EN | ui_rc14.TRANSLATIONS | Chromium 15, bisherige 44 RC13-Dialogfälle lokal PASS |
| 16 | Kalenderhüllen nicht pauschal löschen | library_retirement.remove | strikt nichtleer blockieren, leere eigene Hülle stehenlassen; Lebenszyklustests lokal PASS |
| 17 | Wiederherstellung abgeschlossen EN | ui_rc14.TRANSLATIONS | Chromium 17; lokal PASS |

Chromium nutzt das reale I18n-Modul und den realen renderDays-Code. Dynamische
Pfade und Ereignisnamen werden unverändert als Daten eingesetzt. 147 RC14-
Prüffälle pro vollständigem Browserlauf, daneben 44 bestehende RC13-Fälle;
keine Addition wiederholter Läufe. Das ist keine native iPhone-/TrueNAS-Abnahme.
