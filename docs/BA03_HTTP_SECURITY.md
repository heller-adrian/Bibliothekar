# BA-03 – Zugriffsschutz der Bibliothekar-Web-App und HTTP-APIs

**Version:** 0.50.0 (Entwicklungsbranch, nicht öffentlich freigegeben).

## Grundprinzip

Bibliothekar startet **ohne voreingestelltes Passwort und ohne anonymen
API-Zugriff**. Alle normalen Seiten und API-Routen werden durch die
zentrale HTTP-Middleware in `app/security.py` geprüft – noch bevor der
Bibliothekskontext ausgewählt oder ein Schreib-Endpunkt ausgeführt wird.

- Anmeldung unter `/login` mit Administratorpasswort; alle Benutzer teilen
  sich zunächst **eine** Besitzerrolle. Getrennte Konten/Rollen sind nicht
  Bestandteil von BA-03.
- Ein starkes Passwort von **mindestens 16 UTF-8-Bytes** muss zur Verfügung
  stehen. Bevorzugte Konfiguration ist eine reine Textdatei, kein
  Geheimnis im Quellcode und keine Standardzugangsdaten.
- Authentifizierte Sessions verwenden zufällige, im Cookie gespeicherte
  Sitzungstoken. Auf dem Server liegt nur deren SHA-256; Cookies sind
  `HttpOnly`, `SameSite=Strict`, `Path=/`, maximal 14 Tage.
  Die Sessions werden nur im Arbeitsspeicher geführt; nach einem Neustart
  ist eine erneute Anmeldung erforderlich.
- Zusätzlich muss jede `POST`-, `PUT`-, `PATCH`- und `DELETE`-Anfrage
  einen passenden `X-Bibliothekar-CSRF`-Header senden und eine zulässige
  Herkunft haben. Die PWA-/Browseroberflächen setzen den Header automatisch
  durch die zentral ausgelieferte Datei `/auth/client.js`; die
  Testfall-Kompatibilität ist explizit auf isolierte pytest-Läufe beschränkt.
- Cross-Site- und Same-Site-but-not-Same-Origin-Anfragen werden abgewiesen.
  Es sind keine permissiven CORS-Regeln konfiguriert.
- Acht fehlgeschlagene Passwortversuche innerhalb von 15 Minuten sperren
  weitere Anmeldungen vom betroffenen Client vorübergehend. Die Sperre
  besteht im Arbeitsspeicher, nicht global über mehrere Instanzen hinweg.
- `/healthz` bleibt für TrueNAS/Docker ohne Anmeldung lesbar.
  Die PWA-Manifestdatei, das öffentliche Logo und das für den Client
  benötigte nichtgeheime JavaScript bleiben abrufbar. Normale
  Bibliotheks- und Statistikdaten sind nicht öffentlich.

## Einrichtung in TrueNAS

1. Im bestehenden Verzeichnis für die App-Konfiguration, also dem
   Host-Pfad, der im Container nach `/config` gemountet wird, eine
   **neue** Datei `admin-password` mit einem individuellen,
   zufällig erzeugten Passwort von mindestens 16 Zeichen anlegen. Die
   Datei darf ausschließlich das Passwort und einen optionalen
   abschließenden Zeilenumbruch enthalten.
2. Datei so berechtigen, dass der Eigentümer beziehungsweise die App
   mit ihrer Web-UID **568** lesen kann, aber andere Benutzer keine
   Leserechte erhalten. Beispielsweise je nach TrueNAS-Dataset-ACL
   die Gruppe 568 zuweisen und nur Gruppen-Leserechte vergeben.
3. Im Compose-/TrueNAS-Custom-App-Umfeld
   `BIBLIOTHEKAR_ADMIN_PASSWORD_FILE=/config/admin-password` setzen.
   Der Beispiel-Compose enthält diese Vorgabe bereits. Alternativ ist
   `BIBLIOTHEKAR_ADMIN_PASSWORD` als direkter Umgebungswert möglich,
   sollte aber wegen Sichtbarkeit in Containerkonfigurationen nicht
   bevorzugt werden. Sind beide gesetzt, gewinnt die Datei.
4. Container neu starten; die Bibliothekar-Oberfläche öffnen und
   anmelden. Der integrierte SD-Kartenimport bleibt unverändert.
   Auf iPhone-Web-App und in Safari kann eine getrennte Anmeldung
   nötig sein, da Home-Screen-Web-Apps separate Cookies besitzen können.
5. Für den Zugriff **außerhalb des lokalen Gerätes** HTTPS über einen
   vertrauenswürdigen Reverse-Proxy oder ein entsprechendes privates
   Netz mit TLS verwenden. Dabei
   `BIBLIOTHEKAR_COOKIE_SECURE=true` einstellen und sicherstellen,
   dass der Reverse-Proxy die Host-/Scheme-Informationen korrekt an
   die Anwendung weitergibt. Ein unverschlüsselter LAN-Zugriff
   über HTTP schützt Passwort und Cookie **nicht** vor Mitschneiden.
   **Port 8080/30044 nicht direkt ins Internet freigeben.**

Beim Wechsel des Administratorpasswortes die Secret-Datei ersetzen und
die Anwendung neu starten; dies beendet alle vorhandenen Sitzungen.

**Fehlerfall:** Fehlt das Passwort, ist es zu kurz oder kann die
Web-Anwendung die Datei nicht lesen, wird keine Bibliothek offengelegt.
Die App zeigt einen Hinweis zur Einrichtung; die schreibenden APIs
antworten ohne Ausführung mit `503` beziehungsweise `401`.

## Endpunkte für die Anmeldung

| Pfad | Methode | Verhalten |
| --- | --- | --- |
| `/login` | GET | Login-Seite, ohne Datenzugriff |
| `/auth/login` | POST | Passwortprüfung, Session + CSRF-Cookie |
| `/auth/logout` | POST | Gültige Session + CSRF nötig, danach Session ungültig |
| `/auth/status` | GET | Zeigt nur angemeldeten Clients den eigenen Status |
| `/auth/client.js` | GET | Ungeheimes Skript für den CSRF-Header |
| `/healthz` | GET | Öffentliche minimalistische Container-Liveness |

## Grenzen und Abnahmekriterien

- Diese Implementierung ersetzt **keine TLS-Verschlüsselung**, keine
  TrueNAS-Speicherberechtigungen und keine Netzwerksegmentierung.
- Die Middleware schützt alle HTTP-Routen, nicht die separat
  gestarteten lokalen Geräte-Helper-/Mount-Privilegien. Diese bleiben
  für TrueNAS Discover gesondert zu prüfen.
- Mit einem angreifbar konfigurierten Reverse-Proxy,
  Cookie-Diebstahl oder einer noch vorhandenen XSS-Lücke ist
  umfassender Schutz nicht garantiert. Eine unabhängige erneute
  Sicherheitsprüfung bleibt für die stabile 1.0.0 erforderlich.
- Die Regressionen in `tests/backend/test_0500_http_owner_auth.py`
  prüfen die Anmeldung, die vollständige Methodensperre, CSRF,
  Herkunftsprüfung, Brute-Force-Drosselung, Passwortdatei,
  PWA-JavaScript und reale FastAPI-Routen.
- Vor `latest` bleibt eine **echte browserbasierte iPhone-PWA-Abnahme
  und ein isolierter TrueNAS-Test** (ohne Produktivfotos) notwendig.
  Die bisherigen isolierten Backendtests allein beweisen nicht die
  vollständige Browser-Kompatibilität.
