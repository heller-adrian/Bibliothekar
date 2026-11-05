# Neue TrueNAS-Installation

RC11 ist zur Freigabe vorbereitet; ein öffentlicher RC11-Tag darf erst nach Freigabe verwendet werden. `compose.example.yaml` enthält den vorgesehenen Versionsnamen, veröffentlicht aber kein Image.

Mounts: `/workspace` RW für die vier Verwaltungswurzeln, `/config`, `/database`, `/logs` als eigene Appdaten, `/main-library` als gesonderter RO-Archivmount. Original-Supervisor als root starten; er setzt den Webprozess auf UID/GID 568:568 herab. Den verpflichtenden Administratorzugang vor Exponierung des Ports konfigurieren. Es gibt kein Standardpasswort.

Den privaten Datenbank-/Kontrollbereich nach [SECURITY.md](SECURITY.md) vorbereiten. Auf TrueNAS muss seine tatsächlich lesbare native NFSv4-ACL einschließlich der Eltern die private Autorität belegen. Ein gemeinsamer Workspace darf andere NAS-Benutzer berechtigen; private Steuerdaten dürfen das nicht.

Ein technisch unbenutzter Workspace darf `.DS_Store` enthalten. Ein unabhängig gefülltes RO-Archiv ist keine registrierte Bibliothek. RC11 erstellt automatisch `SD Card Backups`, `Library Workspaces`, `Metadata Correction` und `Trash`, fehlende Config und technische Datenbanken. Das aktive Trash-/Recovery-Lock entsteht ausschließlich im qualifizierten privaten Kontrollbereich.

Nach technischem Abschluss und Anmeldung erscheint die erste Bibliothekseinrichtung. Bibliotheksname, Arbeitsbereich und RO-Archiv werden erst dort bewusst registriert. Danach Neustart und einen weiteren geschützten Vorgang prüfen. Bei unsicherer privater ACL nennt die Oberfläche betroffenen Pfad, Ursache und administrative Vorbereitung; es wird keine unsichere Erstinstallation fortgesetzt.
