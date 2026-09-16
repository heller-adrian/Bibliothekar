# Current State

Stand: 2026-09-16

## Produkt / QA

- Produktversion unter Test: `0.21.2`
- Produkt-Commit: `627c5515e533e167e45354ccaa71f988f104ae08`
- QA-/Harness-Stand: `9cfd760663b512dcf2ef57aed71bb3169edb6932`
- Produkt-Image: `ghcr.io/heller-adrian/bibliothekar@sha256:27554d9f6cc2b8a67f77cf01e856b837423974dca0cb6d6e03e8bc5cdb5dddb6`
- Aktiver frischer QA-Lauf: `BIBLIOTHEKAR_0.21.2_FRESH_20260916_173524`
- Isolierte QA-App: `127.0.0.1:31044`
- Produktivbibliothek und Produktiv-DB sind im QA-Container nicht eingebunden.

## Agentenarchitektur

Verbindlicher Workflow:

`workspacecontroller -> qa-thinker PLAN -> nas-agent EXECUTE -> qa-thinker REVIEW -> workspacecontroller`

- `qa-thinker`: Qwen3.8-27B-DFlash2, `reasoning_effort=medium`, analytischer Planner/Reviewer, nur Kanban-Lifecycle-Tools.
- `nas-agent`: Qwen3.8-27B-DFlash2, `reasoning_effort=none`, operativer Executor.
- `workspacecontroller`: Orchestrierung und Nutzerkommunikation.

Der Thinker-Review ist bindendes Gate. Executor-PASS ist nicht autoritativ.

## Bestätigter Architekturtest

Canary 2 (`t_4b1921b0`, run 26) prüfte die früheren Executor-PASS-Bewertungen T004/T007/T008 und stufte alle drei korrekt als `RETEST_REQUIRED` ein.

Danach wurden PLAN (`t_10b7fa9b`, run 27) und PLAN-REFINEMENT (`t_e022db6a`, run 28) erfolgreich mit dem neuen Thinker durchgeführt.

## Aktueller Arbeitsstand Phase A

Phase A wurde einmal ausgeführt. Der ursprüngliche Executorbericht enthielt methodische Fehlbewertungen bei T004, T007 und T008. Diese drei Tests werden jetzt mit der neuen Architektur korrekt nachgetestet.

Der Code-Review ergab zusätzlich eine technische Voraussetzung für T004/T007: Incremental-Historie hängt an `source_device_id`; diese existiert für `root_key="removable"`, nicht für normale `saved`-Ordnerquellen. Deshalb sollen die Retests mit getrennten virtuellen removable-QA-Quellen erfolgen.

Geplante Retest-Quellen:

- T004: `QA_SD_T004`
- T007: `QA_SD_T007`

T008 wird in `PRE -> ADMIN-RESTART -> POST -> REVIEW` getrennt, weil der nas-agent keine Dockerrechte erhalten soll.

## Sicherheitsregeln

- keine Tests gegen reale Kamerabibliothek oder Produktiv-DB
- keine Änderungen am alten normalen NAS-Checkout
- keine Codefixes/Commits/Deployments durch Hermes-QA
- keine persistenten Dockerrechte für `hermes`
- keine zusätzlichen automatischen Deployment-Backups
- Run 19 bleibt als diagnostische Evidence erhalten und wird nicht fortgesetzt
