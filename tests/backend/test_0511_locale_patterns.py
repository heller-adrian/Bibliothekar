"""Focused 0.51.1 legacy language and physical-path safety tests."""
from __future__ import annotations

import re

from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS


def _translate(value: str) -> str:
    if value in UI_TRANSLATIONS:
        return UI_TRANSLATIONS[value]
    for pattern, template in UI_PATTERNS:
        match = re.search(pattern, value)
        if match:
            return re.sub(
                r"\$(\d+)",
                lambda token: match.group(int(token.group(1))) or "",
                template,
            )
    return value


def test_0511_known_dynamic_english_labels() -> None:
    cases = {
        "1. Aktuelle event.json ins Archiv übernehmen":
            "1. Copy updated event.json into archive",
        "2. Dateien innerhalb der Kamerabibliothek verschieben":
            "2. Move files within the camera library",
        "3 SD-Karten erkannt. Bitte unter „Andere Quelle verwenden“ auswählen.":
            "3 SD cards detected. Select one under 'Use another source'.",
        "Fuji X-E5 · Bereit zum Einbinden":
            "Fuji X-E5 · Ready to mount",
        "Kein externes Laufwerk erkannt.":
            "No external drive detected.",
        "↻ Aktualisieren": "↻ Refresh",
    }
    for german, expected in cases.items():
        assert _translate(german) == expected, german


def test_0511_machine_values_are_not_translated_as_ui() -> None:
    values = (
        "/mnt/workspace/Arbeitsbereich/Später zuordnen/event.json",
        "IMG_20260720_140509.RAF",
        "vfat,ro,nosuid,noexec",
        "SHA-256 5bca5ce97f",
        "Assign Later/2026/Ereignis/",
    )
    for value in values:
        assert _translate(value) == value


def test_0511_regex_catalog_compiles_and_templates_resolve() -> None:
    for expression, translation in UI_PATTERNS:
        re.compile(expression)
        assert isinstance(translation, str)
