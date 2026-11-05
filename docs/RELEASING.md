# Release-Verfahren – Bibliothekar

Es gibt genau zwei getrennte Containerkanäle. **Das Stable-Image `latest` darf erst nach bestandener Freigabeprüfung geändert werden.**

## Entwicklung und Patch-Testimages

- Entwicklung auf einem `patch/*`-Branch; der Branch allein ist **keine** stabile Freigabe.
- Die Backend-QA läuft für Pull Requests oder über `workflow_dispatch`. Ein beliebiger Quell-Push auf `patch/*` veröffentlicht **kein** Image.
- Ein Patch-Image wird nur nach einer ausdrücklich eingecheckten Datei unter `.github/release-requests/` über `.github/workflows/publish-patch-request.yml` gebaut.
- Das Image wird dann ausschließlich mit `patch-<version>` versehen; es überschreibt niemals `latest`.
- Für den Archiv-E2E muss das Testimage aus **genau demselben Commit** gebaut und anhand des OCI-Labels `org.opencontainers.image.revision` kontrolliert werden.

## Stable-Freigabe

Vor dem Merge nach `main` **müssen** alle P0-Datenintegritäts-, Sicherheits- und Wiederanlauf-Gates einschließlich SD-Karten-Import erfüllt sein. Grün gemeldete gewöhnliche Backend-Tests ersetzen keine Crash-/Recovery-Abnahme.

Ein genehmigter Stable-Publish:

1. prüft Compose und führt alle Backend-Tests aus;
2. liest die neue SemVer aus `app/__init__.py`;
3. bricht **vor dem Docker-Build** ab, wenn `v<version>` schon existiert;
4. baut das Image aus dem freigegebenen Git-Commit;
5. veröffentlicht `latest`, `<version>` und `v<version>` mit zugehörigem Image-Digest;
6. erzeugt einen neuen **unveränderlichen** Git-Tag `v<version>` und anschließend den GitHub-Release. Bestehende Tags oder Releases dürfen nicht heimlich überschrieben werden.

Achtung: Das Publizieren des Images und das Anlegen des Git-Tags sind technisch zwei Schritte. Schlägt der zweite Schritt fehl, muss der Release-Betreiber den Zustand prüfen und korrigieren; keinesfalls einen bereits veröffentlichten Versionstag mit `--force` verschieben.

## Version und Testpflichten

`app/__init__.py`, die `RELEASE_VERSION`- und `DEPLOYMENT_VERSION`-Konstanten in `app/main.py`, die sichtbare Versionsanzeige und das Compose-Beispiel müssen denselben Entwicklungsstand ausweisen.

Beispiel:

```python
__version__ = "0.50.0"
```

Ein Entwicklungsbranch mit dieser Nummer ist **nicht** automatisch ein Release. Die Version gilt erst nach dem erfolgreichen Merge in `main` und dem eindeutigen Veröffentlichungslauf als stabil.

## TrueNAS und Wechselmedien

Für installierte stable Custom Apps ist `ghcr.io/heller-adrian/bibliothekar:latest` vorgesehen. Für reproduzierbare Updates/Rollbacks möglichst einen geprüften Image-Digest bzw. festen Versionstag benutzen.

Bei einem App-/Discover-Migrationslauf die vorhandenen Host-Path-Datasets und dieselben Containerpfade für `/config`, `/database`, `/workspace`, `/logs`, `/main-library` und `/sources/nas` beibehalten. Alte und neue Instanzen dürfen nicht parallel auf die SQLite-Datenbanken zugreifen.

**Der SD-Karten-Import direkt über TrueNAS muss funktionsfähig bleiben.** Katalog-Kompatibilität darf nicht durch die stille Entfernung der Geräteerkennung erreicht werden. Der notwendige Gerätezugriff und das privilegierte Helper-Sicherheitsmodell bedürfen einer gesonderten Sicherheits- und TrueNAS-Freigabe.
