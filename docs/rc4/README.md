# RC4 – technischer Kandidat, noch nicht veröffentlicht

Version: `1.0.0-rc.4`. Ausgangsstand: `2e124fc504b4349ede9b38e958c509f048fcd02c`.

Enthalten: RC3-Nachbesserungen, persistente SD-Hintergrundprüfung, mobile Vorschau, EN/DE-Korrekturen, kompakte Archivhistorie, verifizierte Ereignistitel und ausdrücklich bestätigter Einzelabschluss fehlgeschlagener Papierkorb-Restores. Worker und GET schließen fehlgeschlagene Restores nicht automatisch ab.

Die RC4-Endabnahme führt einmal die vollständige isolierte Linux-Backend-Suite aus. Nur bei Erfolg folgen linux/amd64-Build, SHA-256-Abgleich aller App-Dateien und frischer Onboarding-Smoke mit sechs Seiten, JS/CSS, Authentifizierung, Web-UID/GID 568:568 und SQLite-Prüfung. Keine Veröffentlichung oder Installation durch diesen Workflow.

## Manuelle TrueNAS-Abnahme nach Bereitstellungsfreigabe

- SD: „Erneut sichern“ auf vollständig gesicherter Karte; Hintergrundfortschritt auch nach Seitenwechsel/Neustart; Abschluss ohne leeren Import. Fehlende Kopie separat mit synthetischen Daten prüfen.
- Papierkorb: exakt `TRASH_IMPORT_20261023_205446_538D89094806` prüfen, nur diesen fehlgeschlagenen Auftrag ausdrücklich sicher abbrechen. Originale und unabhängige Rückfallkopien samt Hashes prüfen, neu starten, dann reguläre Löschung mit weiterhin erhaltenen Rückfallkopien testen. Konflikte bleiben gesperrt; keine Journalentfernung. Details: [Einzelabschluss](trash-failure-finalization.md).
- Alter Titel: Bibliothek `main`, Ereignis `EVENT_44A83046287D4403A39E02382E0EADCE`, Dokumenthash `28107680f7ea94daa2ff874b95b9434ce2e74baf4e20776d88ca82b5244f3074` und Revision prüfen. Neue manuelle Archivänderung nur für Titel `Test 6`, unveränderter Ordner `07-21 - Test 6`; neue event.json ausdrücklich einsetzen und verifizieren, erst danach Katalogabschluss. Alte Journale behalten. Details: [NAS-Altzustände](nas-altzustaende.md).
- Smartphone/EN/DE: Vorschau geplant/angewendet, kompakte Archivhistorie und SD-Meldungen kontrollieren. Papierkorb-Fortschrittsanzeige B12 bleibt zurückgestellt.

## Plattformgrenzen

Das Compose-Beispiel ist eine Vorlage; weder ein veröffentlichtes RC4-Image noch eine automatische Dataset-/ACL-Konfiguration wird zugesichert. Die bestehende manuelle NFSv4-ACL-Voraussetzung für den geschützten SD-Mountbereich bleibt erforderlich: Web-UID/GID 568:568 darf lesen und durchqueren, nicht schreiben; Helper-Eigentum und tatsächliches read-only bleiben zu prüfen. Reale TrueNAS-ACLs, Mountnamespace, Hotplug und Neustart sind gesondert abzunehmen. Keine pauschalen Rechteänderungen.

F13: letzte externe Archivänderung zwischen Prüfung und SSD-Unlink sowie mmap-Erkennungsgrenze bleiben akzeptiertes Restrisiko. F24: extremer konkurrierender externer Eintragsaustausch bleibt akzeptiert. Keine absolute Erhaltungsgarantie.
