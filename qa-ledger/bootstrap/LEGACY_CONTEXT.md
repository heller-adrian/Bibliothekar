# Legacy Context (Bootstrap, nicht autoritativ)

Diese Datei wurde aus früheren Projektgesprächen rekonstruiert. Sie dient nur dazu, bereits geleistete Arbeit nicht zu verlieren. Sie ist **kein Ersatz für Thinker-geprüfte QA-Evidence**.

## Daten-/Workflow-Grundsätze

- Kamerabibliothek und Produktiv-DB dürfen nicht als QA-Ziel verwendet werden.
- Arbeitsbereich dient Import/Prüfung/Sortierung; Übernahme in Bibliothek bleibt bewusst kontrolliert.
- Ereignisse haben Name, Zeitraum und Segment-/Tageslogik; `event.json` soll portable Ereigniswahrheit tragen.
- RAF bleibt erhalten; Immich-Linkregeln behandeln RAF und Export-JPEGs bewusst unterschiedlich.
- kein automatischer Move nach Übernahme; manuelle Prüfung bleibt zentral.
- `Später zuordnen` soll nicht dauerhaft Jahresordner im normalen Arbeitsbereich vermüllen, sondern separat geführt werden.

## Reassignment-/Archiv-Grundsätze

- Herausfallende Familien dürfen nicht unbeabsichtigt ohne Ereignis hängen bleiben.
- Reassignment-Ziele: bestehendes Ereignis, neues Ereignis, Unterereignis, `Ohne Ereignis`.
- Herausnahme einzelner Familien ohne Zeit-/Kontextänderung ist unerwünscht.
- `Ohne Ereignis` ist segmentbasiert; Zeitspanne ist UI-Hilfe, nicht primäre Wahrheit.
- archivierte Ereignisse müssen vor Abschluss erneut prüfbar sein.
- aus einfachen Ereignissen können nachträglich Ober-/Unterereignis-Strukturen entstehen.
- keine Duplikate gleicher Metadaten.

## QA-/Deploy-Grundsätze

- keine DEV-/Test-DB parallel zur realen Produktiv-DB; QA nutzt stattdessen klar isolierte eigene QA-DB.
- keine zusätzlichen automatischen Backups bei Deployments.
- Releases/Deploys nur bewusst; Hermes-QA selbst macht keine Produkt-Codefixes, Commits, Tags oder Deployments.
- QA-Container muss Produktrevision und Image-Digest exakt belegen und Produktivpfade ausgeschlossen halten.

## Hermes-Lernpunkte

- großer Langzeitkontext führte in Run 19 zu Werkzeug-/Retry-Degeneration.
- Phasen und frische Kontexte sind stabiler als eine gigantische Task.
- `nas-agent` mit reasoning none eignet sich als Executor, aber nicht als alleiniger semantischer Reviewer.
- `qa-thinker` mit medium reasoning und Kanban-only hat sich als unabhängiger Plan-/Review-Gate bewährt.

## Noch zu migrieren

Relevante historische Befunde sollen nur dann nach `verified/` übernommen werden, wenn ein Thinker sie ausdrücklich anhand ausreichender Evidence prüft oder ein aktueller Regressionstest sie neu bestätigt.
