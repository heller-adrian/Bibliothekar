# Historischer Wiederanlaufvertrag – unverändert erhalten

Quelle: Commit `f3cbe4a340114d6dc264e548aeadf2228ebe4028`,
`tests/backend/test_0476_archive_recovery_and_release.py`.
Die beiliegende `.py.txt`-Datei enthält das vollständige ursprüngliche Modul bytegleich.
SHA-256: `7701a770ed6b5d846689aedf22c84fc3ec1cd1631a5278052fe0e112dc689b91`.

Der alte Test `test_0476_release_task_survives_interruption` erwartete nach
`recover_releases()` eine automatisch beanspruchbare Aufgabe mit derselben ID.
Dieser Vertrag scheitert im dokumentierten Linux-Lauf 38750118904 an
`claimed["id"]`, weil `claim_release()` None liefert. Der frühere QA-Bericht
und dessen JUnit/XML bleiben unverändert; das Folgepaket enthält eine Kopie
des historischen vollständigen JUnit-Ergebnisses.

Der Nutzer hat ausdrücklich eine neue Regel genehmigt: Nach Unterbrechung
keine automatische weitere Löschung. Erst eine neue ausdrückliche Anfrage
mit neuer Aufgaben-ID und vollständiger erneuter Prüfung darf fortsetzen.
Die reguläre Regression prüft diesen Vertrag und behält die bisherigen
Abschlussassertions nach der ausdrücklich neu angeforderten Aufgabe bei.
Die historische Datei ist keine regulär gesammelte Regression und wird
weder als PASS, SKIP noch XFAIL gezählt. Sie ist kein offener Produktfehler
unter dem neu genehmigten Vertrag. Die F13-Verlustreproduktionen bleiben
separat unverändert und melden ihre strengen Erhaltungsassertions weiter FAIL.
