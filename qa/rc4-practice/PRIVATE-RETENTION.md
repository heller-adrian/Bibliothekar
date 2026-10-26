# Fehlgeschlagene Restores: private Retention

## Verwendete neue NAS-Nachweise

Fortsetzung von `6c6bba86f0a270b6f58d18284312bac7d8d2644c`.
Der reale Auftrag `TRASH_IMPORT_20261023_205446_538D89094806` ist laut
Benutzerdiagnose fehlgeschlagen, hat `result=null` und einen nicht leeren
64-stelligen Quellenfingerprint (Präfix `f9611220`). Der vollständige Wert wird
**zur Laufzeit aus SQLite** gelesen; sein Präfix berechtigt zu keiner Freigabe.
Seine Übereinstimmung mit den echten NAS-Dateien ist hier nicht vorweggenommen.

Die bestätigten Bind-Mounts `/database` und `/config` sind deutlich enger
berechtigt als der gemeinsame Workspace. Das alte Statusdokument und seine
Eltern mit UID568/GID0 und0770 bleiben unverändert. Ihre ACLs sind keine private
Vertrauensgrenze. Ihre Bytes werden lediglich als Diagnosebeilage erhalten.

## Explizites Vertrauensmodell

Vertraut werden root, die tatsächliche App-EUID und der Eigentümer des
**konfigurierten privaten Datenbank-Elternverzeichnisses** als dessen
Administrator. Im gemeldeten Betrieb sind das UID0,568,3000. Schreibende
System-Administratorgruppen0 und544 gehören ebenfalls zur Vertrauensdomäne.
Das setzt voraus, dass deren Mitgliedschaft tatsächlich auf beabsichtigte
Administratoren beschränkt ist. Die Prüfung versucht nicht, Hostgruppen im
Container anhand gleich klingender Kontonamen aufzulösen.

Alle Prozesse mit denselben vertrauenswürdigen UIDs/GIDs, insbesondere andere
Apps mit UID568, Hostadministratoren, der privilegierte Containersupervisor und
der Kernel sind Teil dieser Vertrauensdomäne. Gegen sie besteht **keine**
behauptete Isolation. Ein Deployment, das unzuverlässige Apps unter568 betreibt
oder weitere Personen in diesen Administratorgruppen führt, erfüllt diesen
Vertrag nicht. Dafür wären getrennte Identitäten/Provisionierung erforderlich;
der Patch ändert keine NAS-ACLs und behauptet keinen Schutz durch0700 allein.

Die Container-Mountgrenze bindet den sichtbaren Datenbanknamensraum. Die
Host-Mountquellen und deren austauschbare Eltern müssen durch den Installer
gegen nicht vertrauenswürdige Schreiber geschützt sein. Das kann ein Prozess
im Container nicht vollständig aus Host-ACLs rekonstruieren. Die gelieferten
NAS-Nachweise und die ausdrücklich akzeptierte Administratorgrenze sind daher
eine Installationsvoraussetzung, keine allgemeine Host-Isolationsbescheinigung.

## Mechanismus

1. Bestehende F14-Zulassung und prozessübergreifende F11-Papierkorbsperre halten.
   Registry, alle zu diesem Workspace registrierten Kataloge und vorhandene
   SQLite-Seitendateien müssen im selben privaten DB-Elternverzeichnis liegen.
   Dieses darf weder innerhalb des Workspace liegen noch dessen Elternordner
   sein. Alle sichtbaren Eltern werden ohne Symlinkverfolgung geöffnet und
   ihre Inodebindung wiederholt geprüft.
2. Native TrueNAS-NFS4-XDR-ACLs per Dateideskriptor lesen. Jede ALLOW-Schreib-,
   Anlege-, Lösch-, Attribute-, ACL- oder Eigentümerberechtigung für andere
   Principals führt zur Ablehnung; auch inherit-only-Rechte werden konservativ
   geprüft. DENYs heben einen verdächtigen ALLOW-Eintrag nicht pauschal auf.
   Unbekannte/mehrdeutige ACL-Formate oder Lesefehler bleiben gesperrt. Nur bei
   nachweislich fehlender erweiterter ACL gilt die zusätzliche POSIX-Prüfung.
   Keine Rechteänderung an bestehenden Objekten. Unter macOS wird die native
   ACL-Anwesenheit mit fstatx/filesec abgefragt; ALLOW-ACLs bleiben unqualifiziert,
   reine DENY-ACLs gewähren keine zusätzlichen Rechte.
3. Genau ein failed-Job, passender Stagepfad, vollständige Journalpartition,
   keine teilweise katalogisierten files/families und keine überlappende
   Restore-Recovery. Vollständiges rekursives FD-Manifest des Stagingbestands
   mit Pfad, Größe und SHA256 gegen gespeicherten Quellenfingerprint vergleichen.
   Das Journalmanifest muss denselben Fingerprint ergeben. Papierkorboriginale
   vollständig gegenprüfen; unbekannte Zwischenmedien, Symlinks und widersprüchliche
   Statusdokumente sperren. Ein passender Fehlertext ist kein Beweis.
4. Neues exklusives Retentionsverzeichnis unter
   `/database/.bibliothekar-restore-retention/<zufällige Beleg-ID>/` erzeugen,
   tatsächliche vererbte Ziel-ACLs prüfen. Alle Medien nach `media/` kopieren,
   keine Hardlinks; Originale und Stage bleiben erhalten. Mindestens64MiB
   zusätzliche SQLite-/WAL-Reserve über fstatvfs verlangen. Quota-/IO-Fehler
   bleiben Fehler. Jede Kopie vollständig rücklesen, Hash, Größe, Identität,
   nlink1 und Unabhängigkeit prüfen; Dateien und Eltern fsync.
5. Originaljournal und Statusbytes zusätzlich in privater `evidence.json`
   bewahren. Medien und Diagnose besitzen getrennte Namensräume. Nochmals
   vollständiges Quellmanifest, Originale, Workspacejournal, Statusrest,
   DB-/Jobidentität und ACLs prüfen. Canonical receipt + Audit gemeinsam in
   bestehendem `jobs.result_json`/`audit_log` committen (SQLite FULL/WAL).
   `state`, `stage`, ursprünglicher Fehler und Importhistorie bleiben failed.
6. Reservierung erst nach frisch validiertem privaten Receipt, privaten Medien
   und Diagnosehash freigeben. Ein Workspace-JSON kann die Freigabe nicht
   selbst behaupten. Unveränderte Journalbindung bleibt erforderlich; spätere
   Manipulation sperrt wieder. Stage und mutable Statusdatei werden nach dem
   privaten Abschluss nicht mehr als alleinige Rückfallgarantie benutzt.
   Erfolgs-Cleanup/erneute Vorbereitung des abgeschlossenen Fehlerauftrags
   sind ausdrücklich gesperrt.

Vor dem DB-Commit ist keine neue Freigabe wirksam. SIGKILL lässt alle bereits
angelegten Kopien erhalten. Ein weiterer Versuch verwendet ein neues exklusives
Verzeichnis; unvollständige Versuche werden nicht gelöscht und gelten nicht als
Beweis. Nach Commit validieren Worker/Startup denselben Beleg idempotent; kein
zweiter Auditabschluss. GET inventarisiert lediglich und finalisiert nicht.

## Fehlender historischer Anker

Kein automatischer Abschluss bei fehlendem/leeren Fingerprint und gemeinsam
beschreibbaren Rückfallpfaden. In den vorhandenen Details kann der Benutzer
**gesondert ausdrücklich** „Alle erhaltenen Varianten sichern“ bestätigen.
Dieser Weg kopiert sämtliche aktuellen Stagevarianten sowie alle ausgewählten
Papierkorbvarianten getrennt nach `media/staging/` und `media/trash/`. Er verlangt
mindestens eine erhaltene Variante je reserviertem Pfad und dieselbe private
Ziel-, Katalog-, Journal- und Recoveryprüfung. Unbekannte Typen/Medienbewegungen,
fehlende letzte Variante oder Teilkataloge bleiben gesperrt.

Er behauptet keine historische Originalidentität und importiert keine Variante
in den Fotokatalog. Der Beleg markiert `confirmed-current-variants`; UI und
Bestätigungsdialog benennen die fehlende historische Authentizität. Ein
vorhandener gültiger Quellenfingerprint darf damit **nicht** umgangen werden.
Die alte normale Sicherheitsbestätigung startet diesen Weg nicht.

## Erstinstallation / Katalog

Die spätere App-Paketierung muss private persistente DB-/Config-Datasets
außerhalb der gemeinsamen Fotoablage über die Installationsoberfläche
bereitstellen. Keine breite SMB-/NFS-Schreibvererbung; Dataset-Eigentümer,
Administratorgruppen, Host-/Container-UID-Abbildung, Mountquelle und deren Eltern
müssen dem obigen Modell entsprechen. Andere Apps dürfen die App-Identität568
nur verwenden, wenn sie als vertrauenswürdig gelten. Keine manuelle Shell-,
chmod- oder chown-Pflicht als Produktlösung. Die Laufzeitprüfung lehnt eine
nicht qualifizierte Ablage ab, statt bestehende ACLs zu „reparieren“.

Installerprüfung: Rechte für DB/Registry/WAL/SHM, Rootkoordination und neu
angelegte Retentionsdateien tatsächlich lesen; als fremder Testnutzer3001
Schreiben/Ersetzen/Löschen verweigern lassen. Host-Mount-/Elternvertrag separat
nachweisen. Konfiguration und Authentifizierung verbleiben unter `/config`;
Retentionsmedien liegen ausschließlich im DB-App-Dataset. Keine vollständige
Katalogimplementierung in diesem Patch.

## Quellen und verbleibende Plattformgrenze

TrueNAS-XDR-Format und Namen anhand der primären Implementierung geprüft:
- https://github.com/truenas/nfs4xdr-acl-tools/blob/master/libnfs4acl/acl_nfs4_xattr_load.c
- https://github.com/truenas/nfs4xdr-acl-tools/blob/master/include/libacl_nfs4.h
- https://github.com/truenas/nfs4xdr-acl-tools/blob/master/include/nfs4.h
Darwin: lokale SDK-Header `sys/acl.h`, `sys/fcntl.h`, `sys/stat.h` und
https://github.com/apple-oss-distributions/Libc/blob/main/posix1e/acl_file.c.

Lokal macOS UID502/GID20, keine Linux-/NFS4-VM oder Containerengine vorhanden.
Native FD-Dateioperationen und echte SIGKILL/Starts sind lokal geprüft; NFS4-ACEs
und UID568/3000/3001 werden in den gezielten Tests ausdrücklich modelliert.
Separate Fremdschreiberprozesse laufen unter der Host-Test-UID; sie modellieren
zugelassene Workspace-Schreiber, keine Kernel-NFS4-Qualifikation.

Noch nötig: isolierte TrueNAS-Abnahme der nativen XDR-xattr-Lesbarkeit und
geerbten Retentions-ACLs, echten fremden Benutzerrechte, Mount-/Gruppenzuordnung,
Quota/fsync/Neustart sowie des vollständigen realen Quellenfingerprints. Eine
Ablehnung nennt den konkreten Konflikt und erhält alle Daten. Keine vollständige
Linux-/TrueNAS-Freigabe aus POSIX- oder XDR-Modelltests ableiten.
