# Veröffentlichungsvorbereitung für v1.0.0-pre

## Geprüfte Grundlage

- Anwendung:70c0bb57afa168efec83b1b60245b819b36161ff.
- Dokumentation:30e492574b02579496fbaece8c3acfe657a70009.
- QA:40840603811; elf erfolgreiche Jobs und elf unveränderlich gebundene Artefakte.
- Vorbereitungszweig:codex/prepare-1.0.0-pre-release.
- Workflow:.github/workflows/publish-pre.yml; ausschließlich workflow_dispatch.
- Runner ausschließlich `[self-hosted, Linux, X64, bibliothekar-safe]`.

**Status: vorbereitet; noch keine Veröffentlichungsfreigabe.** Kein Tag, Release,
Registry-Push oder Stable-Update wurde durch diese Vorbereitung ausgeführt.
Der eigene Vorbereitungszweig löst keine erneute vollständige QA aus.

## Vor der späteren Ausführung noch zu bestätigen

1. GitHub benötigt die Workflowdatei für den manuellen Start auf dem Standardzweig.
   main enthält bisher ausschließlich die älteren Workflowdateien. Ein Stub liegt
   unter release/REGISTER-WORKFLOW.yml bereit. Dessen Registrierung erfolgt erst
   nach ausdrücklicher Freigabe, unter den bestehenden Branchschutzregeln.
   Der Stub allein veröffentlicht nichts; beim manuellen Start muss der
   Vorbereitungszweig ausgewählt werden.
2. Runner bestätigt: Der kurze Smoke-Test40886496425 bestand am29.10.2026
   auf bibliothekar-truenas in6 Sekunden mit exakt den vorgeschriebenen Labels.
   Python3.12.3, Node24.22.1, npm11.19.1, ExifTool12.76, gh2.103.3 und Docker29.1.3
   sowie ACL-Werkzeuge sind verfügbar. Dockerzugriff ist auf dieser dedizierten
   VM ausdrücklich vorgesehen. Ein gecachter hello-world-Container lief als
   nicht privilegierter Benutzer, read-only, ohne Netzwerk und Host-Mounts.
3. Auf dem Runner werden Python3.12+, Git, gh, Docker, tar, gzip und sha256sum
   benötigt. Der Workflow installiert nichts privilegiert und korrigiert keine
   Rechte. Fehlende Programme, Netzwerk- oder Dockerrechte brechen ab.
4. Der Smoke-Test bestätigt lesenden Job-Token-Zugriff auf das private Repository,
   den genehmigten QA-Lauf und die bestehende Paket-API. Das Paket ist bereits
   public, das Repository private; beides bleibt unverändert. Für den später
   genehmigten Publisher sind contents:write, packages:write und actions:read
   konfiguriert. Schreibaktionen bleiben bis zur Freigabe ungetestet und werden
   bei fehlenden Rechten abgebrochen; keine Rechte werden automatisch verändert.
5. Der veröffentlichte Versionsname muss in Git, Releases und GHCR noch frei sein.
   Alle anderen Paketpublisher müssen denselben Versionsnamen während dieser
   Veröffentlichung unbenutzt lassen. GHCR bietet hier keine transaktionale
   Compare-and-swap-Zusage gegen unabhängige externe Registry-Schreiber.

## Sichere Registrierung ohne Stable-Veröffentlichung

GitHub dokumentiert die Default-Branch-Voraussetzung hier:
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

Die spätere Registrierung darf den auf main vorhandenen automatischen
Stable-Publisher nicht starten. Ein von den bestehenden Repositoryregeln erlaubter
reiner Registrierungscommit kann nach Freigabe den GitHub-Schalter `[skip ci]`
verwenden. Dieser unterdrückt push-Workflows; die anschließende bewusste
workflow_dispatch-Ausführung bleibt möglich. Bestehende Branchschutzregeln dürfen
hierfür weder umgangen noch deaktiviert werden. Wenn sie diesen Weg nicht erlauben,
ist die Registrierung vorab durch einen berechtigten Maintainer zu klären.
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs

Kein automatischer main-Commit gehört zur jetzigen Vorbereitung. Ein zufälliger
Start auf main trifft nur den ablehnenden Stub. Der echte Publisher akzeptiert
allein den Vorbereitungszweig und die Eingabe `PUBLISH v1.0.0-pre`.

## Prüf- und Veröffentlichungsreihenfolge nach Freigabe

1. Manueller Start mit genannter Eingabe; Self-Hosted-/Branch-/Repo-/Kontextprüfung.
2. Beide freigegebenen Commits und unveränderten Anwendungscode prüfen. Seit dem
   Dokumentationscommit sind nur explizit aufgelistete Publisherdateien zulässig.
3. Elf Original-ZIP-Dateien erneut laden und gegen die bereits im genehmigten
   Dokumentationscommit gespeicherten SHA-256-Digests prüfen. Sichere Extraktion;
   Quelle, XML, disjunkte Testknoten, Browser und Containerberichte nachweisen.
4. Releaseanlagen und exaktes Quellcodearchiv vorbereiten. Existierende Tags,
   Releases oder Imageversionen sowie unklare Registryantworten verweigern.
5. Image aus git archive des Prüfcodes bauen. Keine Appdaten-/Workspace-/NAS-Mounts.
   Alle eingebetteten app-Dateien einschließlich Dateimodus bytegenau vergleichen,
   Versionswert, Linux/amd64 und OCI-Revision prüfen.
6. Git-Tag atomar neu reservieren und ausschließlich1.0.0-pre pushen. Anschließend
   Docker-Pull über den Digest, denselben vollständigen Payload erneut prüfen;
   Image-ID, OCI-Revision, RepoDigests, rohe Registrymanifestbytes und deren
   SHA-256-Digest vergleichen. Paket- und Repositorysichtbarkeit erneut prüfen.
7. Digest in Compose und Anleitungen einsetzen, SHA256SUMS erstellen und prüfen.
   GitHub-Prerelease mit latest=false erzeugen. Alle Releaseanlagen erneut laden
   und prüfen. Der Publisher schreibt kein latest-Image und ändert keine Zugriffe.

Ein Fehler nach der atomaren Tagreservierung kann einen Tag oder ein bereits
hochgeladenes pre-Image ohne fertigen Release zurücklassen. Dann stoppt der
Workflow. Kein erneuter Versuch überschreibt diese Identitäten; kein automatisches
Löschen oder Rollback. Vor einer Fortsetzung muss ein Maintainer den Teilzustand
und die gesicherten Diagnosen prüfen. Dies ist eine Sicherheitsgrenze, kein
automatischer Reparaturauftrag.

## Runner-/NAS-Grenzen

Alle Build-/Releasepfade und Docker-Anmeldedaten liegen in eigenen temporären
Jobverzeichnissen. Container zur Payloadprüfung laufen ohne Netzwerk, ohne
Host-Bind-Mounts, read-only mit UID/GID568 und ohne zusätzliche Capabilities.
Es gibt weder sudo noch Docker-Pruning noch Zugriff auf Produktionsdaten.
Der Runner selbst bleibt vertrauenswürdige Infrastruktur; seine Labels allein
beweisen keine Isolation. Dockerberechtigung darf nicht durch diesen Workflow
an einer ungeeigneten Maschine freigeschaltet werden.

Native TrueNAS-/NFSv4-, physische SD-/USB- und DNG1.7-Abnahme bleiben NOT_RUN.
Ein erfolgreicher Linux-Publisher darf diese Grenzen nicht als PASS umdeuten.

## Kontrollierter Abschluss des vorhandenen Teilzustands

Der erste Publisherlauf 40891738442 hat Tag und Image erfolgreich angelegt.
Er darf nicht erneut ausgeführt werden. Auf `codex/prepare-1.0.0-pre-release`
aktiviert ausschließlich die Eingabe **`COMPLETE v1.0.0-pre`** den getrennten Job
`complete-existing` im bestehenden manuellen Workflow. Dessen Token hat nur
lesende GHCR-Rechte. Dieser Job enthält keinen Build, Image-Push oder Tag-Schreiber.

`complete.py` bindet den Abschluss an den ursprünglichen Tag-Commit
`9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5`, den vorhandenen OCI-Index
`sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b`,
den unveränderten `latest`-Digest und die ursprüngliche Paket-/Repositorysichtbarkeit.
Die elf ursprünglichen QA-Artefakte und das Diagnose-ZIP des ersten Publishers
werden erneut anhand eingefrorener Digests geprüft. Erst nach vollständigem
Digest-Pull, Appdateivergleich und OCI-Prüfung wird der fehlende Prerelease mit
`--verify-tag --prerelease --latest=false` angelegt. Alle Anlagen werden erneut
heruntergeladen und sowohl mit lokalen Bytes als auch GitHubs Asset-Digests verglichen.
Bei jeder Abweichung stoppen; auch einen fehlgeschlagenen Abschluss nicht blind wiederholen.

Die OCI-Prüfung folgt der [OCI-Indexstruktur](https://github.com/opencontainers/image-spec/blob/main/image-index.md)
und dem [BuildKit-Attestationsformat](https://docs.docker.com/build/metadata/attestations/attestation-storage/).
Alle Deskriptoren werden nach Typ, Größe und SHA-256 geprüft; genau ein linux/amd64-
Anwendungsmanifest wird zugelassen. Provenance besitzt unknown/unknown als Plattform
und muss auf genau dieses Anwendungsmanifest verweisen. Die Attestation ist kein
unabhängiger signierter Vertrauensanker. Die Quellidentität wird zusätzlich durch
vollständigen Appdateivergleich, Modivergleich, Version und OCI-Revision belegt.
Docker-IDs aus klassischem oder containerd-basiertem Image Store sind nur zulässig,
wenn sie exakt der geprüften Konfiguration, dem Plattformmanifest oder dem Index
entsprechen; RootFS und Image-Konfiguration müssen zusätzlich übereinstimmen.

Native TrueNAS-/NFSv4-, physische SD-/USB- und DNG-1.7-Abnahme bleiben NOT_RUN;
das eigenständige Verlustabschlussmodell bleibt DEFERRED.
