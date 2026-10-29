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
2. Die Runner-Verwaltung ist mit der verfügbaren GitHub-Verbindung nicht abrufbar.
   Ein Maintainer muss einen online verfügbaren Runner mit exakt den vier Labels,
   vertrauenswürdigem isoliertem Arbeitsverzeichnis und freigegebenem Dockerzugriff
   bestätigen. Die Prüfumgebung hier ist macOS und bietet weder Docker noch gh.
3. Auf dem Runner werden Python3.12+, Git, gh, Docker, tar, gzip und sha256sum
   benötigt. Der Workflow installiert nichts privilegiert und korrigiert keine
   Rechte. Fehlende Programme, Netzwerk- oder Dockerrechte brechen ab.
4. GITHUB_TOKEN benötigt contents:write, packages:write und actions:read sowie
   Zugriff auf das bestehende Paket. Die Paket-API muss dessen derzeitige
   Sichtbarkeit lesbar liefern. Eine fehlende Berechtigung wird gemeldet;
   Paketfreigaben, Repositorysichtbarkeit und ACLs werden nicht verändert.
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
