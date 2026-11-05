# RC14 – abschließender automatisierter Abnahmebericht (28.10.2026)

## Exakt geprüfter Quellstand

Anwendungscode: `b43d9fb9d957cb817f74e6fee303b6413d91cd38`

Workflow: [RC14 complete isolated acceptance, Lauf 40751837451](https://github.com/heller-adrian/Bibliothekar/actions/runs/40751837451), Status **SUCCESS**, erster Versuch.

Alle 11 GitHub-Actions-Artefakte wurden vollständig heruntergeladen und ihre Originalinhalte überprüft. Dies ist die finale Evidenz für diese Freigabe, nicht der veraltete Zwischenstand aus früheren Testberichten.

| Gate | Ergebnis |
| --- | --- |
| Gezieltes Sicherheits- und Onboarding-Gate | 110 PASS |
| Acht Backendpartitionen (279 je Partition) | 2.232 PASS, alle Testknoten genau einmal |
| Chromium RC14 | 147 PASS |
| Chromium RC13-Regressionen | 44 PASS |
| RC14 echte Containerfälle | 2 PASS: Journal, teilweise Veröffentlichung und Bibliotheksrückzug |
| RC13 echte Container-/RC12-Upgradetests | 2 PASS |
| RC12 Container-/Reparaturfälle | 25 PASS |
| RC11/RC10 Migrations- und Crashfälle | 19 PASS |

Sämtliche Containerberichte weisen die Quellcode-Revision aus. Der Journal- und der Teilveröffentlichungs-SIGKILL wurden am tatsächlichen Rückkehrereignis im `kamera-job-worker` mit UID 568 ausgelöst. Der Bibliotheksrückzug wurde nach dem Registry-Commit im AnyIO-Thread unterbrochen. Vorhandene Archiv- und Importdateien blieben ihren geprüften SHA-256-/Identitätsnachweisen zufolge erhalten; die reguläre Wiederaufnahme wurde abgeschlossen.

**Nicht geprüft:** Native TrueNAS SCALE-/OpenZFS-/NFSv4-ACL-Funktionalität an produktiver Hardware (NOT_RUN). Die RC14-Freigabe ist ein Prerelease, kein Stable-Release.

Der eigenständige Publisher prüft alle Jobs, exakt alle Artefakte, die disjunkte Testabdeckung, Commit- und Paketidentität und das erfolgreiche Docker-Pull-Ergebnis nochmals. Bei Fehlern erfolgt keine Fortsetzung.
