# RC14: Importtransaktionen und erhaltene Herkunft

Entwicklungsbasis: v1.0.0-rc.13, 1f59167e3bfcd38928f0ad32e20d88910a15d53a.
Status: Implementierung vorhanden, automatisierte Gesamtabnahme ausstehend.

## Gesicherter Befund und Beweisgrenze

Der NAS-Bericht belegt WAL, busy_timeout=30000, einen fehlgeschlagenen Import
mit 3892 Dateien / 3889 Familien, 3892 journalgebundene Original-Inodes und
keine vorhandenen Zielobjekte. Ein historischer Stacktrace fehlt. Die misslungene
SQL-Abfrage gegen /database ist kein Nachweis eines Datenbankdefekts; der
Appdatenpfad ist /appdata/database. Der konkrete historische konkurrierende
Writer bleibt unbekannt.

Unabhängig davon reproduziert test_reconcile_hash_does_not_hold_catalogue_writer
im unveränderten RC13 deterministisch SQLITE_BUSY: reconcile_central_free_stock
hält BEGIN IMMEDIATE, während SHA-256 gelesen wird. Ein separater WAL-Writer
für Importfortschritt kommt während eines solchen Hashes nicht zum Zug. Auch
reconcile_trash_inventory konnte nach dem ersten UPDATE weitere Dateien hashen.
RC14 verlagert diese Hasharbeit vor den Writer. Zentralbestand und SQL-Snapshot
werden vor der Übernahme erneut geprüft; Änderungen ergeben einen erneuten Scan,
keine Verlustbestätigung. Trash revalidiert die Dateisignatur vor der Übernahme.

SQL-only Fortschritt, Pfadpersistenz und Lifecycle-Upsert verwenden höchstens
3 Versuche mit je 250 ms SQLite-Wartezeit und 50/100 ms Pause. Kein Filesystem-
Callback wird als ganzer Import erneut ausgeführt. Andere Verbindungen behalten
30000 ms; bei fehlgeschlagener Verbindungsinitialisierung wird geschlossen.

## Veröffentlichungs- und Recoveryvertrag

| Zustand | Verhalten |
|---|---|
| Vor Metadaten / ohne beweiskräftiges Journal | Kopien und Protokolle erhalten; keine automatische Publikation oder Herkunftserfindung |
| Metadaten und ursprüngliche Registry vorhanden, Journal geschrieben, 3892/0 | Explizite Prüfung und Fortsetzung desselben Jobs |
| Teilweise renamet, SQL noch alt | Jedes Objekt liegt unter exakt einem seiner beiden journalisierten Pfade mit ursprünglichem Inode/Hash |
| SQL-Pfadcallback scheitert | Ausschließlich verifizierte eigene Renames zurückrollen; fremde Ziele bleiben erhalten |
| Pfadcallback erfolgreich, Job noch nicht completed | Nicht als freier Bestand zählen, nicht als regulären Verlust reconciliieren |
| completed, technischer Incoming-Umschlag noch vorhanden | Nach vollständiger Prüfung nach .import-history verschieben; keine Dateien löschen |
| Widerspruch / unbekannte Datei / anderes Ziel / fehlende Herkunft | 409 mit Ursache; alle Nachweise bleiben bestehen |

Die App bietet in Import & Prüfung für nachweisfähige Fehlimporte „Import prüfen
und fortsetzen“ sowie „Staging behalten und Auftrag schließen“. Die erste Aktion
prüft im Server erneut und setzt dieselbe Job-ID zurück in die Queue. Sie benötigt
weder einen beschreibbaren Quellmount noch eine neue Quellenregistrierung.
Ursprüngliche canonical/source/member/media-Zeilen bleiben unverändert.
Auch Abbrechen löscht keine kopierten Originale und keine Herkunft mehr.
Ohne ausreichende Nachweise ist Fortsetzung bewusst gesperrt; ein fehlendes
Journal wird nicht aus vermuteten Inodes neu erfunden.

Die Anzeige ermittelt freie Familien aus abgeschlossenen Jobs, tatsächlichen
regulären Dateien an sicheren Pfaden und den Bibliotheksclaims. Sie ist keine
Autorisierung für Mutationen: deren stärkere Hash-/F14-Prüfungen bleiben bestehen.
Fehlgeschlagenes Staging und ungeklärte Imports bleiben im Importverlauf sichtbar.

## Bibliothekslebenszyklus

Neue Zusatzbibliotheken erhalten einen NFC-normalisierten lesbaren Workspace-
Namen aus dem Anzeigenamen. Die technische Bibliotheks-ID behält ihren bisherigen
Algorithmus. NFKC/Casefold-Kollisionen werden abgelehnt, die Anlage erfolgt exklusiv
über einen geprüften Eltern-Deskriptor. Bestehende Namen bleiben unverändert.

„Deaktivieren“, „Bibliothek entfernen“ und Benutzer-„Abmelden“ bleiben getrennte
Aktionen. Entfernen erfordert REMOVE LIBRARY, eine Zusatzbibliothek mit passender
DB-Identität, einen strikt leeren Arbeitsordner, ein echtes RO-Archiv und keine
ungeklärten Jobs/Operationen. Besitzclaims dürfen nur bei verifizierten archivierten
Katalogdateien freigegeben werden. Registrytombstone und vollständige alte Claims
werden in derselben SQLite-Transaktion als Retirementreceipt gesichert; nur die
lebende Claimbelegung endet. Quellenidentitäten, Originalmitglieder, Ereignisse,
Dateien, Datenbank und leere Workspace-Hülle bleiben erhalten.

F14 protokolliert die Registrymutation mit eigener ID. Ein Absturz nach Registry-
Commit bzw. Generationserhöhung wird ausschließlich anhand dieses Receipts und
der unveränderten Bindings/Generationen abgeschlossen. Widersprüche sperren.
Die leere Hülle bleibt reserviert; für eine neue Bibliothek einen anderen Namen
wählen. Kein rekursives Workspace-Löschen, keine event.json-Rekonstruktion.
Wiedereinzug ausschließlich als gewöhnlicher Folder Import über einen ausdrücklich
autorisierten RO-Quellmount. Alte Herkunft bleibt historisch erhalten.

## Unveränderte Grenzen

Speicherersatz und bestätigter Verlust nutzen weiterhin den RC13-Reparaturvertrag.
Der optionale Stagingnachweis gilt nur für neue Bibliotheksregistrierung bzw.
Deregistrierung; Speicherersatz und Stammordnerverschiebungen erhalten ihn nicht.
Authentifizierung, F14, ACL-Vertrauensmodell, Archiv-RO und Herkunftssicherung
bleiben erforderlich. Zusätzliche Benutzerrechte des Hosts sind weiterhin Teil
der bereits dokumentierten administrativen Vertrauensgrenze. Native NFSv4-/ZFS-
Abnahme ist NOT_RUN und wird nicht durch Linux-Tests ersetzt.
