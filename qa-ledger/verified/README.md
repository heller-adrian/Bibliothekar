# Verified QA Results

Unter diesem Pfad dürfen ausschließlich Ergebnisse liegen, die einen abgeschlossenen `qa-thinker`-REVIEW durchlaufen haben.

Ein Executor-Ergebnis allein ist hier unzulässig.

Empfohlene Struktur:

`verified/<version>/<phase>/<test-id>.json`

Beispiel:

`verified/0.21.2/phase-a/T004.json`

Jeder Datensatz referenziert PLAN/EXECUTE/REVIEW und enthält das Thinker-Urteil. `RETEST_REQUIRED` ist ein gültiger autoritativer Befund: Es sagt aus, dass der konkrete Versuch methodisch nicht zur Testentscheidung taugt.
