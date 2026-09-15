"""Vergleich: produktive HTML-Seiten (0.14.0, per HTTP) vs. erwartete Dev-Navs.

Read-only: liest nur die unter /tmp abgelegten HTTP-Antworten.
"""
import re

pairs = [
    ("/tmp/prod_root.html", "root"),
    ("/tmp/prod_events.html", "events"),
    ("/tmp/prod_workspace.html", "workspace"),
    ("/tmp/prod_transfer.html", "transfer"),
    ("/tmp/prod_review.html", "review"),
    ("/tmp/prod_files.html", "files"),
]

for file_path, label in pairs:
    html = open(file_path, encoding="utf-8").read()
    navs = re.findall(
        r'<nav[^>]*aria-label="[^"]*"[^>]*>.*?</nav>', html, re.S
    )
    print(f"=== {label} ===")
    for nav in navs:
        buttons = []
        for m in re.finditer(r"<button[^>]*>.*?</button>", nav, re.S):
            block = m.group(0)
            text = re.sub(r"<[^>]+>", "", block)
            text = re.sub(r"\s+", " ", text).strip()
            href_m = re.search(r"location\.href='([^']*)'", block)
            current = 'aria-current' in block
            disabled = 'disabled' in block
            buttons.append(
                (
                    text or "(ohne Text)",
                    href_m.group(1) if href_m else None,
                    current,
                    disabled,
                )
            )
        for text, href, current, disabled in buttons:
            mark = " [AKTUELL]" if current else ""
            mark += " [DISABLED]" if disabled else ""
            print(f"   {text} -> {href}{mark}")
    print()
