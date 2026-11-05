# Bibliothekar pre.5 – technischer Entwicklungsstand

**Noch keine Veröffentlichung und keine vollständige Linux-Abnahme.**
Die laufenden und älteren tatsächlichen Ergebnisse stehen in TEST-REPORT.md und
EVIDENCE.json. Ein früherer Erfolg ist kein Testnachweis späteren Anwendungscodes.

## Architektur und nachgewiesene Ursachen

ARCHITECTURE.md beschreibt die Root-/Operationsgrenzen und die gefundenen
Fehlerketten. Geschützte Verwaltungsanker, Mounts, Bibliotheksidentitäten,
Datenbankintegrität, Herkunft, Hashes und Journale bleiben verbindlich. Lesende
Views und Medienbeobachter dürfen keine verwaisten Schreibintents erzeugen.
Unbekannte Wirkungen bleiben konservativ gesperrt; unabhängige nachweislich
abgegrenzte Aktionen bleiben möglich. Kein dritter globaler Speicherzustand.

Der genaue erste Inventory-Fehler auf dem NAS ist nicht bewiesen. Reproduziert
sind der nachfolgende GET-Schreibzugriff, die globale Wirkung einer auditierbaren
Beobachtungsreservation, die erneut versuchte Zentralmigration und die verlorene
General-Aufnahmehistorie nach bestätigter Kataloglöschung. Zusätzlich wurde eine
Thumbnail-GET-Schreibfreigabe mit HTTP500 im echten Containerlog nachgewiesen.

## General-202: endgültiger Befund

Lauf 41190356694 führte den ursprünglich unerwartet angenommenen Auftrag bis
completed/organized_verified aus. Ergebnisdatei, echter SHA, Neustart READY,
F14-Abschluss und Archive waren korrekt. Trotzdem entstand eine neue Herkunft
(47→48 Familien, 90→91 Medien/Mitgliedschaften) für eine schon bekannte Aufnahme.
Die frühere Katalogzeile war nach bestätigtem Verlust entfernt worden. Die
Aufnahmeprüfung berücksichtigt jetzt die unveränderliche Mitgliedschaft und
abgeschlossene Korrekturketten aller registrierten Bibliotheken. Keine Hashes,
Familien oder alten Belege werden geändert. Eine wirklich neue General-Datei
bleibt asynchron importierbar. Variante A benötigt erst eine ausdrückliche
Kopienidentität und ist derzeit DEFERRED.

## Prüfung und Bereitstellung

Der vollständige Linux-Workflow verlangt neue gezielte und fokussierte Tests,
historische Recoverytests, echten Supervisor-/API-/Chromiumbetrieb, historische
Originalimages, SIGKILL-Fälle, 90 Dateien/47 Familien/8 Tage, 4.000 Familien und
14 iPhone-JPEGs mit +13:00. Die Backendmatrix weist sämtliche disjunkten Nodes
und passende JUnit-Zahlen nach; fehlende Ergebnisse, Fehler und Skips sind FAIL.

Der versionsgebundene Publisher in release/ ist vorbereitet, bleibt über
ACCEPTANCE.json/PENDING gesperrt und besitzt noch keinen Ausführungsworkflow.
Er darf erst nach vollständiger Abnahme endgültig gebunden und verwendet werden.
Es wurde weder ein pre.5-Tag noch ein GHCR-Image oder Release erstellt.

## Grenzen

Keine NAS-Zugriffe. Native TrueNAS-/NFSv4-ACL-Abnahme, physische SD-/USB-Geräte,
echtes DNG1.7- und natives RAF-Schreiben: NOT_RUN. Eigenständiger Verlustabschluss
und bekannte-Aufnahme-Variante A: DEFERRED. Upgrade und praktische Abnahmeschritte
stehen in UPGRADE-TRUENAS.md. CHANGED-FILES.txt nennt die bisher gegenüber pre.4
versionierten Dateien; die finale Liste wird vor Freigabe aktualisiert.
