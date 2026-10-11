"""0.50.9: text is English in English locale without changing user data."""
from __future__ import annotations

import re
from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS


def tr(value: str) -> str:
    value = value.strip()
    result=UI_TRANSLATIONS.get(value)
    if result is not None:
        return result
    for expr,target in UI_PATTERNS:
        match=re.search(expr,value)
        if match:
            return re.sub(r"\$(\d+)",lambda found:(match.group(int(found.group(1))) or ""),target)
    return value


def test_0509_exact_labels_and_backend_operations():
    examples={
      "Vorbereiten":"Prepare",
      "Finder-Arbeit":"Finder work",
      "Aktualisieren":"Refresh",
      "Ursprünglichen Bestand aus Später zuordnen zurückkopieren":"Copy original inventory back from Assign Later",
      "Archivdateien an ihren ursprünglichen Ort zurückverschieben":"Move archive files back to their original locations",
      "Nicht zum Ursprungszustand gehörende neue Ordner entfernen":"Remove new folders not present in the original state",
      "Dateibestand aktualisiert":"File inventory updated",
      "IST":"Actual",
      "SOLL":"Target",
      "Die Sicherung wird bereits von mindestens einem Ereignis verwendet und kann deshalb nicht mehr vollständig gelöscht werden.":"This backup is already used by at least one event and therefore cannot be deleted completely.",
    }
    for source,expected in examples.items():
        assert tr(source)==expected,source


def test_0509_dynamic_path_preserved():
    examples={
      "8 Dateien in den angegebenen Zielordner verschieben.":"Move 8 files into the specified destination folder.",
      "8 Dateioperationen":"8 file operations",
      "Ursprünglichen Archivzustand wiederherstellen · cr-123":"Restore original archive state · cr-123",
      "115 Dateien insgesamt · 111 Medien · 5.5 GiB · 108 bereits gesichert · 3 neu · 4 Verwaltungsdateien ignoriert":
        "115 total files · 111 media · 5.5 GiB · 108 already backed up · 3 new · 4 administrative files ignored",
      '20260720_fujifilm.JPG liegt unter „2026/Test/Part B/Alle/20260720_fujifilm.JPG“. Die fachliche Zuordnung erlaubt nur „2026/Test/Part A …“.':
        '20260720_fujifilm.JPG is located at “2026/Test/Part B/Alle/20260720_fujifilm.JPG”. The assigned event allows only “2026/Test/Part A …”.',
    }
    for source,expected in examples.items():
        assert tr(source)==expected,(source,tr(source))
