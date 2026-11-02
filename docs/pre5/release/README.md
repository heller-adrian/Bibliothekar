# Pre.5 – einmaliger, versionsgebundener Publisher

Freigegeben ist ausschließlich b4c3a397843567bfe09b35e82c51d0009d0a71bf. Der explizit autorisierte Push der neuen Workflowdatei auf codex/publish-1.0.0-pre.5 startet den Publisher ohne Registrierung auf main. Der Stable-Publisher und frühere Prereleases werden nicht verändert.

ACCEPTANCE.json bindet die tatsächlich verschiedenen QA-Quellstände, Einzeljobs und ZIP-Digests. Die2579 Backendnodes, alle acht Partitionen und die147/15 Originalnodes werden unabhängig per JUnit/Node-Identität verifiziert. Nach der Backendabnahme dürfen nur die drei exakt gehashten RC14-Recovery-Dateien abweichen; Tests nur um die zwei final geprüften Original-RC14-Negativfälle. UI-Exports/Renderer bleiben bytegleich zur akzeptierten191er-Browserprüfung. Der ältere insgesamt rote Frontendlauf wird ausschließlich als erfolgreicher Frontend-Einzeljob anerkannt.

Vor Tag/Push/Release müssen die21 betroffenen alten/neuen F14-, Metadaten- und SQLite-Negativtests auf dem tatsächlichen Finalcode sowie alle sechs Container-/Supervisor-/90-/4000-/14-iPhone-Abläufe auf dem tatsächlich gebauten Image bestehen. Eingebettete Dateien/Modi, OCI-Index/Plattform/Config/Provenance und tatsächlicher Digest-Pull werden geprüft. Danach Release-Anlagen erneut herunterladen und alle Digests vergleichen.

Paket-Rechte, Privatsphäre, alte Releases, Tags, Images, latest und Stable bleiben durch Vorher-/Nachher-Snapshots geschützt. Fehlende Rechte führen zum Abbruch. Nach einem Teilzustand kein automatisches Wiederholen oder Löschen.


## Kontrollierter Abschluss nach dem Uploadfehler

`complete.py` und `.github/workflows/complete-pre5.yml` arbeiten ausschließlich auf `codex/complete-1.0.0-pre.5`. Der explizit autorisierte Push der neuen Workflowdatei startet den Abschluss auf dem dedizierten Self-Hosted-Runner. Berechtigungen: contents write, packages read, actions read. Keine Docker-/Build-/Push-/Git-Ref-Schreibbefehle. Originalartefakt13175578019 wird unverändert per festem SHA256 qualifiziert; QA-ZIPs, alter Publisherlauf, Tag, kompletter OCI-Graph, alle alten Releases und Sichtbarkeit werden geprüft. Der einzige leere Einzeldatei-Nachweis wird für den neuen Anlagensatz durch QA-SOURCE-IDENTITY.md ersetzt. Das unveränderte Original-ZIP einschließlich leerem Diff und alter Prüfsummen wird zusätzlich beigelegt. Neue Prüfsummen, Draft-Upload mit Digestprüfung, explizites Prerelease ohne latest, danach unabhängiger Download aller Anlagen. Bei vorhandenem Release oder widersprüchlichen Nachweisen stoppen. Keine automatischen Wiederholungen oder Löschungen.
