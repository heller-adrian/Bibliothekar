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

Abschlusskorrekturen lokal: 54 RC11-Tests bestanden (159,04 s); anschließend zwei gezielte Pfadmeldungsprüfungen bestanden. Die abschließende gemeinsame Matrix mit Bootstrap, Migration, ACL-Grenzen und privater Retention bestand im isolierenden Harness mit **108 Tests**, 5 Warnungen, **370,87 s**. Quellcode enthält dabei die einheitliche Vertrauensgrenze ohne implizite Aufnahme eines fremden Mountbesitzers.

Aktueller Implementierungscommit: `0eb040ddd2cebe44ec6449be5b29431e23498ca6`. Abschließende Linux-Abnahme: https://github.com/heller-adrian/Bibliothekar/actions/runs/40491103384 (Ergebnis noch offen). Vorheriger Entwicklungslauf: https://github.com/heller-adrian/Bibliothekar/actions/runs/40488694204.

Der Containerlauf prüft die tatsächlich ausgelieferte Onboarding-HTML-Seite und führt die Bibliotheksregistrierungen mit authentifizierten HTTP-/CSRF-Anfragen aus. Eine grafische Browserautomatisierung oder native TrueNAS-Prüfung wird dadurch nicht behauptet.

## Fortsetzung für den RC11-Prerelease

Die Linux-Matrix am Appstand `1e084e5b7185cddd02bb0fb2e033b4a9127f7afe` bestand vollständig: **151 Basis + 57 Bootstrap + 52 Retention + 71 History = 331 Tests**. Belege: https://github.com/heller-adrian/Bibliothekar/actions/runs/40496761565. Der damalige Containerteil scheiterte an einem QA-Beobachter, der als fremde Host-UID private 0700-Dateien lesen wollte. Die Korrektur liest unter der tatsächlichen App-UID im Container; keine private ACL wurde für Tests gelockert.

Weitere Container-Diagnose: Ein durch `--entrypoint python` zum Namespace-PID1 gemachter administrativer Prozess konnte den vorgesehenen selbst gesendeten SIGKILL nicht als normalen Prozessabsturz modellieren. Der QA-CLI läuft nun als Kind des originalen `tini` und verlangt ausdrücklich PID ungleich 1. Die normale Web-Abnahme verwendet weiterhin den originalen Supervisor. Referenzen: [Linux PID namespaces](https://www.man7.org/linux/man-pages/man7/pid_namespaces.7.html), [tini](https://github.com/krallin/tini).

Die Regressionen werden nur bei nachgewiesen unverändertem App-/Test-/Abhängigkeits-/Regressionsstand wiederverwendet. Der gezielte Containerworkflow prüft die tatsächlichen erfolgreichen Originaljobs, sämtliche JUnit-Fälle ohne Fehler/Skip und eine strenge Git-Diff-Allowlist für ausschließlich Container-QA/Workflow/Dokumentation. Er archiviert diese Zuordnung als `reuse-proof.json`. Das ist kein erneut ausgeführter Regressionslauf am späteren QA-Commit.

**Abschließendes Ergebnis:** https://github.com/heller-adrian/Bibliothekar/actions/runs/40513323411 — erfolgreich. Abgenommener Quellstand `d275b4a98735ce87aab57820c61c4b0cf355596e`. Alle **19 realen Linux-Containerfälle bestanden**, einschließlich administrative Receipt-SIGKILL als PID7/UID568/GID568, RC10-completed-Lücke, 14 Bootstrap-Persistenzgrenzen, erste/zweite Bibliothek, Neustarts und unveränderte RO-Archive. Die reale RC10-Reservationsvorlage wurde in allen Migrationsfällen mit erhaltener ID und unveränderten Rollenbindungen abgeschlossen. Die 331 unveränderten Regressionen sind über den beschriebenen Wiederverwendungsnachweis gebunden.

Native TrueNAS-/ZFS-/NFSv4-Abnahme bleibt **NOT_RUN** und folgt ausdrücklich nach Veröffentlichung des Test-Prerelease. Kein vollständiger neuer Backend-Gesamtlauf und kein physischer SD-Karten-/NAS-Test werden behauptet. Der Release enthält einen separaten abschließenden TEST-REPORT.md und die unveränderten Originalbelege mit Prüfsummen.
