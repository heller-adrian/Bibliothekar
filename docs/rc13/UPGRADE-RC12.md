# Sichere Aktualisierung der gesperrten RC12-Installation

Diese Anleitung gilt für dieselbe bestehende RC12-Instanz und dieselben Mounts.
Die Linux-/Containerabnahme ist bestanden. Das Release enthält den geprüften
Image-Digest und Pullbeleg; native Abnahme folgt separat.

1. Bibliothekar in TrueNAS **stoppen**. Keine zweite Instanz mit denselben
   beschreibbaren Appdaten oder demselben Workspace starten.
2. Den vollständigen Appdatenstamm und den Workspace im gestoppten Zustand
   konsistent sichern, vorzugsweise über TrueNAS-Dataset-Snapshots. Bei separaten
   Datasets alle betroffenen Datasets im selben gestoppten Zeitfenster sichern.
   Die Sicherung enthält SQLite einschließlich vorhandener WAL-/SHM-Dateien,
   Konfiguration, Registry, F14, Journale und Retention. Nicht einzelne
   Datenbankdateien aus dem laufenden Container kopieren.
3. Vorhandene App-Einstellungen dokumentieren. Appdaten-, Workspace- und
   Archivmounts einschließlich RO-Einstellungen identisch beibehalten.
   Keine ACL-, Eigentümer-, Ordnernamen- oder Datenbankkorrektur ist für diesen
   Quellenfamilienfehler erforderlich.
4. Nach Veröffentlichung ausschließlich das im RC13-Release ausgewiesene
   geprüfte Image verwenden. In der Custom-App das Image aktualisieren und
   dieselbe Instanz starten. Das bestehende GHCR-Paket ist öffentlich abrufbar. Bei einer Zugriffssperre
   vorhandene TrueNAS-Registry-Zugangsdaten prüfen; das Repository bleibt privat.
5. Anmelden. Der Startabgleich prüft ursprüngliche Registry-Mitglieder und
   passende bestätigte Löschbelege automatisch. Er schreibt keine verkürzte
   Herkunft und erfordert keinen SQL-Eingriff. Wiederholte Starts sind zulässig.
6. Prüfen: richtige Version, vorhandene Bibliothek, erhaltene RAW-Datei,
   passender aktueller Bestand, unveränderte Archive. Anschließend zweite
   Bibliothek mit eigenem RO-Archiv anlegen und beide nach Neustart prüfen.
7. Bei `source_inventory_conflict` die vollständige Diagnose und Logs sichern.
   Fehlende Belege oder abweichende ursprüngliche Hashes/Größen werden weiterhin
   gesperrt. Nicht durch Löschung von F14/Audit/Registry freigeben.

## Rückkehrgrenze

Ein bloßer Rückwechsel zu RC12 kann denselben Quellfamilienfehler erneut auslösen
und versteht die RC13-Projektionsnachweise nicht. Nach Arbeiten mit RC13 nur auf
Basis der vollständig zusammengehörigen, vorher gesicherten Appdaten und des
passenden Workspace zurückkehren. Vorher erneut stoppen und den aktuellen Stand
sichern. Keinen alten Katalog mit neuem Workspace oder neuer Registry mischen.
RC13 ändert das F14-Format 3 von RC12 nicht.

## Praktische RC13-Abnahme auf TrueNAS

- Vorhandene gesperrte Installation ohne Clean Slate starten.
- Deutsch/Englisch und Mobil/Desktop prüfen, insbesondere Archivänderung,
  Rückänderung, tatsächliche Pfade und mobile Statusanzeige.
- Unbekannte Papierkorbdatei: Wiederherstellung muss weiterhin ablehnen;
  anschließendes ausdrücklich bestätigtes Leeren muss funktionieren.
- In einer isolierten Testbibliothek einzelne Dateilöschung zweimal vollständig
  abgleichen, dann neu starten; die ursprüngliche Quellenfamilie bleibt erhalten.
- Originalordner-Reparatur und ausdrücklich bestätigten Ersatz mit ausschließlich
  synthetischen Testdaten erneut abnehmen.

Die separate Erstinstallations-/ACL-Abnahme ist ausdrücklich nicht enthalten.
