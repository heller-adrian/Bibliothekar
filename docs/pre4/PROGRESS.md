# pre.4 – Arbeitsstand (nicht abgenommen)

Basis: veröffentlichtes v1.0.0-pre.3, f18b377a5d3a6a04aab0d1b51ddd1d4c33dc9793.
Branch: codex/pre4-storage-operation-separation. Keine Veröffentlichung.
Budget dieser Phase: Wochenverbrauch 75 → maximal 80 Prozent.

## Umsetzung im Entwurf

- Zwei globale Zustände READY/UNAVAILABLE; Setupfortschritt separat.
- Zentrale Operationsdiagnose und konservative Workspace-Schreibsperre bei
  unbekannten Auswirkungen; authentifizierte Katalog-Leseansicht bleibt erreichbar.
- Startup unterscheidet technische Schema-/DB-/Strukturfehler von fachlicher Recovery.
- Dynamische Dateipfade sind keine globalen Anker. General und Batch Correction
  werden als notwendige Verwaltungsanker aufgenommen; bestehende Namen bleiben.
- Vor unbekannten Altoperationen keine gewöhnliche Startup-Migration/Backfill;
  ursprüngliche F14-, Hash- und Journalprüfungen bleiben bestehen.

## Nachgewiesener Codepfad / Diagnosegrenze

General-UI → POST /api/metadata-correction/general/reintegrate →
metadata_general_import → result_json.organization.imported_source_files →
verifizierte Übergabe und Quellbereinigung. Die Recovery erwartet diesen Weg.
metadata_transfer_admission_missing_or_ambiguous bedeutet null oder mehrere passende
Nachweise. Der reale Fuji-Importweg und die übrigen NAS-Operationen sind damit noch
nicht unabhängig belegt. Keine Zielsuche nur nach Name/Hash und keine NAS-Änderung.

## Noch offen / nicht installationsreif

- Gezielte Linux-Vertragstests neu angelegt, Ausführung ausstehend.
- Vollständiger echter API-/Containerablauf und historische Regressionen ausstehend.
- Explizite Fortsetzung qualifizierter Bibliotheks-Reintegration und Folder-Import-
  Altoperationen bei aktiver Operationssperre noch zu integrieren. Gegenwärtig
  konservativ gesperrt; keine Behauptung unveränderter Recovery-Funktionalität.
- DB-Integritätsprüfung, Kontrollhistorienverlust und durchgängiger Schutz gegen
  TOCTOU-/Parallelitätsfälle noch abschließend zu prüfen.
- Schreibsperre bisher Workspace-weit; keine nachgewiesene feinere Isolation.
- Keine native TrueNAS-/NFSv4-, physische SD/USB- oder echte DNG-1.7-Abnahme.

Nächster Schritt: kleinen Self-Hosted-Linux-Vertragstest auswerten, danach gezielte
Recovery-Integration und API-/Containerabnahme. Keine vollständige CI-Matrix starten,
bevor diese gezielten Prüfungen bestanden sind.
