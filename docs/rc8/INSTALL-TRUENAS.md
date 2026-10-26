# RC8 auf TrueNAS SCALE

Bestehende RC7-App: UPDATE-RC7-RC8.md verwenden; Datenpfade unverändert übernehmen.

Neue isolierte Test-App: digestgebundenes compose.truenas.yaml verwenden und alle Beispiel-Hostpfade auf eigene tatsächlich bereitgestellte Test-Datasets anpassen. create_host_path:false beibehalten; ein erreichbarer leerer Pfad beweist keinen vorgesehenen NAS-Mount. Private /database und /config einschließlich Eltern auf die dokumentierte App-/Administrator-Vertrauensgrenze begrenzen; gemeinsame Foto-/Workspace-Rechte nicht pauschal ändern. /logs und /workspace persistent beschreibbar, Archiv und NAS-Quellen wie vorgesehen read-only. Root-Entrypoint trennt Web568:568 und internen Gerätehelper. Einstellungen zu Mountpropagation/Geräten aus der funktionierenden Installation bewahren; keine fremden Mounts übernehmen.

Vor Netzwerkfreigabe Admin-Passwort über die bestehende private Passwortdatei konfigurieren. Keine Standardanmeldung. Nach Start erzeugt die App die vier englischen Verwaltungsordner automatisch; anmelden und die erste Bibliothek über das Onboarding mit Name, Arbeitsbereich und Archiv anlegen. Kein Terminalanlegen der Verwaltungsordner nötig. Bei Storage-/ACL-/Mountfehlern den konkreten Dialoggrund prüfen, keine Schutzprüfungen umgehen.

SD-Helper benötigt weiterhin die nachgewiesene manuelle NFSv4-ACL des geschützten Mountbereichs und seiner Eltern: Web568:568 Lesen/Durchqueren, kein Schreib-/Löschzugriff; tatsächliches ro,nosuid,nodev,noexec. Kein pauschales chmod/chown/ACL-Rezept. Automatische Bereitstellung durch den späteren TrueNAS-Katalog ist offen. Native Geräte-/ZFS-/NFSv4-/SMB-Abnahme ausstehend.
