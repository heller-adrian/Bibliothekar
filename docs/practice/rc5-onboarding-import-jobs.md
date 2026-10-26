# RC5 Praxispatch: Einrichtung, Importprüfung und Aufgabenkarte

Basis: veröffentlichter Produktcommit62db66fab6f066116b36ed67dc29e4eb7f4f9034.

## Einrichtung

Eine neue leere Struktur wird weiterhin im normalen Startup initialisiert und tatsächlich gebunden; normale Erstinstallationen benötigen keinen Dialog. Das produktive /workspace muss als Mount verfügbar sein (einschließlich Linux-Bind-Mounts). Containerpfad/Mountnachweis allein identifiziert kein konkretes NAS-Dataset; korrekte externe Zuordnung bleibt Installationsvoraussetzung.

Bei alten F14-Bindungen und einem geleerten Workspace erscheint **Neu einrichten / Set up again** ausschließlich nach positivem Nachweis. Authentifizierung, CSRF und ausdrückliche Bestätigung erforderlich. Gleicher Workspace-Inode, englische Standardnamen, gleiche DB-Bindung und leerer Strukturbaum; keine Bibliotheksregistrierung, Bestandsregistry, Kataloghistorie, Retention, offenen Reservationen, unbekannten Belege, fremden ACL-Schreiber oder SQLite-Recoverybytes. Alle registrierten/alten externen Pfade müssen eindeutig und leer bleiben. Neue Dataset-/Mountidentität, fehlender Katalog bei vorhandenen Medien oder unklare Reste bleiben gesperrt.

Unter bestehender exklusiver F14-Sperre werden die Prüfungen wiederholt, der komplette frühere Zustand unter setup-history-<SHA256>.json gesichert und die neue Generation atomar veröffentlicht. Keine alte Datei, Bibliothek, Registry oder Retention wird gelöscht oder übernommen. Nach SIGKILL vor Veröffentlichung bleibt der Altzustand; nach Veröffentlichung übernimmt die vorhandene resumierbare Initialisierung. SQLite-SHM, das schon durch lesende Abfragen entstehen kann, ist nur neben separat geprüften vorhandenen Datenbanken zulässig. WAL/Recoveryjournale, verwaistes SHM und Datenhistorie bleiben Sperrgründe.

## Import

Ordner-/Laufwerksimporte benutzen vorab die vorhandene persistente SD-Prüfqueue. HTTP stellt nur einen technischen Auftrag ein. Quelle wird FD-/No-follow-gebunden vollständig gehasht, Veränderungen und Symlinks werden abgewiesen. Herkunft aller registrierten Kataloge und tatsächlich erhaltene Kopien werden mit dem vorhandenen Integritätsmechanismus geprüft. Vollständiger Bestand endet ohne Kindimport, neue Sicherungsordner oder Importhistorieneintrag. Neue/fehlende Dateien erhalten eine transaktionale Übergabe an den normalen SHA-/Familien-/No-Clobber-Importer. Prüfungen sind über die bestehende Abbruch-API abbrechbar und über vorhandene Jobverwaltung sichtbar; Wiederholung und Startup prüfen erneut.

Der alte Routingtest hat nun ein explizites synthetisches RO-Mountmodell und beendet die erste Prüfung über die echte Abbruch-API, bevor er einen zweiten Ordner desselben Geräts auswählt. Alle ursprünglichen Pfad-/Geräteassertions bleiben; Originaldatei und Rohresultate im QA-Paket. Keine direkte SQL-Statuskorrektur als Ersatz für diesen Ablauf.

## Oberfläche und Prüfung

Der Mini-Button benutzt dieselbe undurchsichtige Fläche wie Prozentfeld und Karte; Ring/Animation/Position bleiben. Neue Texte stehen vor der Erzeugung des ausgelieferten DE/EN-Wörterbuchs.

Gezielt insgesamt 301 unterschiedliche PASS, ein unveränderter roher macOS-FAIL des expliziten Linux-/dev/shm-Tests,0SKIP; darunter 48 neue Fälle. Kein Gesamtsuiten-PASS behauptet. Große Sicherheitsauswahl250PASS/1Plattform-FAIL; direkte letzte Auswahl72PASS/1Fixture-Vertragsfehler, anschließend SQLite-Auswahl10PASS. Vier Browserfälle für die echte Importseite plus vier Shell-Gegenproben PASS. Native RO-Mount-/NFSv4-Eigenschaften sind lokal modelliert, nicht nativ TrueNAS-abgenommen. Virtuelle5,5GiB-HTTP-Probe benutzt Sparse-Datei, keine Performancezusage für tatsächliches Hashen dieser Datenmenge.

## Noch praktisch prüfen

Isolierte TrueNAS-Testdatasets: frische Einrichtung und bestätigter geleerter Altzustand, echtes Mount/ACL-Verhalten, tatsächlicher Warnungsdialog/Onboarding;100 bekannte Dateien, gemischtes JPG/RAW/Video, verlorene bzw. veränderte Kopien; USB/SD, Abbruch/Neustart und Smartphone in DE/EN. Unterschiedliche gleichzeitig eingereichte Quellen und Änderungen anderer Importe zwischen Prüfabschluss und Kindimport benötigen einen zusätzlichen Integrationsnachtest; der normale Import prüft weiter selbst, eine absolute Nullauftragsgarantie über diesen Übergang wird nicht behauptet.

Keine NAS-Änderungen, Versionserhöhung, Gesamtsuite, Actions oder Veröffentlichung. Private Retention sowie F11/F12/F14/F24 bleiben erhalten; akzeptierte Restrisiken unverändert.
