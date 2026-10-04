# Release-Verfahren

Bibliothekar verwendet zwei klar getrennte Kanäle.

## Entwicklung

Entwicklung und Abnahme erfolgen auf `patch/<version>`.

Ein Push auf einen Patch-Branch:

- führt die vollständige Backend-QA aus,
- baut ein GHCR-Testimage,
- veröffentlicht einen Branch-Tag wie `patch-0.40.2`,
- verändert weder `latest` noch den stabilen GitHub-Release.

## Veröffentlichung

Der freigegebene Commit wird nach `main` übernommen.

Ein erfolgreicher Publish-Lauf auf `main`:

1. validiert Compose und führt die vollständige Backend-QA aus,
2. liest die Version aus `app/__init__.py`,
3. baut genau diesen Commit,
4. veröffentlicht
   - `ghcr.io/heller-adrian/bibliothekar:latest`,
   - `ghcr.io/heller-adrian/bibliothekar:<version>`,
   - `ghcr.io/heller-adrian/bibliothekar:v<version>`,
5. setzt den Git-Tag `v<version>` auf denselben Commit,
6. erstellt bzw. aktualisiert den GitHub-Release als stabilen Release.

`latest` wird ausschließlich von `main` geschrieben.

## Versionsregel

Vor einer Freigabe muss `app/__init__.py` exakt die neue SemVer-Version enthalten, zum Beispiel:

```python
__version__ = "0.40.2"
```

Patch-Branches dürfen dieselbe Versionsnummer während der Abnahme tragen. Erst die Übernahme nach `main` macht sie zum stabilen Release.

## TrueNAS

Normale Installationen verwenden:

```text
ghcr.io/heller-adrian/bibliothekar:latest
```

Für Rollback oder reproduzierbare Installationen kann stattdessen ein fester Tag verwendet werden:

```text
ghcr.io/heller-adrian/bibliothekar:0.40.1
```
