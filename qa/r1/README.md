# R1 – isolierte Wiederherstellungskonflikte

Basis: 35299e900b3aa38a9a45935d2a6d5fd15f75be6f; eigene Korrektur ohne F11/F12/F13/F24-Integration.

Nur nachweisbar unberührte Trash-Originale und konsistente ausschließlich auf Trash zeigende Kataloge dürfen einen Zielkonflikt isolieren. Journalstatus conflict reserviert alle Dateien der Operation dauerhaft, verhindert automatischen Queue-Wiederanlauf und automatische Vereinnahmung des fremden Ziels. Der bestehende Papierkorbstatus zeigt den Konflikt. Es gibt keinen Override-/Fortsetzen-Dialog.

Neue Restorejournale speichern Quellidentität, natürlichen Familienschlüssel und Ziel-Veröffentlichungsreceipt, bevor das Original entfernt wird. Gleiche Bytes reichen nicht als Zielbesitz. V1-Journale bleiben lesbar; unbekannte Zielidentität ohne gesichertes Original oder bei Teilcommit bleibt global gesperrt. Die bisherige completed/known_restored-Handoffbereinigung entfernt nur Abschlussjournale.

Die physische Vollleergrenze und Import-Cleanup halten für die Prüfung persistenter Restorejournale den bestehenden Workspace-Lock. Dies ist eine unmittelbar notwendige R1-Voraussetzung; die vollständige F11-Reservierungskoordination wird nicht integriert. F11, F19 sowie allgemeine Pfadwechsel-/Unlink-TOCTOU-Grenzen aus F24 bleiben eigene Befunde.

Unveränderte Originale unter original/ sind per SHA-256 referenziert. Vorher/Nachher laufen getrennt und unverändert. Alle Tests verwenden synthetische temporäre Verzeichnisse und Datenbanken. Globale Startup-Sperren in den Negativfällen sind erwartetes sicheres Verhalten, keine Warnungsumdeklarierung.
