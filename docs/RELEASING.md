# Release-Verfahren – Bibliothekar

Es gibt genau zwei getrennte Containerkanäle. **Das Stable-Image `latest` darf erst nach bestandener Freigabeprüfung geändert werden.**

## Entwicklung und Patch-Testimages

- Entwicklung auf einem `patch/*`-Branch; der Branch allein ist **keine** stabile Freigabe.
- Die Backend-QA läuft für Pull Requests oder über `workflow_dispatch`. Ein beliebiger Quell-Push auf `patch/*` veröffentlicht **kein** Image.
- Ein gewöhnliches Patch-Image wird nur nach einer **neu angelegten oder ausdrücklich aktualisierten** Datei unter `.github/release-requests/` über `.github/workflows/publish-patch-request.yml` gebaut. Historische Anträge liegen ausschließlich unter [docs/history/release-requests](history/release-requests/) und lösen keine Builds aus.
- Das Image wird dann ausschließlich mit `patch-<version>` versehen; es überschreibt niemals `latest`.
- Für den Archiv-E2E muss das Testimage aus **genau demselben Commit** gebaut und anhand des OCI-Labels `org.opencontainers.image.revision` kontrolliert werden.

## Stable-Freigabe 1.1.0

1. Führe auf dem Entwicklungsbranch die vollständige **Backend QA** für den Freigabecommit aus. Alle acht Regressionsteile, die vollständige Testabdeckung und die nativen ZFS-Prüfungen müssen bestanden sein. Die P0-Prüfungen einschließlich SD-Karten-Import und Wiederanlauf bleiben Pflicht.
2. Starte **Publish container image** auf dem Entwicklungsbranch mit der ID dieser Backend-QA. Der Workflow baut ein Image unter dem commitgebundenen Patch-Tag, prüft den Digest auf nativem ZFS und prüft das Upgrade von 1.0.0 und RC22 mit den veröffentlichten Images.
3. Führe PR #41 nach bestandener Qualifizierung mit einem Merge-Commit nach `main`. Der geprüfte Commit bleibt Teil der Historie und sein Git-Baum muss mit dem Stand des Merge-Commits übereinstimmen.
4. Starte **Publish container image** ausdrücklich auf `main` mit der ID des erfolgreichen Image-Laufs. Der Publisher prüft Merge, Quellcommit, Backend-Nachweis und Container-Digest. Er setzt die beiden Versions-Tags und veröffentlicht den Stable-Release mit dem geprüften Commit. Anschließend wird `latest` auf denselben Digest gesetzt.

Der Publisher baut bei der Freigabe kein Image erneut. Bestehende Versionstags mit einem anderen Digest werden abgelehnt. Nach einem teilweise abgeschlossenen Lauf prüfe GitHub-Release und Registry-Tags, bevor du denselben freigegebenen Lauf erneut startest. Der Tag `v1.0.0` und die früheren Vorabversionen bleiben als historische Stände erhalten.

## Version und Testpflichten

`app/__init__.py`, die `RELEASE_VERSION`- und `DEPLOYMENT_VERSION`-Konstanten in `app/main.py`, die sichtbare Versionsanzeige und das Compose-Beispiel müssen denselben Entwicklungsstand ausweisen.

Versionsnummer für diese Freigabe:

```python
__version__ = "1.1.0"
```

Ein Entwicklungsbranch mit dieser Nummer ist **nicht** automatisch ein Release. Die Version gilt erst nach dem erfolgreichen Merge in `main` und dem eindeutigen Veröffentlichungslauf als stabil.

## TrueNAS und Wechselmedien

Für installierte stable Custom Apps ist `ghcr.io/heller-adrian/bibliothekar:latest` vorgesehen. Für reproduzierbare Updates/Rollbacks möglichst einen geprüften Image-Digest bzw. festen Versionstag benutzen.

**Neuinstallation:** Maßgeblich ist die aktuelle [Compose-Vorlage](../compose.example.yaml). Sie bindet den persistenten Appzustand nach `/appdata`, den Arbeitsbereich nach `/workspace` und das Kameraarchiv **read-only** nach `/main-library` ein. Optional kann ein NAS-Quellverzeichnis nur lesend unter `/sources/nas` eingebunden werden. Die Host-Path-Variablen heißen `BIBLIOTHEKAR_APPDATA_DIR`, `BIBLIOTHEKAR_WORKSPACE_DIR` und `BIBLIOTHEKAR_MAIN_LIBRARY_DIR`.

**Bestehende ältere Installation:** Historische Konfigurationen können zusätzliche Pfade wie `/config`, `/database` oder `/logs` verwenden. Solche Installationen nicht blind auf die neue Compose-Vorlage umstellen oder gespeicherte Daten verschieben; zuerst tatsächliche Mounts, Datenbankpfade und Migrationsverfahren prüfen und sichern. Alte und neue Instanzen dürfen nicht gleichzeitig dieselbe SQLite-Datenbank öffnen.

**Der SD-Karten-Import direkt über TrueNAS muss funktionsfähig bleiben.** Katalog-Kompatibilität darf nicht durch die stille Entfernung der Geräteerkennung erreicht werden. Der notwendige Gerätezugriff und das privilegierte Helper-Sicherheitsmodell bedürfen einer gesonderten Sicherheits- und TrueNAS-Freigabe.
