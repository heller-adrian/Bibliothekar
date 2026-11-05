# Private Autorität und TrueNAS-ACLs

Die Kontrollgrenze umfasst den privaten Datenbankmount, F14-State, Sperren, Reservationen, Abschluss- und Migrationsbelege sowie deren mountsichtbare Eltern. Ein Fremder darf private Dateien weder schreiben noch über ein Elternverzeichnis löschen/ersetzen oder ihre ACL/Eigentümerschaft verändern können.

Vertraut werden UID 0 und die tatsächliche Web-UID (Standard 568). Schreib-Grants an Administratorgruppen 0 und 544 liegen innerhalb der ausdrücklich definierten Administrationsgrenze. Die App isoliert sich nicht gegenüber Host-root, diesen Administratoren oder anderen Prozessen mit identischer App-UID. Gruppenname `apps` ist keine Einzelbenutzeridentität. Namentliche Benutzer `adrian` (3000), `hermes` (3001) und andere NAS-Benutzer werden nicht stillschweigend vertraut. Ihre direkten Schreib-ACEs blockieren die private Qualifikation. Hostadministration kann ihnen unabhängig davon administrative Rechte geben; das ist keine automatische App-Freigabe eines benannten ACL-Eintrags.

## Unterstützte Prüfung

- Linux: Kernel-Mountzuordnung des gehaltenen Deskriptors aus `/proc/self/fdinfo` und `/proc/self/mountinfo`.
- Lokale POSIX-Dateisysteme: ext2/3/4, XFS, Btrfs, tmpfs, OverlayFS, aufs und ramfs; native ACL-Attribute werden explizit abgefragt. Nicht ausgewertete POSIX-Access-ACLs werden konservativ abgewiesen, statt aus Modusbits Sicherheit zu erraten. Default-ACLs werden am Erzeugungsziel ebenfalls nicht ignoriert.
- TrueNAS-ZFS: tatsächlich lesbares `system.nfs4_acl_xdr`, bekannte XDR-Struktur und sämtliche bekannten Schreib-/Lösch-/ACL-/Eigentümerrechte. Die Definitionen sind an [TrueNAS nfs4.h](https://github.com/truenas/nfs4xdr-acl-tools/blob/master/include/nfs4.h) und [XDR-Decodierung](https://github.com/truenas/nfs4xdr-acl-tools/blob/master/libnfs4acl/acl_nfs4_xattr_load.c) geprüft.
- `security.nfs4acl_xdr` ist keine hinreichende Kernel-Autorität. Die TrueNAS-Bibliothek unterstützt diese alternative Ablage auch für nichtnative/testweise ACLs. RC11 verwendet sie nicht als Sicherheitsbeweis. Siehe [TrueNAS Xattr-Reader](https://github.com/truenas/nfs4xdr-acl-tools/blob/master/libnfs4acl/nfs4_get_acl.c).
- Unbekannte Dateisysteme, fehlende native ZFS-ACL, verweigerte ACL-Abfrage oder unbekannte Semantik blockieren. Die App synthetisiert keine NFSv4-ACL aus POSIX-Modi.
- Darwin: nachgewiesene Abwesenheit einer nativen ACL; nichttriviale Darwin-ACLs werden konservativ blockiert. Dies ist kein TrueNAS-Backend.

Allow-Grants an unberechtigte Prinzipale werden auch bei vorangestellten Deny-ACEs konservativ abgewiesen; komplexe ACLs werden nicht als sicher geraten. Inherit-only und geerbte Schreib-Grants werden berücksichtigt. Die Prüfung ist eine hinreichende strenge Qualifikation, keine vollständige Anzeige aller effektiven Benutzerberechtigungen.

Alle Komponenten werden No-follow geöffnet und ihre gehaltenen Identitäten revalidiert. Neue private Dateien werden vor dem Schreiben und vor Veröffentlichung geprüft. RC11 führt kein chmod/chown/setfacl zur Reparatur bestehender Daten aus.

## Administrative Vorbereitung

Den alten Container vor Änderungen an der privaten Kontrollgrenze anhalten und eine konsistente Sicherung erstellen. In TrueNAS den **privaten** Appdaten-/Datenbankbereich einschließlich relevanter Eltern so konfigurieren, dass nur die definierte App-/Administrationsgrenze schreiben, löschen, ersetzen oder Rechte verändern kann. Keine pauschale rekursive Änderung am Foto-Workspace oder Archiv vornehmen.

Auf ZFS eine explizite, für UID 568 lesbare native ACL verwenden. Breite geerbte Einträge für `builtin_users`, `apps` als allgemeine Gruppe oder weitere Benutzer sind dort kein zulässiger Ersatz. Auch ein `0700`-State kann durch eine nichttriviale ACL unsicher bleiben. Eine Härtung einzelner Dateien reicht nicht, wenn ein Elternordner ihren Austausch erlaubt.

Wenn das native ACL-Backend im Container nicht lesbar ist, bleibt die App mit `acl_backend_unavailable` gesperrt. Administratoren müssen die Lesbarkeit und private Rechte im tatsächlich gemounteten Dataset herstellen beziehungsweise einen dafür geeigneten privaten Mount vorsehen. Eine Umgebungsvariable zum Abschalten dieser Prüfung existiert nicht.

Die gemeinsame Workspace-ACL darf dagegen grundsätzlich bestehen bleiben. Medien und dortige Journale werden weiterhin durch die jeweiligen F14-/No-follow-/Hash-/Recoveryverträge geschützt. Das alte RC10-Lock wird nach geprüfter Migration nur als inaktives, unsicheres Koordinationsartefakt inventarisiert und nicht mehr zur Autorisierung verwendet.

Native Prüfung auf dem tatsächlichen TrueNAS ist ein separates Abnahmegate. Bytefixtures und Linux-POSIX-Tests beweisen keine NFSv4-Kernelwirkung.
