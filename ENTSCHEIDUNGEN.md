# Entscheidungen: Kamera-Automatisierung

**Stand:** 01. September 2026
**Zuständigkeit:** Diese Datei ist das fortlaufende Entscheidungsprotokoll. Jede Entscheidung wird hier eingetragen, sobald sie getroffen oder bestätigt wird.

**Rangfolge:**
- **Bestätigte Nutzerentscheidungen** haben höchste Vorrang. Sie werden nicht von Hermes entschieden.
- **Technische Entscheidungen von Hermes** hat Hermes selbstständig getroffen (siehe `.hermes.md` §5).
- **Offene Entscheidungen** sind noch nicht entschieden und werden vom Nutzer behandelt.

---

## 1. Bestätigte Nutzerentscheidungen

*(Entscheidungen, die der Nutzer ausdrücklich getroffen hat.)*

| ID | Datum | Entscheidung | Kontext |
|---|---|---|---|
| N1 | 2026-08-29 | App-Grundstruktur und Zielbild festgelegt (sd-Karte → Kamera-Bibliothek) | `PROJEKTKONTEXT.md` §7 |
| N2 | 2026-08-29 | Sicherheitsbereiche und Hermes-Rechte festgelegt | `PROJEKTKONTEXT.md` §5 und `.hermes.md` §2 |
| N3 | 2026-08-29 | Versionsziel 0.15.0 als nächstes Entwicklungsziel | `AKTUELLER-STAND.md` §1 |
| N4 | 2026-08-31 | Vergleichsauftrag t3 (Archiv- vs. DEV-Vergleich) beauftragt | Auftrag in Sitzung |
| N5 | 2026-09-01 | **Keine** produktiven Veränderungen, **keine** Migrationen, **keine** Versionsänderung in der t3-Sitzung | Nutzer-Anweisung vor t3 |
| N6 | 2026-09-01 | **Projekt-Steuerungsstruktur einrichten:** `.hermes.md`, `AKTUELLER-STAND.md`, `LANGFRISTPLAN.md`, `ENTSCHEIDUNGEN.md`, `PROJEKTKONTEXT.md` | Nutzer-Anweisung vor dieser Sitzung |
| N7 | 2026-09-01 | **Option C bestätigt und umgesetzt**: `resort_required` (DB) + `event_reapply_removed_families` (Tabelle) aus Archiv in DEV übernommen, `loadReapplyPlan()` nachgetragen, DEV-Module `event_document.py` + `event_reapply.py` beibehalten. `APP_VERSION` auf `0.15.0` angehoben. | Nutzer-Anweisung |

---

## 2. Technische Entscheidungen von Hermes

*(Entscheidungen, die Hermes selbstständig innerhalb der bestehenden Architektur trifft.)*

| ID | Datum | Entscheidung | Begründung | Verweis |
|---|---|---|---|---|
| H1 | 2026-09-01 | Vergleichsauftrag t3: SHA-256-Prüfsumme des 0.15.0-Archivs verifiziert (PASS) | `sha256sum`-Ergebnis ist eindeutig | `AKTUELLER-STAND.md` §2 |
| H2 | 2026-09-01 | Vergleichsauftrag t3: DEV-Stand ist Superset (23 Module = 21 + `event_document.py` + `event_reapply.py`) | Dateibasierter Vergleich, `comm`-Befehl | `AKTUELLER-STAND.md` §3 |
| H3 | 2026-09-01 | Vergleichsauftrag t3: 4 DEV-Tests erfolgreich (PASS) | pytest-Ausführung im DEV-Stand | `AKTUELLER-STAND.md` §3 |
| H4 | 2026-09-01 | Vergleichsauftrag t3: `resort_required` (DB) + `event_reapply_removed_families` (Tabelle) + 5 Code-Stellen + UI-Logik `loadReapplyPlan()` fehlen im DEV-Stand | `grep`-Ausführungen beider Stände | `AKTUELLER-STAND.md` §2 |
| H5 | 2026-09-01 | **Option C empfehlen** (Migration 012 + Code-Stellen aus Archiv in DEV; DEV-Module beibehalten) | Option A ist gefährlich (Migration auf Produktion), Option B ist funktionell eingeschränkt (keine UI-Nachsortier-Vorschau); Option C ist technisch und fachlich am vollständigsten | `ABNAHME-VERGLEICH-t3.md` §7.3 |
| H6 | 2026-09-01 | `APP_VERSION` **nicht** in t3-Sitzung ändern | Nutzer-Anweisung (N5); Regel in `.hermes.md` §3 | `.hermes.md` §3 |

---

## 3. Offene Entscheidungen

*(Entscheidungen, die noch vom Nutzer behandelt werden müssen.)*

| ID | Datum | Offene Frage | Hintergrund | Dringlichkeit |
|---|---|---|---|---|
| O1 | 2026-09-01 | **Option C bestätigt und umgesetzt** (2026-09-01, N7) | `resort_required` + `event_reapply_removed_families` + `loadReapplyPlan()` implementiert, 4/4 Tests PASS, `APP_VERSION` = `0.15.0` | **Geschlossen** |
| O2 | 2026-09-01 | Migration 012: Name `012_reapply_runs.sql` → `012_event_reapply.sql` oder beibehalten? | Kosmetisch; funktional irrelevant. | Niedrig |
| O3 | 2026-09-01 | 0.15.0 in Produktion freigeben? | Option C umgesetzt, 4/4 Tests PASS, `APP_VERSION` = `0.15.0`. Erwartet: **Nutzerfreigabe**. | **Offen** |

---

## 4. Dokumentation und Pflege

- Diese Datei wird **jedes Mal** aktualisiert, wenn eine der obigen drei Kategorien eine neue Entscheidung erhält.
- `AKTUELLER-STAND.md` §5 verweist auf diese Datei.
- `PROJEKTKONTEXT.md` enthält die fachlichen Anforderungen, die diese Entscheidungen begründen.
- `LANGFRISTPLAN.md` enthält die Reihenfolge, in der diese Entscheidungen die Versionen betreffen.
