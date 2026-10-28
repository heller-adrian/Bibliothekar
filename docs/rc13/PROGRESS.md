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
