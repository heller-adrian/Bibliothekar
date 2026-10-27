# RC11 Abnahmeprotokoll

Diese Datei wird mit dem abschließenden Quellstand und den tatsächlich ausgeführten Ergebnissen vervollständigt. Keine native TrueNAS-Freigabe aus synthetischen Ergebnissen ableiten.

## Vorheriger Ausgangsstand

Die unveränderten sechs RC10-Zieldateien am Commit c8e078ee wurden vor der Implementierung lokal isoliert ausgeführt: 151 bestanden, 6 Warnungen, 138,40 Sekunden, macOS/Python 3.12.13. Originalcode und Testdaten lagen getrennt; keine produktiven Pfade wurden beschrieben.

## Reproduzierbarer RC11-Lauf

Die Zieldateien stehen in `qa/rc11/targets.json`. Der vorhandene Harness verwendet ausschließlich neu erzeugte Pfade unter RUNNER_TEMP, blockiert unzulässige SQLite-Ziele und beendet verwaiste Testprozesse.

```sh
RUNNER_TEMP='<neues isoliertes Testverzeichnis>' \
PYTHONDONTWRITEBYTECODE=1 \
python qa/f14/linux/run_linux.py "$PWD" targets qa/rc11/targets.json
```

Der Docker-Abnahmelauf wird einmal nach den Regressionen aus demselben Commit gebaut. Er verwendet den unveränderten Supervisor, echte UID/GID 568:568, tatsächliche RO-/RW-Bind-Mounts, echte Anmeldung mit CSRF, erste und zweite Bibliothekserstellung sowie Neustarts. QA-Faultobserver werden ausschließlich als separate read-only Testdateien gemountet; Dockerfile kopiert sie nicht ins Produktimage. Es gibt kein Auth-, Mount- oder ACL-Testbypass im Containerabnahmepfad. Das Image wird nicht in eine Registry veröffentlicht.

Die NFSv4-XDR-Unittests prüfen bekannte und unbekannte ACL-Dokumente, Vererbung und administrative Grenzen als synthetische Bytes. Die Ubuntu-Bind-Mounts stellen kein natives TrueNAS-ZFS bereit. Der Containerbericht führt das native Gate ausdrücklich als NOT_RUN, niemals als PASS.

## Noch erforderliche manuelle Gates

- Native ZFS-XDR-Abfrage als Web-UID im tatsächlichen TrueNAS-Container, Vergleich mit dem NAS-Referenzbefund.
- Unsichere private ACL blockiert einschließlich Elternrechten; nach administrativer Absicherung erfolgreiche Qualifikation.
- Gemeinsame Workspace-ACL unverändert; kein neues aktives Workspace-Lock.
- Isolierte Migration einer konsistenten Sicherung des blockierten RC10-Standes und vollständiger Webablauf.
- Erst anschließend gesondert freigegebener produktiver Wiederaufnahmeversuch; kein Clean Slate.

## Lokale Ergebnisse vom 27. Oktober 2026

- Unveränderter RC10-Ausgangsstand: **151 bestanden**, 6 Warnungen, 138,40 s.
- Erweiterte lokale Matrix `combined-2`: **325 bestanden**, 6 Warnungen, 874,77 s, macOS/Python 3.12.13. Während dieses Entwicklungsdurchlaufs wurden abschließende Absicherungen ergänzt; er ist deshalb kein Beleg für den endgültigen Commit als Ganzes.
- Danach gezielt: vier Tests zu Versions-/Schemaidentität, fehlender Konfiguration, verlorenem Kontrollstate bei altem Lock und expliziter Bestandsübernahme bestanden.
- Ein direkt gestarteter Entwicklungs-Testaufruf ohne PYTHONPATH scheiterte beim Import der Kindprozesse (`ModuleNotFoundError: app`). Dies war ein Aufruffehler; der dokumentierte Harness setzt den Modulpfad. Dieser Lauf wird nicht als Abnahme gewertet.

Der Linuxlauf ist auf den exakten Commit festgelegt und wird nach Abschluss hier mit Ergebnis und Grenzen ergänzt.

Für native Migrationstests einen **eigenen RC10-Teststart auf isolierten TrueNAS-Datasets** erzeugen und dessen tatsächliche Bindings erhalten. Eine Dateikopie oder ein Datasetklon einer produktiven Sicherung kann Geräte-/Inodeidentitäten ändern; eine solche Kopie ist nicht ohne Weiteres eine wiederaufnehmbare Installation. Die Tests dürfen ihre synthetische Fixture auf lokale Testidentitäten umsetzen. Dieses Vorgehen ist keine Erlaubnis, produktive Bindings manuell umzuschreiben.
