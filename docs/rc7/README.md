# RC7 – gezielte technische Abnahme und TrueNAS-Praxistest

Basis: `8f2dc28e554a20dcfe3ae02d23d0a1229475701e`, Tree `cf8c06d8bf071b79ec21b9dd0cbb986815466528`.
Alle RC6-Funktionen bleiben enthalten. Produktänderungen gegenüber dieser Basis sind ausschließlich Versionssubstitutionen in drei App-Dateien. Der Quellvertrag prüft sämtliche 176 App-Dateien gegen die Basis.

RC7 vervollständigt den ausdrücklich bestätigten Neueinrichtungsweg bei vollständigen historischen F14-Wurzelbindungen ohne vollständiges storage_initialization. Medien, Retention, Bibliotheks-/Registryhistorie, offene Vorgänge und widersprüchliche Speicherbindungen sperren weiterhin. Alte Belege bleiben archiviert. Fehlende Katalogmeldungen werden dedupliziert; DE/EN erklärt eine nicht zulässige Neueinrichtung.

Abnahme: gezielte Linux-Regressionen, reale persistente Container-Mounts und Offline-Chromium; keine neue Backend-Gesamtsuite. RC6-Nachweise gelten ergänzend: ursprünglich 1993 PASS/17 Fixture-FAIL, anschließend gezielte Linux-Nachprüfung, insgesamt 2010 unterschiedliche PASS; kein vollständig grüner RC6-Gesamtlauf behauptet. Lokaler Praxispatch: 193 unterschiedliche Backend-PASS und acht Browserproben.

Native TrueNAS-/ZFS-/NFSv4-Abnahme bleibt offen; akzeptierte F13-/F24-Risiken und B12 bleiben unverändert.
