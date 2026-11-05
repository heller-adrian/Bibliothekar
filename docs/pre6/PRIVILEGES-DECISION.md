# TrueNAS-Katalogprofil – ausschließlich Analyse, 03.11.2026

Status: **ARCHITECTURE_RECOMMENDATION; keine Deployment-Implementierung.** Dockerfile, Compose, Supervisor, Helper, Mount-Ledger und Sicherheitsmechanismen unverändert.

## Tatsächliche Aufruf- und Rechtegrenzen

`container_supervisor.run()` → Vorbereitung der App-Unterverzeichnisse bereits mit Web-Zugangsdaten → Webserver UID/GID568. Im Grundprofil bleibt der Supervisor UID0, der Helper ist deaktiviert. `compose.example.yaml`: kein privileged, read-only Containerroot, /tmp-Tmpfs und no-new-privileges; Appdata/Workspace RW, Archiv RO. Das ist bereits nicht privileged, aber noch kein vollständig als UID568 betriebenes Gesamtprofil.

Bei explizitem optionalem Geräteprofil: Web-API → localhost-Helper → verifiziertes Kernel-Blockgerät (Major/Minor) → eigener Mountpunkt/Ledger → mount/umount → erneute Mount-/Geräteidentitätsprüfung. `compose.removable.yaml` aktiviert privileged und /run/udev:ro. Helper benötigt aktuell UID0; ohne Rechteumstellung verweigert der Supervisor diese Betriebsart ausdrücklich. Ist der Gerätenode nicht vorhanden, verwendet `_ensure_mount_device_node()` mknod. Ein Ledger-konformes Unmount ist erforderlich; keine geratenen/übernommenen Fremdmounts.

## Empfehlung und noch zu qualifizierende Varianten

| Profil | Vorschlag | Grenze |
|---|---|---|
| Katalogstandard | Supervisor und Webprozess568:568, Helper deaktiviert, ausschließlich vorgegebene Ordner-/NAS-Quellen RO, cap_drop ALL, RO-Containerroot und private beschreibbare App-Volumes | Machbarkeit aus Code plausibel; vollständiger rootloser Betrieb noch NOT_RUN. Mount-/Appdatenzugriff und Neustart müssen im TrueNAS-Template verifiziert werden. |
| Bestehendes SD/USB-Profil | Separat und ausdrücklich erhöhte Rechte; vorläufig unverändert | Nutzerbericht bestätigt echte Gerätefunktion; breite Hostrechte, keine gleichwertige Sandbox zum Standardprofil. |
| Reduzierte Gerätefähigkeiten | Isolierter späterer Versuch: notwendige SYS_ADMIN-Mountrechte, ggf. MKNOD, explizite Device-Cgroup-/Nodefreigaben sowie passende seccomp/AppArmor-Regeln | SYS_ADMIN bleibt weitreichend; Capabilities allein ermöglichen weder beliebige Device-Cgroup-Zugriffe noch sicheres dynamisches Hotplug. Keine Zusage gleicher Funktion ohne privileged. |
| Separater Gerätehelper | Optionaler langfristiger Dienst mit eng begrenzter Geräte-/Mount-API und eigener Authentifizierung/Autorisierung | Neue Vertrauens- und Namespacegrenze; eigener Auditauftrag. Kein Host-Docker-Socket, keine TrueNAS-Hostmanagement-API als Ausweg. |

Der aktuelle gemeinsame Container teilt den Mountnamespace von Helper und Webserver. Ein eigener Helper-Container benötigt ausdrücklich qualifizierte Mount-Propagation und Freigabe des konkreten Mountbaums. `rprivate` ist im aktuellen Appdata-Bind-Mount absichtlich gesetzt. Es darf nicht pauschal auf bidirektionale Host-Propagation umgestellt werden. Prüffälle: Hotplug/Major-Minor-Wechsel, Neustart, SIGKILL zwischen Mount und Receipt, fremder Mount, SD Read-only, FUSE/Dateisystemtreiber, sichere Auswurfverweigerung und unveränderte Archive.

Ein echtes Standardpaket sollte /appdata als eigenes verwaltetes App-Volume (ix_volume) vorsehen und nur den notwendigen Nutzerspeicher einbinden. Initialisierung/Permission-Check beschränkt sich auf dieses zugewiesene Volume; keine rekursive chmod/chown-Behandlung gemeinsam genutzter Hostpfade. Tatsächliche Rechte, Symlinks, Root-/Mountbindung und Installationsidentität bleiben verbindlich. UID3000 mit tatsächlichem Zugriff für568 ist nicht automatisch Bibliotheksverlust und begründet keine pauschale Startblockade.

## Offizielle Katalogbedingungen

Die [TrueNAS Contributions Policy](https://github.com/truenas/apps/blob/master/CONTRIBUTIONS.md#apps-catalog-inclusion-policy), am03.11.2026 geprüft, fordert Betrieb innerhalb zugewiesener Container-/Storage-/Netzgrenzen. Hostmanagement-/API-Zugriffe und bekannte Datenintegritätsrisiken schließen Aufnahme aus. Technische Konformität garantiert keine Aufnahme; unklare Geräteprofile sollen vorab mit den Maintainers geklärt werden. Die Anleitung beschreibt App-Metadaten, questions.yaml, Jinja-Compose-Template und Testwerte sowie verwaltete Volumes/Permissions-Checks.

Die [offizielle Custom-App-Sicherheitsdokumentation](https://www.truenas.com/docs/scale/26/apps/installcustomappscreens/#security-context-configuration-settings), am03.11.2026 geprüft, beschreibt die weitreichenden Hostrechte von privileged und empfiehlt gezielte Capabilities, soweit möglich. Die [Beitragsübersicht](https://apps.truenas.com/getting-started/contributing-to-apps/) ist der Einstieg für den Katalogprozess. Ein allgemeines Verbot jedes privileged-Profils lässt sich daraus nicht ableiten. Meine Empfehlung ist ein unprivilegierter Standard und eine separat geprüfte optionale Geräteerweiterung, keine Behauptung bereits erfolgter Katalogzulassung.

## Entscheidung / Aufwand

Standardprofil: überschaubares eigenes Paketierungs- und Abnahmeprojekt (Template, verwaltetes Volume, UID568, Start/Login/Import/Archiv-RO/Restart, zwei getrennte Instanzen). Optionales Capabilities-Geräteprofil: deutlich größeres, hardwareabhängiges Projekt. Vorgeschlagene Voranfrage: „Ist ein standardmäßig rootloses Fotoverwaltungsprogramm mit ausschließlich expliziten Storage-Mounts zulässig, und unter welchen Bedingungen kann ein separates optionales SD/USB-Mountprofil aufgenommen werden?“ Diese Anfrage wurde nicht versendet.

Native NFSv4-/ACL- und Hardwareprüfungen wurden in diesem Auftrag nicht ausgeführt. Keine Privilegien-/Composeänderung implementiert.
