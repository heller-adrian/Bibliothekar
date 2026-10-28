# RC13 Fortschritt

Basis: v1.0.0-rc.12 / 671d7e7eb96ff493ae51720bb2769eccd8f9048f.
Branch: release/v1.0.0-rc.13. Kein produktiver Zugriff.

- Beide Auftragsdokumente gelesen, alle 20 Originalscreens einzeln gesichtet.
- P0: bestätigte zentrale Löschung verkürzt `files`; Startup fingerprintet diese
  als vermeintlich neue Herkunft. RC12-Reproduktion: Partialverlust blockiert;
  Ganzfamilienverlust mit entfernten Audits wird hingegen nicht geprüft.
- Read-only Herkunftsqualifikation implementiert: ursprüngliche Member/Fingerprint
  bleiben erhalten; Fehlbestände benötigen zu Job/Familie/Hash passende Löschbelege.
  Neue Löschbelege enthalten zusätzlich ursprünglichen Pfad/Hash/Größe.
- `control_file_invalid`: deterministischer Austausch nach JSON-Lesen vor zweiter
  ACL-Prüfung reproduziert. Wiederholung nur bei State + entkoppeltem alten FD +
  nachweislich anderem aktuellen Inode; vollständige neue Sicherheitsprüfung.
- Tests/Implementierung laufen. Noch keine vollständige Abnahme/Veröffentlichung.
- Nächster Schritt: Herkunftsgegenbeispiele, Projektionen/zweite Bibliothek,
  Bildschirmkorrekturen und vollständige isolierte Testläufe.

Zwischenstand nach Umsetzung: Herkunfts-/UI-/Recovery-/JS-Gate lokal 62 PASS;
gezieltes F14-/Herkunfts-/Archiv-Gate 50 PASS. Erste Chromium-Matrix 28 PASS;
Erweiterung auf Rückänderung und Statusanzeige läuft. Vollständiger macOS-Lauf
enthält erwartete Linux-inotify-Grenzen und alte Fixture-/Compose-Verträge;
angepasste Verträge werden erneut geprüft. Vollständige Linux-Abnahme mit acht
lückenlosen Dateipartitionen und echtem RC12→RC13-Containerupgrade vorbereitet.
Noch kein Tag, kein Release, kein Image veröffentlicht.

Linux-Lauf 40607188501 auf b14729c5: Chromium 44 PASS. Erste fertige
Backendpartition: 270 PASS, ein veralteter DOM-Stub für die neue Schließen-Schaltfläche
fehlgeschlagen. Stub ergänzt, keine Sicherheitsbedingung geändert.
Weitere lokale Befunde: tatsächlicher SIGKILL unmittelbar nach erster
Quellfamilienregistrierung lässt noch keine lokalen Files/Member zurück. Dieser
unvollständige Nachweis wird jetzt ausschließlich bei exakt passender offener
Importreservation und Job-/Quell-/Generations-/Bindingprüfung erhalten. Es wird
keine Mitgliedschaft vervollständigt und keine Operation abgeschlossen.
Ein solcher Import bleibt ungeklärt; der RC12-Appdaten-Operationsaudit wird nicht
umgangen. Folgeprüfung: 23 PASS (Herkunft, fünf Projektions- und fünf
Metadaten-SIGKILL-Fälle), zusätzlich 14 PASS für Herkunft und Anzeige-Gate.
Die übrigen Linuxpartitionen laufen noch; noch keine Container-/Releasefreigabe.

Fortsetzung 28.10.: Alle acht fehlgeschlagenen Gruppen aus 40607188501 sowie
Artefakte ausgewertet. Alte UI-/Versionsverträge aktualisiert; zu breite
Zählerübersetzung auf konkrete vollständige Texte begrenzt. Deskriptor-relative
Race-Fixtures korrigiert und fehlgeschlagene/symlinkartige Kontrollöffnungen
präzise abgefangen. Linux-Dateisystemtyp wird auf jedem gehaltenen FD mit
fstatfs bestimmt; kein Cache und unveränderte ACL-/Identitätsprüfungen.
Gezielt lokal: UI 16 PASS; Herkunft/F14/Bootstrap 95 PASS, ein ausschließlich
Linux-spezifischer ABI-Test auf macOS SKIP; fünf zuvor langsame Lifecycle-/Trash-/
Sortier-Recoveryfälle 5 PASS ohne bedingten Recovery-Skip. Chromium-Matrix erneut
44 PASS. Neuer Linuxlauf führt zuerst ein gezieltes Fehler-/Sicherheitsgate aus,
dann alle acht vollständigen Backendpartitionen und die echte Containerabnahme.
Keine Veröffentlichung erfolgt. Nächster Schritt: Linuxgate, vollständige
Abnahme und Fehlerkorrekturen anhand der tatsächlichen Containerbelege.

Linuxlauf 40654740807 auf ad73cf38: gezieltes Fehler-/Sicherheitsgate
64 PASS ohne SKIP (einschließlich echter Linux-fstatfs-ABI, alter Timeouts,
F14-Abschlussbelegen und Sortier-Recovery); Chromium 44 PASS. Die acht vollständigen
Backendgruppen laufen. Veröffentlichung weiterhin gesperrt bis zum vollständigen
Backend- und Containerergebnis. Praktische Anleitung in TRUENAS-TEST.md ergänzt.

Abschließender UI-Abgleich: verbliebene englische SSD-Formulierungen einschließlich
Backend-Freigabehinweis auf Arbeitsbereich/Workspace korrigiert; 21 gezielte
UI-/Lokalisierungstests PASS. Die bisherige Browserfixture entfernte auf der
Reparaturseite auch deren eigenen Sprachcode. Jetzt läuft das tatsächliche
Seitenskript mit echten EN-/DE-Schaltflächen. Dabei Sprachzustand der lokalen
Recovery-Texte mit der allgemeinen I18n-Engine synchronisiert; ausschließlich
Darstellung, unveränderte Reparaturrequests/-bestätigungen. Chromium erneut
44 PASS einschließlich beider realer Sprachwechsel und erwarteter Ordnernamen.

Letztes lokales UI-/QA-Gate: 23 PASS; Chromium 44 PASS mit Prüfung jedes
Sprachwechsels. Gegenprobe ohne Sprachzustands-Synchronisation reproduziert
falsch englischen Text nach DE-Wechsel. Keine Änderung an Reparaturautorisation.
Die vollständige Linuxabnahme wird für diesen letzten UI-Stand erneut gestartet.
Lange Crashdateien werden jetzt nach gesammelten Test-IDs statt ganzen Dateien
verteilt; Manifestprüfung muss über alle acht Gruppen genau jeden Test einmal
nachweisen. Frühere Gruppenergebnisse werden nicht als abschließende Abnahme
dieses neuen Stands ausgegeben.

Kopierknopf zusätzlich für normale NAS-HTTP-Ursprünge abgesichert: falls die
Clipboard API fehlt oder verweigert wird, selektierter temporärer Textbereich
im Dialog als Fallback; keine Reparaturaktion. Browser prüft den Fallback mit
ersetzter Zwischenablageschnittstelle ohne Zugriff auf die Systemzwischenablage.

Finaler automatisierter Lauf: 40658249648 auf 3657f5dc.
Gezieltes Linuxgate: 67 PASS, keine SKIPs; Chromium: 44 PASS.
Vollständige Sammlung lokal geprüft: 2.188 Test-IDs in 253 Backenddateien.
Alle acht Nodepartitionen laufen; Containerabnahme und Veröffentlichung stehen
noch aus. Keine produktiven Systeme angesprochen. Nach bestandenem Gesamtlauf
nur Abschlussdokumentation ergänzen, identischen App-/Teststand nachweisen,
Prerelease/Image veröffentlichen und tatsächlichen Pull prüfen.

Folgelauf 40658249648 vollständig ausgewertet: sieben Fehler in fünf Gruppen,
Details in CI-FAILURES.md. Korrigiert wurden Laufzeitisolation der Testfixtures,
SSD-Gegenprobe mit eigenem Crashzustand, getrennte F15-Phasen und alte DOM-/Text-
Erwartungen. Drei Package-C-Gegenproben und beide F15-Phasen bestehen lokal;
Linux-inotify bleibt zwingend für SSD. Zusätzlich prüft die echte RC13-Docker-QA
nach jedem registrierten Neustart ausdrücklich geschützte Papierkorboperationen,
statt allein Storage-ready als Nachweis zu verwenden. Kein Produktguard geändert.

Abnahme fa803ca7: vollständiges Backend 2.189 PASS in acht Gruppen, gezieltes
Gate 101 PASS, Chromium 44 PASS. Alle heruntergeladenen JUnit-/inkrementellen
Ergebnisse und Node-Manifeste unabhängig geprüft: exakt vollständige disjunkte
Abdeckung, keine Fehler oder SKIPs. Containerjob wurde zunächst vor Runnerstart
von GitHub wegen Actions-Kontingent gesperrt. Nach Erneuerung durch den Benutzer
nur den Containerjob erneut gestartet; vorhandene erfolgreichen Belege erhalten.
Aktuell echter Imagebau und Supervisorabnahme, Veröffentlichung weiterhin offen.
