# Bibliothekar pre.5 – Fortsetzung

Stand: 2026-10-30. Branch `codex/pre5-operation-recovery`.
Ausgangspunkt: veröffentlichtes `v1.0.0-pre.4`, Commit
`adcc2aa9a444042440ff764be10fe1e42191904d`.

Beide vollständigen Auftragsunterlagen vom 30.10. gelesen. Keine NAS-Zugriffe.
Budget zunächst ungefähr 10–15 Wochenprozentpunkte; spätestens bei 80 % des
Fünf-Stunden-Fensters reproduzierbaren Zwischenstand sichern. Anfang: beide
Anzeigen 0 %, nächster Check: fünf Stunden 6 %, Woche 1 %.

## Befund / nächste Schritte

- GET Workspace ruft schreibende `compatibility_workspace_root()` auf.
- `operation_health` sperrt nach jeder verwaisten Reservation den gesamten
  Workspace. Unbekannte Wirkungen müssen weiter geschützt bleiben, bekannte
  unabhängige Bereiche benötigen eine belastbare Freigabe.
- Erster Inventory-Abbruch auf TrueNAS bislang nicht bewiesen. Zuerst drei
  Dateiwege getrennt und kombiniert gegen unveränderten Release-Code testen.
- Noch keine pre.5-Anwendungsänderung oder Veröffentlichung. Vorhandene
  unversionierte Datei `qa/rc14.zip` gehört nicht zu diesem Auftrag.

Nächster Schritt: Linux-Reproduktion mit eng begrenztem Self-Hosted-Workflow;
danach Architekturkorrektur, gezielte und vollständige fachliche Abnahme.
Veröffentlichung erst nach allen verbindlichen bestandenen Prüfungen.
