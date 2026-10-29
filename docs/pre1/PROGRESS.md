# pre.1 Veröffentlichung — Fortschritt

Freigabe zur eigenständigen Prerelease-Veröffentlichung liegt vor.
Branch codex/publish-1.0.0-pre.1. Freigegebener Hotfix 79ab9c1f; gefrorener
versionierter Build 282aeba2dd8464f30c8484034759cbb0fd8e0823. Einzige Appänderung:
Versionskennung, lokal 12 Versions-/Startregressionen bestanden. Der finale
Dokumentationsstand 3fb14e6b enthält denselben Hotfix-Anwendungscode.

Der versionsgebundene neue Publisher verwendet die bewährte OCI-Index-Prüfung
aus dem erfolgreichen Publisher a72aaed4. Keine Verwendung des auf pre
festgelegten alten Writers. Neun gezielte Publisher-Tests mit zahlreichen
Negativ-Unterfällen, Actionlint und Bash-/Python-Syntaxprüfung bestehen.
Der Registry- und GitHub-Schreibteil ist ausschließlich manuell mit expliziter
Bestätigung PUBLISH v1.0.0-pre.1 auf dem vorbereiteten Zweig möglich.

Nächster Schritt: minimale Registrierung des manuellen Workflows auf main
unter bestehenden Regeln, dann einmaliger Dispatch. Der Publisher prüft die
akzeptierten ZIP-Digests und alle Tests, den Versionsdiff, alle eingebetteten
Appbytes und Modi und den erneut gestarteten echten Supervisor vor dem ersten
Tag-/Image-Schreibvorgang. Bei Fehler oder Teilveröffentlichung sicher stoppen.
Keine automatische Löschung oder Wiederholung. Vorhandenes pre, latest,
stabile Releasekennungen, Repository-/Paketsichtbarkeit werden geschützt.

Keine TrueNAS-Änderungen. Native TrueNAS/NFSv4, SD/USB und DNG 1.7 bleiben NOT_RUN;
Verlustabschlussmodell DEFERRED. Ein erfolgreicher Prerelease ermöglicht erst
die anschließende praktische TrueNAS-Abnahme.
