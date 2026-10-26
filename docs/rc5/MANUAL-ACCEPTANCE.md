> Prerelease v1.0.0-rc.5; manuelle Plattformabnahme weiterhin erforderlich.

# v1.0.0-rc.5 – manuelle Abnahme

Nur isolierte Testdatasets, synthetische JPEG/RAW/XMP und ausdrücklich gewählte
Wegwerf-Testmedien. Kein Test gegen bestehende Fotobestände. Pro Punkt Ergebnis
PASS/FAIL/BLOCKED mit Logs/Version/Digest notieren. Vor/nach Dateioperationen Pfade,
Dateianzahl und SHA-256 erfassen. Kein Formatieren realer Medien ohne gesonderten Auftrag.

- [ ] **Installation:** SCALE-/Kernel-/ZFS-Version, Image-Digest, Container-Mounts,
  effektive UID/GID/ACLs dokumentiert; nur Port 8080 veröffentlicht, Helper intern;
  tatsächliche Datasetbindung überprüft. UI meldet `1.0.0-rc.5`.
- [ ] **Browser:** Desktop und Mobilansicht, Navigation und Dialoge funktionieren;
  synthetische Ereignistitel `<b>Test & Text</b>` erscheinen als Text, keine zusätzlichen
  DOM-Elemente. F25 bisher nur über Node/HTMLParser geprüft.
- [ ] **Login:** ohne Passwortdatei gesperrt, gültiges Login/Logout, falsches Passwort,
  CSRF/Origin, HttpOnly/SameSite/Secure im tatsächlich verwendeten HTTP-/HTTPS-Profil;
  übergroßer Loginbody kontrolliert 413. Keine Geheimnisse in Logs.
- [ ] **SD:** nur Testkarte; eindeutige Partitionsidentität, Kernel bestätigt RO,
  fremder/RW-Mount wird abgewiesen. Import vollständig per Hash geprüft; eigener
  Mount wird sicher ausgeworfen. Neustart/Hotplug und fehlender Identitätsnachweis
  führen zu nachvollziehbarer Sperre. Keine fremden Mounts übernehmen.
- [ ] **Ordnerimport:** RO-Testquellordner, Duplikate und gleichnamige Fremddatei;
  Quelle/Fremdbytes bleiben erhalten, neue Aufnahme korrekt katalogisiert.
- [ ] **Sortierung:** Ereignis anlegen/ändern, zuordnen und zurücknehmen;
  RAW/JPEG/XMP-Zusammenhang, Herkunft und freie Bestände bleiben konsistent.
- [ ] **Metadaten:** Vorschau, ausdrücklich bestätigte Korrektur, Backup, erneute
  Analyse; zwei überlappende Aufträge sicher koordinieren. Anschließend reguläre
  neue Korrektur möglich, Projektionen in zweiter Testbibliothek stimmen.
- [ ] **Archivierung:** Staging/externen Kopierschritt und vollständige Archivprüfung
  durchführen; fehlende/beschädigte synthetische Kopie blockiert Freigabe.
- [ ] **Arbeitsbereich freigeben:** normaler Erfolg; erkannte externe Archivänderung
  stoppt weitere Löschungen. Warnung/Retrydialog verständlich. Restdateien beim
  ausdrücklichen Retry neu geprüft; bereits gelöschte Dateien nicht als restauriert
  angezeigt. Letzte Race/mmap-Grenze bleibt akzeptiert, keine absolute Garantie.
- [ ] **Papierkorb:** selektiv löschen, nichtleeren Elternordner erhalten, vollständig
  leeren, Restore gegen reservierten Bestand; Originale/Zuordnungen stimmen.
  Synthetischer Symlink-Canary außerhalb des Papierkorbs bleibt unberührt.
- [ ] **Restore:** gleichnamiges Fremdziel bleibt byteidentisch; Konfliktjournal und
  Trashoriginal bleiben erhalten; andere Testbibliothek nutzbar.
- [ ] **Neustart:** App dreimal unabhängig neu starten; konsistente Dateien/Jobs/
  Journale und SQLite (`integrity_check`, `foreign_key_check`), Familien/Claims/Herkunft.
  Ausgewählten Testjob unterbrechen; keine automatische weitere SSD-Löschung.
- [ ] **Storagefehler:** Testmount/Verwaltungsordner zeitweise entziehen; sichtbare
  Warnung und gesperrte betroffene Jobs, keine automatische leere Neuerstellung.

SIGKILL/Containerneustart ist kein Nachweis für physischen Stromausfall oder
ZFS-Dauerhaftigkeit. Fehler mit minimaler synthetischer Reproduktion melden;
bei widersprüchlichen Zuständen keine Journale oder Daten automatisch bereinigen.

Ergebnis dieser Liste ausdrücklich bestätigen, bevor eine stabile Version erwogen wird.

## RC4-Funktionsbasis Schwerpunkt

- Identische SD erneut einbinden: kurze „bereits gesichert“-Rückmeldung, kein 0-Dateien-Normalauftrag. Integrität bewusst prüfen; fehlende Kopie nur im synthetischen Testbestand wiederherstellen. NeueJPG/RAW/Video und Duplikatanzahl vergleichen.
- EN/DE: laufende/historische Meldungen, Bestätigungen, Eject und Vorschläge; echte Namen/Pfade/Rohlogs unverändert.
- Telefon: Tages-/Ereignisauswahl, vollständige geplante und tatsächliche Vorschau, Scrollende/Schließen/Wiederöffnen/Orientierung. Desktopvergleich.
- Archivhistorie: aktuelle Dateien/unkatalogisierte Dateien, Katalogname versus echter Ordner; historische Verifikation aufklappen.
- Beim RC2-Handytest nicht geprüfte Papierkorbregression ausdrücklich nachholen; B12 bleibt offen.

## RC4-Schwerpunkt

- [ ] SD-Hintergrundprüfung über Seitenwechsel/Browser-/Appneustart; vollständige Karte ohne leeren Import, fehlende synthetische Kopie mit sicherem Ergänzungsimport.
- [ ] Automatischer Abschluss sicher belegter fehlgeschlagener Restores beim Worker/Startup: vollständiger Fingerprint, private Retention, Auditbeleg, Originale/Stage/Protokoll und ursprünglicher Fehler bleiben erhalten. Danach reguläres Leeren; private Kopien bleiben. Abweichende Fingerprints, unklare ACLs und fehlende Kopien bleiben gesperrt.
- [ ] Aktiver Restore sperrt alle Löschungen; inaktive Reservation schützt ihre Auswahl, unabhängige Auswahl löschbar; vollständiges Leeren bleibt gesperrt.
- [ ] Alter Ereignistitel über neuen manuellen Auftrag, unveränderte Bildhashes und alte Journale; aktueller Titel überall konsistent.
