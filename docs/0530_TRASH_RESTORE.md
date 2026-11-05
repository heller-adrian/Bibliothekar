# Bibliothekar 0.53.0 – Papierkorb-Wiederherstellung

Die Papierkorbseite bietet ohne Markierung **Alle wiederherstellen**. Nach **Auswählen** lassen sich einzelne Dateien oder mit Umschalt-Taste Bereiche markieren; dann heißt der Button **Auswahl wiederherstellen**. „Alle auswählen“ kann die Auswahl setzen und aufheben.

Restaurierte katalogisierte Kameradateien werden ausschließlich in den zentralen freien Tagesbestand geschrieben. Die kanonische Tages-/Zeitordnerberechnung berücksichtigt belegte Intervalle. Alle zugehörigen Bibliotheksdatenbanken werden aktualisiert. Bei Konflikten, unbekanntem Aufnahmedatum, fehlender eindeutiger Katalogidentität oder SHA-256-Abweichung wird die gesamte angeforderte Auswahl vor einer Dateibewegung abgelehnt. Nicht katalogisierte Dateien bleiben im Papierkorb, bis ihre Herkunft geklärt ist. Noch zu einem Ereignis gehörende Dateien werden nicht als frei verbucht.

Das echte Archiv bleibt read-only. Es werden keine Dateien überschrieben. Die bestehende Funktion **Papierkorb entleeren** bleibt unverändert und getrennt.

Quellbasis: `patch/0.52.1` (`c824afb7070835d9bae4e9c82e2c90420b23bead`); Entwicklungsbranch `patch/0.53.0`.
