# pre.5 – Veröffentlichungsvorbereitung

**Nicht ausführungsbereit:** `ACCEPTANCE.json` steht auf `PENDING`.
Kein Tag, Image oder Release wurde durch diese Vorbereitung erzeugt.

Vor Verwendung müssen der finale erfolgreiche Linux-Lauf, sämtliche vier
Artefakt-IDs und ZIP-Digests, JUnit-Zahlen, vollständige disjunkte Backend-Coverage
und die abschließende Dokumentationsidentität fest gebunden sein.
`source_audit()` verweigert alle anderen Zustände vor externen Schreibvorgängen.

Grundlage ist der erfolgreich verwendete pre.4-Publisher. Der pre.5-Pfad baut
ausschließlich den vollständig abgenommenen Commit einschließlich der bereits
getesteten Versionskennung. OCI-Index-, Deskriptor-, Konfigurations-, Docker-ID-
und Byteprüfungen sowie tatsächlicher Digest-Pull und unabhängiger Download aller
Release-Anlagen bleiben Pflicht. Alle früheren Prereleases einschließlich pre.4,
Repository-/Paketstatus, stabile Kennzeichnungen und `latest` werden verglichen.
Nach einem unklaren Teilzustand ist kein automatischer Wiederholungsversuch erlaubt.

Vor dem ersten externen Schreibvorgang werden außerdem die Laufzeit-/Container-
Gates auf dem tatsächlich gebauten Release-Image erneut geprüft. Die vollständige
fachlich unveränderte Backendmatrix wird nicht allein für den Publisher wiederholt.
