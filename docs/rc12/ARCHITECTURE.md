# RC12: Speicherzustände und Vertrauensgrenze

Ausgangspunkt ist das veröffentlichte RC11-Tag d275b4a9. RC12 ändert das Installationsprofil, nicht die Semantik bestätigter Medienverluste.

## Befund im vollständigen Startpfad

Der Supervisor startet Web als UID/GID 568:568 und optional den privilegierten Quellenhelper. Vor RC12 prüfte `_coordinate_startup` über `require_storage` und `inspect_storage` Konfiguration, Datenbankeltern und F14, bevor Ordner, Konfiguration oder SQLite angelegt wurden. `private_storage_security.qualified` qualifizierte dabei jeden Elternpfad und verlangte UID 0/568 sowie ausschließlich erlaubte ACL-Schreibberechtigte. Deshalb scheiterte ein leeres Dataset UID3000 mit tatsächlichem UID568-Zugriff bereits vor einer Aussage zur Bibliothekshistorie. Zusätzlich konnten unlesbare native ACLs, breite Vererbung oder gruppenschreibbare technische Dateien die gesamte Anwendung blockieren.

Erforderliche Kontinuitätsschutzregeln bleiben: Workspace-Mount vorhanden/RW, keine Symlinks in verwalteten Pfadketten, exakte bekannte Ordneridentitäten, F14-Generationen und Reservations-ID/Operationsschlüssel, persistierte Abschlussbelege, lesbare konsistente Registry/Kataloge, positive Medien-/Job-/Retentionhistorie, ungeklärte kritische Dateioperationen, keine automatische Archivregistrierung. Ein fehlendes Schema darf historische Belege nie überstimmen.

UID- und vollständige ACL-Exklusivität aller NAS-Eltern sind zusätzliche Host-Manipulationshärtung. Sie beweisen keine Bibliotheksnutzung und sind keine Voraussetzung für ein hostverwaltetes Fotoarchiv. RC12 trennt diese Härtung vom normalen Installationsprofil.

## Ein explizites neues Profil

`KAMERA_APPDATA=/appdata` wählt ein **hostverwaltetes** Profil. Root, Dataset-Eigentümer und alle von der NAS-ACL berechtigten Writer gehören zur administrativen Vertrauensgrenze. Deren Änderungen können nicht kryptografisch von Appänderungen unterschieden werden. Dieses Profil ist nicht manipulationssicher gegenüber diesen Akteuren. Unlesbare native ACLs sind hier kein Neuinstallationsblocker; es wird auch keine erfolgreiche ACL-Exklusivitätsprüfung behauptet. Tatsächliche Kernelzugriffe, sichere Dateitypen, einzelne Links, keine Symlinks und FD-gebundene Revalidierung bleiben verbindlich.

Die Anwendung legt nur config/database/logs/removable-sources unter dem vorhandenen Appdatenmount an. Echte Erzeugungs-, Schreib-, fsync- und Löschproben erfolgen als Web-UID. Es gibt kein chmod/chown und keine ACL-Reparatur. Fehlender tatsächlicher Zugriff sperrt mit dem betroffenen Pfad. Ein nicht gemountetes `/appdata` wird nicht automatisch erzeugt. Pfadüberschneidungen und alte Variablen außerhalb des neuen Stamms werden abgewiesen.

F14-Format 3 kennzeichnet dieses Profil. Neue Instanz-ID und Appdaten-/Workspace-Identitäten werden vor technischen F14-Schritten gespeichert. Ein atomar veröffentlichter Workspace-Claim verhindert die automatische Übernahme durch eine andere Instanz mit frischen Appdaten. Eine unterbrochene eigene Claim-Veröffentlichung wird anhand derselben ID wiederholt. Nach technischem Commit werden fehlende Katalog-/Registry-/State-Dateien als Historienverlust behandelt, nicht neu erzeugt.

Ohne KAMERA_APPDATA bleibt der bisherige RC11-Vertrag einschließlich nativer ACL-Prüfung und expliziter RC10-Übernahme aktiv. Es findet kein automatisches Verschieben, Zurücksetzen oder Umdeuten alter Kontrollzustände statt. Ein RC11-Workspace mit Legacy-Lock und frischen RC12-Appdaten ist AMBIGUOUS. Selbst leere technische Verwaltungsordner ohne solche Gegenbeweise sind dagegen kein Benutzerbestand.

## Fünf Zustände

| Zustand | Nachweis | Verhalten |
|---|---|---|
| FRESH | Technisch leer, keine positive Nutzungs-/Operationshistorie, kein fremder Claim | Technische Einrichtung automatisch |
| INITIALIZING | Passende eigene Startupreservation und prüfbare unvollständige Schritte | Dieselbe Reservation kontrolliert fortsetzen |
| READY | Technisch abgeschlossen, Katalog/Registry verfügbar, bekannte Identitäten und Mounts passend | Normaler Betrieb; ohne Benutzerbibliothek Onboarding |
| DEGRADED | Bekannter Pfad/Mount/Historie fehlt oder wurde ersetzt, tatsächlicher Zugriff fehlt | Authentifizierte Diagnose; gefährdete Dateioperationen gesperrt |
| AMBIGUOUS | Unbekannte Inhalte, fremde Instanz, Legacy- oder widersprüchliche Operationsnachweise | Kein Reset; ursprüngliche Historie/Mounts wiederherstellen oder explizites Legacy-Verfahren |

Der öffentliche Zustand wird zentral aus der Kontinuitätsbeobachtung bestimmt. `ready` bedeutet technisch bereit, nicht bereits angelegte Benutzerbibliothek. Das Onboarding ist ein eigener Benutzerworkflow. Die Datei-/Journalprüfungen bleiben bei jedem F14-Eintritt aktiv; eine globale ACL-Vermutung ersetzt sie nicht.

Wenn sämtliche historischen Informationen einschließlich Workspace-Claim, Medien und Appdaten verschwinden, lässt sich vollständiger Verlust nicht von Neuinstallation unterscheiden. Kein Zustandsautomat kann verschwundene Beweise rekonstruieren. NAS-Backups und administrativ richtige Mountzuordnung bleiben erforderlich.

## Reparatur nach Rolle

| Rolle | Ursprüngliche Identität wieder verfügbar | Bestätigter leerer Ersatz |
|---|---|---|
| Trash, SD Card Backups, Metadata Correction | Erneut prüfen | Nur registriert/persistiert, identischer Workspace/Mount, leeres Ziel, gesunde Kataloge, keine ungeklärten Operationen; Verlustreceipt und Generationserhöhung |
| Library Workspaces / registrierter Arbeitsordner | Erneut prüfen | Zusätzlich alle registrierten Kindwurzeln prüfen/neu binden; unbekannte Kinder verhindern Ersatz |
| Workspace oder abweichender/fehlender Dataset-Mount | Ursprüngliche Einbindung wiederherstellen | Kein automatischer Ersatz; keine Ordneranlage auf dem darunterliegenden Dateisystem |
| Datenbank, Registry, F14-State, Appdatenstamm | Konsistente Gesamtsicherung wiederherstellen | Kein leerer Ersatz und keine SQLite-/Receipt-Löschung |
| Kritisches offenes Journal | Passenden bisherigen Recoverypfad ausführen | Keine pauschale Freigabe durch Ordnerersatz |

Ersatz verlangt authentifizierte Sitzung, CSRF, doppelte UI-Bestätigung und `I ACCEPT MISSING FILES`. Alte Medienreferenzen werden weder gelöscht noch als erfolgreich abgearbeitet markiert. Ursprünglicher Ordner heißt exakte Geräte-/Inodeidentität, nicht Kopie einzelner Dateien. Stabile Mount-Provenienz (Mountziel, Root, Quelle, Gerät, Dateisystem) verhindert einen Ersatz bei verschwundenem separatem Rollenmount; Kernel-Mount-ID allein wäre nach Neustarts ungeeignet.

## Wechselmedien und Privilegien

Die Basisinstallation benötigt keinen privilegierten Container und aktiviert den Quellenhelper nicht. NAS-/Ordnerquellen bleiben möglich. Optional aktiviert compose.removable.yaml den bisherigen Gerätehelper. Der Supervisor bereitet Appdaten zuerst als UID568 vor, setzt ausschließlich seinen Container-Appdatenbind auf rprivate und montiert einen rootkontrollierten Tmpfs auf /appdata/removable-sources. Hostinhalt wird nicht übermountet, wenn dort unbekannte Dateien liegen. Der Webprozess kann diesen gemounteten Pfad nicht umbenennen, keine Helperjournale ändern und nur lesend auf Quellen zugreifen.

Helper und Web teilen denselben Containermountnamespace; rshared-/Hostpropagation ist nicht erforderlich. Mounts bleiben `ro,nosuid,nodev,noexec`, reale Kernel-/Geräteidentität und persistierte Helpernachweise innerhalb der Runtime bestimmen die Unmountberechtigung. Ein fremder Mount wird nicht aufgrund seines Pfadnamens übernommen. Containerneuanlage verwirft die Runtime und deren Mountnamespace. Der Kernel muss den bisherigen eindeutigen statx-Mountnachweis unterstützen. Fehlende Helperprivilegien/Kernelfähigkeiten deaktivieren Wechselmedien mit Diagnose und blockieren nicht das Bibliotheks-Onboarding.

Native TrueNAS-ACL-Vererbung, reale SD-/USB-Geräte und die konkrete Custom-App-Oberfläche benötigen weiterhin eine eigene Abnahme. Linux- und synthetische Unit-Tests werden nicht als native TrueNAS-Freigabe ausgegeben.
