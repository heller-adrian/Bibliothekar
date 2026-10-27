# RC12 veröffentlichter Teststand

Quelle: `671d7e7eb96ff493ae51720bb2769eccd8f9048f`, Tag `v1.0.0-rc.12`.

[402 Linux-Regressionen und44 reale Containerfälle bestanden](https://github.com/heller-adrian/Bibliothekar/actions/runs/40552807697): 151 Basis,57 Bootstrap,52 Retention,71 History,71 RC12/Geräte/Auth/Mehrbibliothek. Vollständiger neuer Lauf am veröffentlichten App-/Teststand; keine Wiederverwendung älterer Appstände. Warnungen (5/6 pro Gruppe) betreffen die bestehenden FastAPI-/Starlette-/String-Escape-Meldungen.

Container:25 RC12-Fälle, darunter20 echte SIGKILL-Persistenzgrenzen;19 Legacy-/RC10-Migrationsfälle. Supervisor, UID/GID568, reale RW-/RO-Binds, HTTP-Login/CSRF, Bibliotheksanlage, Neustart, Originalordner und bestätigter Ersatz, Folgeaktion, UID3000/benannte Kernel-POSIX-ACLs, tatsächliche Zugriffsverweigerung und private Helper-Tmpfs-Mounts. Archive unverändert. Lokale neue RC12-Prozess-/HTTP-Matrix:22 bestanden,104,92s; dort ist der RO-Archivnachweis ausdrücklich synthetisch. Echte RO-Binds werden durch die Linux-Container geprüft.

[Veröffentlichungslauf40557043623](https://github.com/heller-adrian/Bibliothekar/actions/runs/40557043623) erfolgreich. Image `ghcr.io/heller-adrian/bibliothekar@sha256:9c09a2d50b7796777e3b40ecab5b03dea5f95071a428419b84dbc74381435702` per Digest aus GHCR gezogen; Version/Revision/Appbytes/Manifesthash stimmen. Alle Release-Anhänge nach erneutem Download erfolgreich gegen SHA256SUMS geprüft. Repository weiterhin privat; NAS-Lesetoken separat erforderlich.

Nicht geprüft: natives TrueNAS/OpenZFS/NFSv4 und physische SD-/USB-Geräte. Kein vollständiger neuer Backend-Gesamtlauf wird behauptet. Hostverwaltetes Profil vertraut berechtigten Hostwritern und ist gegen diese nicht manipulationssicher. Kein produktiver NAS-Eingriff. Release-Testbericht und Originalbelege sind als Anhänge mit Prüfsummen verfügbar.
