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

- Erster Linux-Vertragstest erfolgreich: 40979277494, Commit b4c485d23d6f944d6a50e39e95232547fc4dcfc2; neun Tests bestanden.
  Artefakt 12944092160, ZIP-SHA256 a40457a54966d931ace07f10b832f6944f257c4f8c2cef9729064957457faf85.
  Zwei zusätzliche reale Fachfunktions-Regressionsfälle (DNG-Verweigerung, JPEG-Übernahme mit zweifachem Startup) ergänzt; deren Prüfung folgt.
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

## Fortsetzung (zusätzlich freigegeben bis 90 %)

- Elf gezielte Tests bestanden auf 67bc739312e688110d2f66870efa54c8bdf4b833,
  Lauf 40979424380. Artefakt 12943833279,
  SHA256 1528585f72117e9b425d89ea375b707707852d841c8330c4f25a6ebea5303cf6.
- Erweiterter Lauf 40980313558: 22 bestanden, drei Reparaturfälle fehlgeschlagen.
  Ursache: zusätzliche Ankerdiagnosen waren nicht mit der bestehenden strikten
  Ersatzqualifikation abgestimmt. Diese Integration wird korrigiert; keine Freigabe.
- Pauschale Ersatzoberfläche entfernt. Normale Seiten bleiben erreichbar;
  fachlich gesperrte GET-Anfragen lesen SQLite über mode=ro/query_only.
- Technischer Startup-Lease endet vor fachlicher Recovery. Ein späterer
  Fachfehler erzeugt dadurch keinen zusätzlichen technischen Startup-Altvorgang.
- Zusätzliche Schreibbarrieren für Datenbank/Registry, explizit qualifizierte
  Original-Recovery, Verwaltungsunteranker und Integritätsprüfung in Arbeit.

- Lauf 40981050859, Anwendung 78d453a3: 25 neue Vertragstests bestanden;
  historische Auswahl 141 bestanden / 7 fehlgeschlagen (345,31 s).
  Vier falsch verschachtelte Test-Recoveries auf die echte physische Original-
  Recovery umgestellt; frühere globale Startup-Erwartungen durch READY plus
  nachgewiesene Schreibsperre ersetzt. Unfertige technische Einrichtung meldet
  bis zum Abschluss UNAVAILABLE. Lauf auf 08d177eb prüft diese Änderungen.
- Chromium-Prüfung der tatsächlichen, authentifizierten normalen Anwendung
  (DE/EN, mobil/Desktop) im isolierten Container ergänzt, noch ausstehend.

- Lauf 40982068050 auf 08d177eb: 30 Vertragstests und alle 148 historischen
  Regressionen bestanden. Reale Containerkorrektur und General-Import gelangen
  bis zur Neustartkontrolle; deren Testprozess-Auswahl erfasste sich selbst.
  Testhilfe korrigiert (exakte argv-Prüfung statt Teilstrings); keine Lockerung
  fachlicher Prüfungen. Abnahme war dadurch insgesamt fehlgeschlagen.
- Lauf 40983043058 auf 5d13dc2d: 32 Vertragsfälle bestanden, ein neuer
  technischer Wiederanlauf-Nachweis fehlte nach Abschluss (generische finished-
  Receipts sind absichtlich flüchtig). Additiven dauerhaften technischen
  Abschlussbeleg ergänzt. Historische Auswahl und Container wurden korrekt
  noch nicht gestartet. Verifikation des neuen Belegs folgt.

## Gezielte Nachprüfung von f88db90b (zusätzlich freigegeben bis 92 %)

Lauf 40984782546: 36 Vertragsfälle und 148 historische Regressionen bestanden;
Containerstufe scheiterte an der Shutdown-Logprüfung. Artefakt 12946942630
(b54d1adf65c8832934b92e7bcab2ddf60b4012b79f760e4adb05b37c16b7b755)
enthält tatsächlich „Application shutdown complete“ und „Finished server process“.
Die Testhilfe hatte bei docker logs nur stdout ausgewertet; Uvicorn schreibt stderr.
Beide Streams werden nun geprüft, einschließlich Traceback-Ausschluss und Exitstatus.

/healthz rief ohne Bibliothekskontext get_health auf. Nach Onboarding prüfte es
somit den nicht angelegten Bootstrap-Arbeitsplatz statt der registrierten Struktur.
Die öffentliche Probe nutzt jetzt die vollständige strukturelle Storage-Prüfung
und technische Startup-Fehler. Fachliche Schreibsperren bleiben separat aktiv.
Neue Regression: gesund und fachlich gesperrt → 200; technischer Fehler/fehlender
Trash → 503. Reale Probeprüfungen in der Containerabnahme ergänzt.
