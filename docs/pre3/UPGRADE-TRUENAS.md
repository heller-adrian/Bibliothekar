# TrueNAS-Testupgrade: 1.0.0-pre.2 → 1.0.0-pre.3

**Nur Test-Prerelease, keine Freigabe für produktive Bestände.** Diese Anwendung wurde noch nicht nativ auf deinem TrueNAS abgenommen.

1. Die bestehende TrueNAS-App kontrolliert stoppen. Für einen verlustfreien Upgradepfad Appdaten und Workspace gemeinsam und konsistent sichern, vorzugsweise mit ZFS-Snapshots bei gestoppter App. Datenbank inklusive WAL/SHM, Journale und F14-Nachweise erhalten.
2. Vorhandene Custom-App bearbeiten, ausschließlich das Repository `ghcr.io/heller-adrian/bibliothekar` und den Tag `1.0.0-pre.3` einstellen. Wo die Oberfläche eine vollständige Referenz akzeptiert, das veröffentlichte `ghcr.io/heller-adrian/bibliothekar@sha256:…` aus `IMAGE-DIGEST.txt` verwenden. Digest nicht ungeprüft in ein reines Tag-Feld einfügen.
3. Appdaten, Workspace, Bibliotheken, UID/GID 568:568 und alle Mounts unverändert übernehmen. Alle Fotoarchive **Read Only** belassen. Keine zweite Instanz gleichzeitig mit denselben beschreibbaren Mounts starten.
4. Nach Start tatsächlich laufendes Image/Digest, Startprotokolle, Anmeldung und die neue Diagnoseansicht prüfen. Die historische Fuji-JPEG-Korrektur darf nur bei vollständiger Import- und Herkunftsprüfung qualifiziert werden. Die originalen Metadaten- und F14-Nachweise müssen dauerhaft erhalten bleiben.
5. Falls `Storage unavailable` weiterhin erscheint, ist dies **nicht automatisch ein Rückfall**: Bis zu drei originale F14-Operationen waren bekannt, zwei davon noch unklassifiziert. Unter „Repair options“ ausschließlich die authentifizierte Diagnose lesen, den Fehler protokollieren, keine Quellen verschieben und keine Nachweise löschen. Bei unbekannten oder fremden Inhalten bleibt die Sperre zurecht bestehen.
6. Einen kontrollierten Neustart erst nach erfolgreicher Qualifikation vornehmen; anschließend Bibliotheken, Hauptbestand und 14 iPhone-JPEGs mit dem Offset +13:00 kontrollieren.

Kein Clean Slate, keine manuelle SQLite-Statuskorrektur oder Abschwächung von Hash-/F14-Schutz. Ein Rückwechsel des Image-Tags ist keine Datenbank-Rückabwicklung: nur zusammengehörige Snapshots von Appdaten und Workspace wiederherstellen, wenn dies nötig ist.

### Kontrollierte Diagnose

Die Release-Anlagen enthalten `READ-ONLY-DIAGNOSIS.md` und `read_only_diagnosis.py`. Der Diagnoseaufruf ist ausschließlich zur privaten Beweissicherung bestimmt. Er schreibt nicht in die bestehenden SQLite-Dateien oder F14-Journale. Die Ausgabe kann interne Dateipfade und Bibliotheksdaten enthalten.

### Grenzen

Native TrueNAS/NFSv4, echte DNG 1.7 und physische SD/USB bleiben NOT_RUN; Verlustabschlussmodell DEFERRED. ExifTool-Kompatibilität mit DNG 1.7 wird hier nicht behauptet.
