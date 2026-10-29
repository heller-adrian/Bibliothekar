# pre.1 — Veröffentlichung und Abnahme

Freigegebener Hotfix: 79ab9c1f3c9906723e328873ad790074e3f7b60c.
Dokumentationsstand: 3fb14e6b452d86c68bd5a703c398e793a4e7417d; identischer Anwendungscode.
Versionierter Build: 282aeba2dd8464f30c8484034759cbb0fd8e0823.
Exakte einzige Appdifferenz: __version__ in app/__init__.py von 1.0.0-pre zu 1.0.0-pre.1.
Der QA-Versionsvertrag wurde entsprechend angepasst. Keine Funktionsänderung.

Akzeptierter Hotfixlauf: https://github.com/heller-adrian/Bibliothekar/actions/runs/40906773810
118 Linux-Regressionsfälle stammen aus dem erfolgreichen Testschritt in Lauf
40904815727. Die Containerabnahme 40906773810 verifizierte dessen eingefrorenes
ZIP, JUnit und Quellgleichheit. Der neue Publisher prüft beide Original-ZIPs
mit ihren SHA-256-Digests und alle Erfolgsbedingungen erneut. Er führt keine
unnötige vollständige Backend-/Browsermatrix aus.

Gedeckte Fälle: 4.000 Familien, neue und bestehende Projektionen, frische
Wiederholungsqualifikation, widersprüchlicher nicht projizierter Hauptbestand,
Herkunfts-/Verlustnachweise, Claims, Metadatenoffsete, F14-SIGKILL und konkurrierende
Operationen. Profil des alten Codes mit 1.000 Familien: 108,295 s; korrigierter
Backfill mit 4.000 Familien: 0,768 s (lokales Python-3.13/macOS-Profil, nicht NAS).
Ursprünglicher realer Linux-Supervisorstart: 5,370 s; Neustart: 6,291 s.

Vor dem neuen Push werden erneut tatsächliche Appdateibytes und Dateimodi gegen
den versionierten Quellstand geprüft. Der neue Container durchläuft erneut
Supervisorstart mit zwei Bibliotheken/4.000 Dateien, UID 568, HTTP-Anmeldung,
Neustart, RO-Archive und 14 erhaltenen korrigierten JPEGs. Zusätzlich wird der
originale RC14-Korrektur-/Wiederaufnahmefall mit 14 +13:00-JPEGs geprüft.
Die tatsächlichen Ergebnisse stehen in pre1-startup-evidence.json und
pre1-pre-evidence.json. Nach Push: echter Digest-Pull, erneuter Bytevergleich,
OCI-Index/Manifest/Konfiguration/Docker-ID/Revision/Provenance-Zuordnung und
unabhängiger Download sämtlicher Release-Anlagen mit Digest-/Bytevergleich.

v1.0.0-pre und seine Anlagen, latest, stabile Releasekennungen sowie
Repository-/Paketsichtbarkeit werden vor/nach verglichen. Bei Fehler stoppt der
Publisher; keine automatische Löschung, Überschreibung oder Wiederholung.

NOT_RUN: native TrueNAS/NFSv4-ACL, physische SD/USB-Hardware, DNG-1.7-Originaldatei.
DEFERRED: eigenständiges Verlustabschlussmodell. Kleine künstliche Mediendateien
belegen keine Startzeit bei großen RAW-Datenmengen. Medienhashprüfungen bleiben aktiv.
