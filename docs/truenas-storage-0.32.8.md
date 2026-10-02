# TrueNAS-Speicherarchitektur 0.32.8

## Ziel

Bibliothekar trennt ab 0.32.8 Container-Mounts von fachlichen Ordnern. Für den
normalen Kameraworkflow genügt ein gemeinsamer read-write Workspace-Mount.
Bibliotheksarchive bleiben dagegen absichtlich getrennte read-only Mounts.

## Empfohlene TrueNAS-Mounts

Persistente App-Daten bleiben separat:

- `/config` – RW
- `/database` – RW
- `/logs` – RW

Gemeinsamer Kamerabereich:

- ein beliebiger Host-Ordner oder ein Dataset → `/workspace` – RW

Main-Archiv:

- gewünschter Host-Ordner/Dataset → `/main-library` – RO

Jedes zusätzliche Archiv:

- eigener Host-Ordner/Dataset → frei gewählter Containerpfad – RO

Optionale externe Arbeitsbereiche:

- nur wenn ein Arbeitsbereich bewusst außerhalb `/workspace` liegen soll:
  eigener Host-Ordner/Dataset → frei gewählter Containerpfad – RW

## Von Bibliothekar verwaltete Workspace-Ordner

Standardmäßig:

```text
/workspace
├── SD-Kartensicherungen
│   └── Freigewordene Archivdateien
├── Arbeitsbereiche
│   ├── main
│   └── <weitere Bibliotheks-ID>
└── Metadatenkorrektur
```

Die Namen `SD-Kartensicherungen`, `Arbeitsbereiche` und
`Metadatenkorrektur` sind unter Einstellungen → Pfade änderbar.

Bibliothekar darf diese selbst verwalteten Ordner innerhalb des Workspace-Mounts
atomar umbenennen. Es werden dabei keine Dateikopien erzeugt. Ist ein Pfad
stattdessen selbst ein TrueNAS-Mount oder ein eigenes darunter eingehängtes
Dataset, wird die Umbenennung abgewiesen; die Mount-Konfiguration muss dann
in TrueNAS geändert werden.

## Bestehende Installationen

Ein bereits vorhandener echter `/workspace/Arbeitsbereich` bleibt unverändert.
Bibliothekar verschiebt ihn beim Upgrade nicht automatisch.

Auf einer frischen 0.32.8-Installation ist `/workspace/Arbeitsbereiche/main`
die kanonische Main-Wurzel. `/workspace/Arbeitsbereich` wird nur als
Kompatibilitätsalias bereitgestellt, damit ältere Pfadannahmen während der
Migration nicht brechen.

## Neue Bibliothek

Im Standardfall:

1. Archiv als eigenen read-only Host Path in TrueNAS einbinden.
2. Bibliothekar → Einstellungen → Bibliotheken → Bibliothek hinzufügen.
3. Anzeigename eingeben.
4. Arbeitsbereich leer lassen.
5. Archiv-Containerpfad angeben und prüfen.

Bibliothekar erzeugt den Arbeitsbereich automatisch unter
`/workspace/Arbeitsbereiche/<interne-id>`.

## Benutzerdefinierter Arbeitsbereich

Soll eine Bibliothek auf einem anderen Speicherort liegen:

1. Ziel in TrueNAS als zusätzlichen RW Host Path in den Container einbinden.
2. Diesen Containerpfad in Bibliothekar als Arbeitsbereich eintragen.
3. Bibliothekar prüft Existenz, Zugriffsrechte und Dateisystembeziehung zum
   globalen Bestand.

Die App verschiebt beim Ändern eines Bibliothekspfads keine bestehenden Dateien.
Der Nutzer stellt deshalb vor dem Umschalten sicher, dass der neue Pfad den
gewünschten Bestand enthält.

## Archive

Archive bleiben pro Bibliothek getrennt. Das ist eine bewusste Sicherheitsgrenze:

- kein gemeinsamer schreibbarer Archivstamm
- jedes Archiv kann auf einem anderen Dataset/Pool liegen
- jeder Archivmount ist read-only
- Bibliothekar führt keine unkontrollierten Archiv-Moves aus
- physische Archivänderungen bleiben Finder-/Nutzeraktionen mit anschließender
  Verifikation

## Hardlinks

Hardlinks sind nur möglich, wenn Quelle und Ziel tatsächlich dasselbe
Dateisystem besitzen. Bibliothekar prüft die reale Dateisystemgrenze.

- gleiche `st_dev` / erfolgreicher Link → Hardlink
- `EXDEV` → Hardlink unmöglich
- danach sichtbare Auswahl: Kopieren oder Verschieben

Ein gemeinsamer `/workspace`-Mount ist deshalb die bevorzugte Standardstruktur.
Er garantiert Hardlinks nur dann, wenn die beteiligten Unterordner nicht wiederum
auf unterschiedlichen ZFS-Datasets/Mounts liegen.

## 0.32.8-Sicherheitsregeln

- keine automatische Verschiebung bestehender Bibliotheksbestände beim Upgrade
- keine automatische Änderung von TrueNAS-Mounts
- Archive bleiben read-only
- globale SD-/Rückkehrbestände bleiben bibliotheksübergreifend zentral
- Bibliotheks-Arbeitsbereiche bleiben getrennt
- globale Claims bleiben bibliotheksübergreifend exklusiv
- Cross-Dataset-Transfers werden nie stillschweigend als Hardlink behandelt
