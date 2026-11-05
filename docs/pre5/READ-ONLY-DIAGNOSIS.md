# pre.5 – Diagnose ohne manuelle Reparatur

Zuerst nach Anmeldung „Settings and recovery“ öffnen und Speicher-, Operations-
und Datenbankdiagnose sichern. READY beschreibt die Verwaltungsstruktur;
Operationsdiagnose nennt zusätzlich die konkret geschützten Bereiche. Eine
fehlende Mediendatei ist kein fehlendes Dataset. Fehlende Verwaltungsanker,
vertauschte Mounts und beschädigte Datenbanken verlangen dagegen ihre eigene
Wiederherstellung und bleiben UNAVAILABLE.

Die Datenbankdiagnose liest nur; das Sollschema entsteht in SQLite :memory:.
Sie setzt keine Aufträge auf completed, entfernt keine F14-Reservation und
verändert keine SQLite-/WAL-/SHM-Datei. „Repair Database“ ist kein universeller
Reset. App stoppen und einen konsistenten gemeinsamen Sicherungsstand von
Appdata, Workspace und F14-/Journalnachweisen verwenden, falls ein tatsächlicher
Datenbankverlust vorliegt. Keine zweite App mit denselben schreibbaren Mounts.

Für einen nicht aufgelösten historischen Vorgang können dessen vollständige
Reservation, Nonce, gebundene Wurzeln, Generation und verknüpfte Task-/Job- und
Hashnachweise erforderlich sein. Unbekannte Inhalte niemals löschen oder als
abgeschlossen markieren. Ein passender Dateiname allein ist kein Herkunftsbeweis.

Optional liegt `read_only_diagnosis.py` den Release-Anlagen bei. Es liest
persistente Dateien ausschließlich über O_RDONLY, öffnet SQLite nur auf zuvor
geprüften Kopien unter Container-/tmp und verweigert veränderliche oder zu große
Belege. Es importiert kein app.main und startet keine Recovery. Falls dieser
zusätzliche Bericht benötigt wird, das Skript über Standardeingabe im vorhandenen
Container als Web-UID 568 ausführen; keine persistenten Dateien installieren und
keine Rechte ändern. Das JSON enthält private Pfade; nur vertraulich teilen.

Codex hat keinen Zugriff auf den realen NAS-Bestand vorgenommen. Diese Anleitung
behauptet keine automatische Qualifikation der bislang unbekannten NAS-Belege.
