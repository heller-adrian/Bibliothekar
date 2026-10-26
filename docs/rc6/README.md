# RC6 – technische Abnahme, noch keine Veröffentlichung

Basis: `34de39fbf4906e0582858d0b7d6a79ec282196c4`, Tree
`f5e2be9e7309668b679b02ffb549ffe0b96399d6`; enthält RC5 und den Praxispatch.
Version `1.0.0-rc.6`. Der exakte Quellvertrag liegt in `qa/release/rc6.json`.

RC6 ergänzt am bestehenden persistenten Prüfauftrag eine atomare Übergabesperre:
Während ein regulärer globaler Import publiziert, bleibt ein überlappender
Prüfauftrag technisch wartend. Nach dessen Abschluss werden Quelle und aktuelle
Katalogkopien vollständig erneut geprüft. Auch eine zwischen Prüfung und
Übergabe geänderte Importgeneration erzwingt eine Wiederholung. Es entsteht
kein zweiter leerer Importauftrag. Unterbrochene Importe bleiben geschützt und
werden durch die bestehende Recovery behandelt. Die Queuearchitektur bleibt
unverändert. Nur `sd_recheck.py` und die zugehörige Claim-Auswahl in `database.py`
erhalten fachliche Änderungen; drei weitere App-Dateien ändern nur die Version.

## Kurze TrueNAS-Probe nach späterer Veröffentlichungsfreigabe

1. Zuerst separate synthetische Test-App mit eigenen privaten DB-/Config-
   Datasets, leerem tatsächlich gemountetem Workspace und eigenem Archiv.
   Automatische englische Verwaltungsordner, Login und echte Erstbibliothek
   prüfen. Ein erreichbarer leerer Hostpfad beweist den beabsichtigten Mount
   weiterhin nicht; Datasetbereitstellung ist Installationsverantwortung.
2. Auf separaten leeren Testdaten historischen F14-Identitätszustand prüfen:
   erneute Einrichtung nur bei angebotener sicherer Qualifikation ausdrücklich
   bestätigen. Mit vorhandenen Bibliotheksdaten, fehlendem Katalog, veränderten
   Mounts oder Retention muss die Neueinrichtung gesperrt bleiben.
3. Zwei unterschiedliche Testquellen mit identischen Medien gleichzeitig prüfen:
   ein Import, zweite Prüfung bereits gesichert. Neue/gemischte Dateien, fehlende
   Kopie, SD read-only, Abbruch und Neustart gegenprüfen. Kein leerer Verlaufseintrag.
4. Desktop/Mobil, DE/EN und Prozentanzeige prüfen; Archivumbenennung, Metadaten,
   Papierkorb/Restore und private Retention an synthetischen Daten nachtesten.

Vor einem späteren Update des bestehenden Datenbestands App und Schreibzugriffe
stoppen. Vollständige konsistente Sicherung von `/database` samt WAL/SHM,
Registry, F14-Verwaltung und Retention sowie `/config` und relevanten Workspace-
Originalen/Journals erstellen und an Kopien prüfen. Startup kann fehlgeschlagene
Restores automatisch finalisieren. Keine laufenden Einzel-SQLite-Dateien kopieren,
keine manuelle Journalbereinigung und kein Clean Slate.

Die dokumentierte private ACL-Vertrauensgrenze für Administratoren/UID568 gilt
weiter; native NFSv4-/ZFS-/SMB-/Hotplug-Abnahme steht aus. SD-Helper benötigt
weiterhin den nachgewiesen geschützten Mountbereich; Katalog-Provisionierung ist
separat. Akzeptierte F13-/F24-Risiken und zurückgestelltes B12 bleiben bestehen.
Linux-PASS ist keine vollständige native TrueNAS-Abnahme.
