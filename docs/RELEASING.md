# Release-Verfahren – Bibliothekar

Es gibt genau zwei getrennte Containerkanäle. **Das Stable-Image `latest` darf erst nach bestandener Freigabeprüfung geändert werden.**

## Entwicklung und Patch-Testimages

- Entwicklung auf einem `patch/*`-Branch; der Branch allein ist **keine** stabile Freigabe.
- Die Backend-QA läuft für Pull Requests oder über `workflow_dispatch`. Ein beliebiger Quell-Push auf `patch/*` veröffentlicht **kein** Image.
- Ein Patch-Image wird nur nach einer ausdrücklich eingecheckten Datei unter `.github/release-requests/` über `.github/workflows/publish-patch-request.yml` gebaut.
- Das Image wird dann ausschließlich mit `patch-<version>` versehen; es überschreibt niemals `latest`.
- Für den Archiv-E2E muss das Testimage aus **genau demselben Commit** gebaut und anhand des OCI-Labels `org.opencontainers.image.revision` kontrolliert werden.

## Stand nach Release 1.0.0 (05.11.2026)

Das erste stabile Release `v1.0.0` ist veröffentlicht und bleibt unverändert.
**Ein Commit auf `main` startet nicht mehr automatisch die Image-Veröffentlichung.**
Der vorhandene Stable-Publisher lässt sich ausschließlich durch einen expliziten
`workflow_dispatch` auf `main` starten. Patch-Images verwenden weiterhin die
separate, explizite Release-Request-Datei.

**Wichtige Übergangsgrenze:** Die Stable-Freigabeprüfung in
`.github/workflows/publish-container.yml` ist gegenwärtig noch fest auf den
vollständigen Abnahmelauf für **1.0.0** einschließlich Commit, Baum und Run-ID
gebunden. Sie ist noch kein allgemeines Verfahren für **1.0.1 oder höher**.
Vor dem nächsten stabilen Release müssen die Freigabeprüfung und der
wiederverwendbare vollständige QA-Workflow geprüft, angepasst und erfolgreich
gegen den dann tatsächlich auszuliefernden Commit ausgeführt werden.
Bis dahin darf niemand die bisherige 1.0.0-Qualifikation für einen anderen
Quellstand als ausreichend behandeln.

Alte versionsgebundene Actions-Dateien sind anhand des unveränderten Tags
`v1.0.0` weiter erreichbar; siehe [historische Workflows](history/ci-workflows.md).

## Stable-Freigabe

Vor dem Merge nach `main` **müssen** alle P0-Datenintegritäts-, Sicherheits- und Wiederanlauf-Gates einschließlich SD-Karten-Import erfüllt sein. Grün gemeldete gewöhnliche Backend-Tests ersetzen keine Crash-/Recovery-Abnahme.

Ein genehmigter Stable-Publish:

1. verlangt eine vollständige, quellstandsgenaue Freigabe einschließlich Compose- und Backend-/Recovery-Abnahme; der Publisher verifiziert diese Nachweise, statt bei jedem Stable-Publish selbst alle Tests erneut auszuführen;
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
