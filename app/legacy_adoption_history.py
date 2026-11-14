"""Read completed adoptions in the selected library and link their archived events."""
from contextlib import closing
from html import escape
import json
from urllib.parse import urlencode

from app.legacy_adoption_catalogue import catalogue_job_id
from app.legacy_adoption_ui import _I18N_JS
from app.operation_health import read_connection
from app.ui_shell import apply_shell


PAGE_SIZE = 20


def completed_adoptions(library, registry_path, *, job_id=None, page=1):
    selection = "AND job.id = ?" if job_id else ""
    parameters = (library.library_id, job_id) if job_id else (library.library_id,)
    with closing(read_connection(library.database_path)) as catalogue, closing(read_connection(registry_path)) as registry:
        catalogue.execute("BEGIN")
        rows = catalogue.execute(f"""SELECT plan.id, plan.job_id, plan.events_json, run.method, run.updated_at
                 FROM legacy_adoption_plans plan JOIN legacy_adoption_jobs job ON job.id = plan.job_id
                 JOIN legacy_adoption_execution run ON run.plan_id = plan.id
                 WHERE job.library_id = ? AND plan.state = 'completed' AND run.phase = 'completed' {selection}
                 ORDER BY run.updated_at DESC, plan.id DESC LIMIT ? OFFSET ?""",
            (*parameters, 1 if job_id else PAGE_SIZE + 1, 0 if job_id else (page - 1) * PAGE_SIZE),
        ).fetchall()
        results = []
        for row in rows:
            receipt = registry.execute("""SELECT plan_fingerprint FROM legacy_adoption_receipts
                WHERE plan_id = ? AND library_id = ? AND catalogue_job_id = ?""",
                (row["id"], library.library_id, catalogue_job_id(row)),
            ).fetchone()
            if receipt is None:
                continue
            entry = {"job_id": row["job_id"], "method": row["method"], "updated_at": row["updated_at"]}
            if job_id:
                entry["fingerprint"] = receipt["plan_fingerprint"]
                entry["files"], entry["families"] = catalogue.execute("""SELECT count(*), count(DISTINCT inventory.family_key)
                    FROM legacy_adoption_moves move JOIN legacy_adoption_inventory inventory
                      ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
                    WHERE move.plan_id = ? AND move.target_path IS NOT NULL""", (job_id, row["id"]),
                ).fetchone()
                originals = json.loads(row["events_json"])
                placeholders = ",".join("?" for _ in originals)
                current = {event["id"]: event for event in catalogue.execute(
                    f"SELECT id, name, job_id FROM events WHERE id IN ({placeholders}) AND status = 'archived'",
                    [event["id"] for event in originals],
                )}
                entry["events"] = [
                    {"id": original["id"], "name": current[original["id"]]["name"], "job": current[original["id"]]["job_id"]}
                    if original["id"] in current else {"id": original["id"], "name": original["name"], "job": None}
                    for original in originals
                ]
            results.append(entry)
    return results[:PAGE_SIZE], len(rows) > PAGE_SIZE


def history_html(library, entries, *, job_id, page, more):
    def href(path, **parameters):
        return escape(path + "?" + urlencode({"library": library.library_id, **parameters}), quote=True)

    def date(entry):
        raw = entry["updated_at"]
        iso = escape(raw.replace(" ", "T") + "Z", quote=True)
        return f'<time datetime="{iso}" data-bk-preserve-language>{escape(raw)}</time>'

    def method(entry):
        return "TrueNAS-Skript" if entry["method"] == "script" else "Manuell über SMB"

    history = href("/legacy-adoption/history")
    title = "Übernahmehistorie"
    if job_id and entries:
        entry = entries[0]
        title = "Bestandsübernahme abgeschlossen"
        events = []
        for event in entry["events"]:
            name = f'<span data-bk-preserve-language>{escape(event["name"])}</span>'
            if event["job"]:
                link = href("/events", job=event["job"], event=event["id"])
                events.append(f'<li><a href="{link}">{name}</a></li>')
            else:
                events.append(f'<li>{name} <span class="muted">Nicht mehr im Archiv</span></li>')
        body = f'''<section class="card adoption-history-card">
          <dl class="adoption-history-facts"><div><dt>Übernommene Dateien</dt><dd>{entry['files']}</dd></div>
            <div><dt>Übernommene Dateifamilien</dt><dd>{entry['families']}</dd></div>
            <div><dt>Abgeschlossen am</dt><dd>{date(entry)}</dd></div><div><dt>Methode</dt><dd>{method(entry)}</dd></div></dl>
          <h2>Archivierte Ereignisse</h2><ul>{''.join(events)}</ul>
          <details><summary>Prüfnachweis anzeigen</summary>
            <p>Die Dateien und Ereignisdokumente wurden vor der Registrierung unabhängig mit SHA-256 geprüft.</p>
            <p>SHA-256 des bestätigten Plans</p><code>{escape(entry['fingerprint'])}</code></details>
          <nav class="adoption-history-actions"><a class="primary" href="{href('/events')}">Alle Ereignisse öffnen</a><a href="{history}">Übernahmehistorie</a></nav>
          </section>'''
    elif job_id:
        body = f'<section class="card"><p>Für diesen Auftrag ist kein abgeschlossener Nachweis verfügbar.</p><a href="{history}">Übernahmehistorie</a></section>'
    else:
        rows = "".join(f'<li>{date(entry)} · <span>{method(entry)}</span> · '
                       f'<a href="{href("/legacy-adoption/history", job=entry["job_id"])}">Abschluss anzeigen</a></li>'
                       for entry in entries)
        previous = f'<a href="{href("/legacy-adoption/history", page=page - 1)}">Neuere Übernahmen</a>' if page > 1 else ""
        following = f'<a href="{href("/legacy-adoption/history", page=page + 1)}">Ältere Übernahmen</a>' if more else ""
        listing = f'<ul>{rows}</ul>' if rows else '<p>Keine abgeschlossenen Übernahmen in dieser Bibliothek.</p>'
        body = f'<section class="card adoption-history-card">{listing}<nav class="adoption-history-actions">{previous}{following}</nav></section>'
    complete_class = ' class="adoption-complete"' if job_id and entries else ""
    library_label = "" if complete_class else f'<p data-bk-preserve-language>{escape(library.display_name)}</p>'
    return apply_shell(f'''<!doctype html><html lang="de"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} · Bibliothekar</title>
      <style>
        main .adoption-history-card{{display:grid;gap:20px;overflow-wrap:anywhere;padding:clamp(16px,3vw,28px)}}
        main.adoption-complete h1{{font-size:clamp(1.55rem,5.5vw,2.35rem);overflow-wrap:anywhere}}
        .adoption-complete h1::before{{content:"✓";margin-inline-end:.45em;color:var(--bk-green)}}
        .adoption-history-card :is(h2,ul,dl){{margin:0}}
        .adoption-history-card li+li{{margin-top:8px}}
        .adoption-history-actions,.adoption-history-facts{{display:flex;flex-wrap:wrap;gap:12px 24px}}
        .adoption-history-card a{{color:var(--bk-ink);text-underline-offset:.22em}}
        .adoption-history-actions a{{padding:9px 14px;border:1px solid var(--bk-line);border-radius:8px;background:var(--bk-surface-2);text-decoration:none;font-weight:650}}
        .adoption-history-actions a.primary{{background:var(--bk-blue);color:var(--bk-on-blue);border-color:transparent}}
        .adoption-history-actions a:focus-visible{{outline:2px solid var(--bk-blue);outline-offset:3px}}
        .adoption-history-actions:empty{{display:none}}
        .adoption-history-facts dd{{margin:4px 0 0;font-weight:650}}
      </style></head><body><main{complete_class}><h1>{title}</h1>{library_label}{body}</main>
      <script>
        function formatAdoptionDates() {{
          const locale=window.BibliothekarI18n?.getLocale()||document.documentElement.lang;
          const formatter=new Intl.DateTimeFormat(locale,{{dateStyle:"medium",timeStyle:"short"}});
          document.querySelectorAll(".adoption-history-card time").forEach(time=>{{
            const date=new Date(time.dateTime);
            if(!Number.isNaN(date.getTime()))time.textContent=formatter.format(date);
          }});
        }}
        document.addEventListener("DOMContentLoaded",formatAdoptionDates);
        window.addEventListener("bk-language-changed",formatAdoptionDates);
      </script></body></html>''', active_area="workspace", subarea="adoption", localization_js=_I18N_JS)
