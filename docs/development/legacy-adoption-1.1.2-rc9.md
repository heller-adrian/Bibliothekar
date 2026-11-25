# Bibliothekar 1.1.2 RC9

Ausgangspunkt ist RC8 bei `3c8c29a1856ef36637e1f723fde59bf7bf0ba573`.

## Ursache und Korrektur

RC8 hielt beim Rückweg von „Plan prüfen“ in den Entwurf ab `BEGIN IMMEDIATE`
eine SQLite-Schreibtransaktion offen. `assert_original_layout()` berechnete
innerhalb dieser Transaktion SHA-256 für jede geplante Quelle. Ein Browser-Reload
brach die Serverprüfung nicht zuverlässig ab und zeigte ihren Zustand nicht mehr.
Andere Schreibzugriffe konnten bis zum SQLite-Timeout warten und scheitern.

RC9 speichert die Annahme, den laufenden Zustand und das Ergebnis am Auftrag.
Browser-Reloads lesen diesen Zustand. Nach einem Prozessneustart kann der Server
einen bereits angenommenen Rückweg erneut prüfen. Die Operationssperre verhindert
einen zweiten Worker oder eine konkurrierende Skriptfreigabe. Änderungen am
Plan, an der Inventurgeneration oder am Ausführungszustand werden vor dem kurzen
Transaktionsabschluss geprüft. Rückkehr zum Entwurf verändert keine Mediendatei.

Beim Rückweg wird der ungestartete Plan verworfen. Die gespeicherte Dateiidentität
entscheidet, ob vor der Neuplanung eine Inventur nötig ist. Der Rückweg berechtigt
zu keiner Dateioperation. Vorhandener Archivbestand wird weiterhin per SHA-256
geprüft. Verbindliche Bestätigung, Skriptvorbereitung und kontrollierte Rücknahme
behalten ihre Datei- und SHA-256-Prüfungen. Die langen Lesephasen von Bestätigung,
Skriptvorbereitung und kontrolliertem Rückweg laufen ohne SQLite-Schreibtransaktion.
Unverbindliche Ansichtswechsel verwenden vorhandene Pläne und Dokumente.

## Neue Inventur

Ereignisse, Zeiträume, Unterereignisse und Layouts bleiben gespeichert. Unveränderte
Nachweise bleiben gültig. Ein umbenannter Dateipartner wird nur übernommen, wenn
Gerät, Inode, Größe und SHA-256 ihn eindeutig belegen und die gesamte dazugehörige
Familie weiterhin nachweisbar ist. Bei fehlenden oder geänderten Belegen werden
die betreffenden Dateientscheidungen verworfen. Andere Entscheidungen bleiben
erhalten. Die Planung weist auf nicht mehr belegte Ereignisse hin.

## Messung und Paketabgleich

Isolierter Test mit 436 Dateien zu je 512 KiB, ca. 218 MiB, auf lokalem SSD-Speicher.
Mit jeweils demselben synthetischen Datensatz dauerte der Rückweg 0,539 s unter RC8
und 0,100 s unter RC9. Die Anzahl der Quellhashes sank von 436 auf null. Inventur
(ca. 0,77 s), Entwurfsvorschau (0,014 s) und Erstplanung (ca. 0,22 s) lagen in der
gleichen Größenordnung. Das sind keine gemessenen TrueNAS-Laufzeiten.

Das vorliegende RC8-ZIP wurde statisch gegen Quellcode, Manifest und
Ereignisdokumente geprüft. Es enthält 10.346 Moves, 6.343 Dateifamilien, 35
Ereignisdokumente und 562 XMP-Änderungen. Drei Streaming-Patches können ohne
die Originalbytes nur strukturell geprüft werden. Das Paket wurde nicht ausgeführt.
