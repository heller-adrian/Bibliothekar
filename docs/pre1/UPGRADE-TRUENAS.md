# Bestehende TrueNAS-Custom-App: 1.0.0-pre → 1.0.0-pre.1

Dieses Prerelease korrigiert den CPU-Startfehler. Es benötigt keine
Datenbankmigration, keinen Clean Slate und keine manuelle SQLite-/F14-Reparatur.
Die native TrueNAS-Abnahme steht aus. Bestehende App weiterverwenden.

1. **App stoppen und Zustand sichern.** In TrueNAS Apps die bestehende
   Bibliothekar-App auswählen und stoppen. Wenn alle Appprozesse beendet sind,
   zusammengehörige Snapshots/Sicherungen der bestehenden Appdaten und des
   Workspaces erstellen. Bei mehreren Datasets alle beteiligten Teile im
   gestoppten Zustand sichern. SQLite einschließlich vorhandener WAL/SHM-Dateien,
   F14-/Recoverynachweise und die 14 korrigierten Originaldateien erhalten.
2. **Bestehende App bearbeiten.** Im Apps-Bereich die vorhandene Custom-App über
   Bearbeiten/Edit öffnen. Ausschließlich die Imagereferenz aktualisieren.
   Appdaten-, Datenbank-, Workspace- und zusätzliche Bibliotheksmounts unverändert
   erhalten. Archive weiterhin Read Only; bisherige UID/GID und Rechte beibehalten.
   Keine zweite Instanz mit denselben schreibbaren Mounts starten.
3. **Image einstellen.** Repository `ghcr.io/heller-adrian/bibliothekar`, Tag
   `1.0.0-pre.1`. Bei getrennten Repository/Tag-Feldern keinen SHA-256-Wert als Tag
   eintragen. Falls die verwendete TrueNAS-Version ein Digest-Feld anbietet,
   den Digest aus IMAGE-DIGEST.txt dort eintragen. Bei einer vollständigen
   Imagereferenz bzw. bestehender YAML-Konfiguration die Referenz
   `ghcr.io/heller-adrian/bibliothekar@sha256:…` aus IMAGE-DIGEST.txt verwenden.
   Bei Formularen ohne Digest-Unterstützung den eindeutigen neuen Tag verwenden
   und nach dem Start dessen tatsächlichen Digest prüfen. Soweit angeboten,
   Pull-Policy für dieses Update auf Always setzen. Bestehende GHCR-Zugangsdaten
   beibehalten; Repository bleibt privat, Paketsichtbarkeit wie bisher.
4. **Gerätehelfer bewusst beibehalten.** Den bisherigen Wert von
   KAMERA_SOURCE_HELPER_ENABLED zunächst prüfen. Der Helper wird für tatsächlich
   verwendete physische Wechselmedien-/Mountfunktionen benötigt. Nicht allein
   wegen dieses Hotfixes deaktivieren oder Privilegien verändern. Der Startlog
   meldet, ob der Helper explizit aktiviert oder das Standardprofil verwendet wird.
5. **Speichern und starten.** Auf vollständigen Start warten. Erwartet werden
   `Startup phase …: completed in …s` und danach `Application startup complete`.
   Die Statusanzeige soll von Deploying zu Running/Healthy wechseln. Die App
   muss 1.0.0-pre.1 anzeigen und die bisherigen Bibliotheken bereitstellen.
6. **Installiertes Image verifizieren.** In den App-/Containerdetails, sofern
   angezeigt, den tatsächlichen Image-Digest mit IMAGE-DIGEST.txt vergleichen.
   Die Web-Versionsanzeige allein beweist den Digest nicht. Falls die Oberfläche
   ihn nicht anzeigt, ist dieser ausschließlich lesende Befehl eine optionale
   unabhängige Prüfung (vorher den aktuellen Containernamen einsetzen):

   ```sh
   docker inspect --format '{{.Image}}' CONTAINERNAME
   docker image inspect --format '{{json .RepoDigests}}' IMAGE_ID_AUS_ERSTEM_BEFEHL
   ```

   Der zweite Befehl soll die vollständige RepoDigest-Referenz aus
   IMAGE-DIGEST.txt enthalten. Er verändert keine Dateien, Rechte oder Appdaten.
   Bei Abweichung App stoppen und das Ergebnis melden, nicht manuell bereinigen.

## Praktische Abnahme

- Anmeldung, beide Bibliotheken und Bestandszahlen prüfen.
- Die 14 korrigierten iPhone-JPEGs müssen weiterhin verfügbar sein. Vor dem
  Einsortieren Datum und +13:00 prüfen. Dann den vorgesehenen normalen Retry
  verwenden; keine Datenbank-/Reservationsdateien bearbeiten.
- Nach erfolgreicher Reintegration Aufnahmedatum, Offset, Herkunft und Zielpfade
  prüfen. Ein kontrollierter Neustart muss anschließend wieder gelingen.
- Vorhandene Speicherreparatur und Archiv-Read-Only-Bindung erhalten.
- Bei Stillstand die letzte neue Startphasenmeldung samt Dauer und Appversion
  senden. Die Phase central-stock-migration prüft weiterhin Medienhashes;
  große reale Dateien können zusätzliche Zeit benötigen.

Ein Rückwechsel von pre.1 zu pre behebt den ursprünglichen Startfehler nicht.
Nicht mit gleichzeitigen Instanzen arbeiten. Eine vollständige Rücksicherung
muss Appdaten und Workspace aus derselben gestoppten Sicherung gemeinsam
wiederherstellen; nicht nur einzelne SQLite-/F14-Dateien austauschen.

GUI-Feldnamen unterscheiden sich nach TrueNAS-Version. Grundlage:
https://www.truenas.com/docs/scale/apps/installcustomappscreens/
