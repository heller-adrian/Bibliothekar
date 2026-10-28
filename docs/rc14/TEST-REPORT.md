# RC14 Testbericht – laufende Abnahme

Status: keine Veröffentlichung freigegeben. Native TrueNAS/NFSv4: NOT_RUN.

## Tatsächlich vorhandene Nachweise

- Unveränderter RC13: konkurrierender WAL-Writer während des Zentralbestands-
  Hashes scheitert reproduzierbar. Nach Verlagerung der Hasharbeit besteht die
  Gegenprobe. Das beweist die Codeanfälligkeit, keinen historischen NAS-Stacktrace.
- Lokaler fokussierter Lauf nach Zähler-/Recoverykorrekturen: 53 PASS,
  30,69 s, Python 3.13 / macOS, synthetische Daten. Zusätzlich eine HTTP-
  Bibliothekslisten-Gegenprobe PASS. Überlappende Läufe werden nicht addiert.
- Aktueller lokaler Lebenszykluslauf mit Claimfreigabe/Retirementreceipt:
  23 PASS, 8,15 s. Nachfolgende Identitätsrevalidierung wird noch geprüft.
- Chromium: 44 bestehende RC13-Fälle und 147 RC14-Fälle (EN/DE/EN,
  320/390/1280 px) lokal bestanden. Tatsächlicher Tagesrenderer, tatsächlicher
  I18n-Katalog; keine externe NAS-Verbindung.
- Linuxlauf 40718962941: Browser PASS; gezieltes Gate 82 PASS / 1 TIMEOUT.
  Der neue 3892-Dateien-Test überschritt die pauschalen 90 Sekunden unter
  vollständigem Dateizugriffsaudit. Nur dieser neue Größenfall erhält 300 s.
- Linuxlauf 40720091267 auf 65c56bf985af775516e83c1f698c178911db8c1d:
  gezieltes Gate und Chromium PASS. Acht vollständige Backendgruppen laufen.

## Verpflichtende noch offene Belege

Vollständige disjunkte Backendabnahme, originale Supervisor-Container unter UID
568 mit RW-/RO-Binds, echte HTTP-Anmeldung, RC12-Herkunftsfehlerupgrade,
RC13-Journal-/Teilpublikations-SIGKILL und derselbe Import nach RC14-Upgrade,
Retirementabsturz, normaler Folder Import aus erhaltenem RO-Archiv, zwei Neustarts
und alle bisherigen RC11-/RC12-Speicherreparaturfälle.

Die Größenfixture enthält tatsächlich 3892 Dateien in 3889 Familien; sie ist kein
66,5-GiB-Durchsatzbenchmark. Jeder originale Inode, jede SHA-256 und alle vier
unveränderlichen Ursprungstabellen werden verglichen. Linux-POSIX-ACL-Tests
ersetzen keine native NFSv4-/OpenZFS-Abnahme.

## Bekannte Grenzen

Ohne ein vollständiges Eigentumsjournal bzw. verifizierbare ursprüngliche
Herkunft wird ein früher unterbrochener Import erhalten und verständlich gesperrt;
es gibt keine erfundene Veröffentlichung oder automatische Datenbereinigung.
Bestätigte Quellenverluste behalten ihre ursprünglichen Familien. Neue Claims
und Archiv-Wiedereinzug werden nur über die normalen Zulassungsregeln geprüft.

Quelle, Image-Digest, exakte Abschlusszählungen und erfolgreiche Run-Links werden
erst nach tatsächlich bestandener Gesamtabnahme eingetragen. Ein grüner Browser-
oder Storage-Health-Check ist keine Containerfreigabe.

## Nachfolgende gezielte Korrekturen

Lokaler aktueller Gate-Lauf: **63 PASS, 28,66 s**, Python 3.13/macOS,
`test_rc14_import`, `test_rc14_lifecycle`, `test_rc14_ui`, Konsistenzsemantik,
Archivprojektion sowie sämtliche ungültigen relativen Publikationspfade.
Linuxspezifischer Cross-Filesystem-Test wurde separat auf macOS erwartungsgemäß
mit „BLOCKED: actual Linux second filesystem required“ abgewiesen; kein PASS
behauptet. Er gehört zur vollständigen Linuxabnahme.

Bereits gelesene rote Linuxgruppen aus Lauf 40720091267: veralteter deutscher
Pfadfehlertext, README-Version, synthetisch als queued angelegte fertige Bestände,
Archivprojektion und zwei bisher destruktive Discard-Verträge. Die Textkompatibilität
ist wiederhergestellt; Fixtures kennzeichnen abgeschlossene Veröffentlichungen.
Die Discardtests prüfen nun Verweigerung sowie erhaltene Dateien/Jobs/Journale.
Das bisherige Rot bleibt im Lauf sichtbar und gilt nicht rückwirkend als PASS.
