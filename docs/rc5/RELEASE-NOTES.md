# v1.0.0-rc.5 – Prerelease zur praktischen TrueNAS-Abnahme

Vollständige RC4-Basis mit gezielten Praxisnachbesserungen:

- Fehlgeschlagene Papierkorb-Restores werden bei vollständigen vertrauenswürdigen Belegen durch Worker/Startup sicher finalisiert. Vollständiger Quellfingerprint, Medienbytes, private unabhängige Retention und transaktionaler Auditabschluss werden geprüft. Job bleibt failed samtOriginalfehler; Originale, Protokolle, Journale und Rückfallbytes bleiben erhalten. Unklare und widersprüchliche Zustände bleiben gesperrt.
- Private persistente Retention im Datenbankbereich schützt gegenüber nicht autorisierten Workspace-Schreibern innerhalb des dokumentierten Vertrauensmodells. Keine pauschale Lockerung gemeinsam beschreibbarer NFSv4-ACLs und keine automatische Bereinigung unbekannter Medien.
- Konkret dokumentierte UI-, Sprach-, mobile Layout- und automatisch erzeugte Import-/Quellbezeichnungen korrigiert. SD-Hintergrundprüfung, Duplikatschutz, Archivumbenennung, Metadaten, selektive und vollständige Papierkorblöschung bleiben erhalten.

**Vor dem ersten RC5-Start konsistente Sicherung anlegen.** Der Worker kann beim Start automatisch finalisieren. App/alle Schreiber stoppen; Datenbanken inklusive WAL/SHM, Registry/Retention/F14-Verwaltung, Konfiguration und relevante Workspace-Originale/Stage/Protokolle/Journale zusammen sichern und prüfen. Details: UPDATE-RC4-RC5.md. Zuerst isolierte synthetische Testdaten verwenden.

Freigegebener Produktcommit `62db66fab6f066116b36ed67dc29e4eb7f4f9034`, Tree `ab5b82ec43544cf8f9a92aecd63fb6a902c438bf`.
Abnahme: https://github.com/heller-adrian/Bibliothekar/actions/runs/40291622012
**1956 PASS, 0 FAIL/ERROR/SKIP**, linux/amd64-Build, frisches Onboarding, Authentifizierung, sechs Seiten/JS/CSS,176Apphashes, UID/GID568:568, SQLite/Fremdschlüssel und positive/negative Container-Startup-Recovery PASS. Alte rote Läufe bleiben roh dokumentiert; keine erneute Backend-Suite zur Veröffentlichung.

Digestgebundene TrueNAS-Konfiguration, Quellarchiv, Imagearchiv, SHA256SUMS, QA-Belege und Installations-/Update-/Abnahmeanleitung sind beigefügt. Bestehende SD-Helper-ACL-Voraussetzung bleibt: Web568 liest/durchquert den geschützten Removable-Bereich, schreibt dort nicht; effektive vererbte NFSv4-ACLs seiner Eltern mitprüfen. Automatische Katalogbereitstellung bleibt offen.

Native TrueNAS-/ZFS-/NFSv4-/SMB-/SD- und Smartphone-Abnahme steht aus. Linux-PASS ersetzt sie nicht. Administratoren und andere Prozesse mit den vertrauenswürdigen UIDs liegen innerhalb des Schutzmodells. Akzeptierte F13-Race/mmap- und extreme F24-Konkurrenzrisiken bleiben unverändert; keine absolute Erhaltungsgarantie. Archivdateien während Arbeitsbereich-Freigabe nicht extern ändern. B12 bleibt zurückgestellt.

Dies ist ein Prerelease; keine stabile1.0.0 und kein latest-Update.
