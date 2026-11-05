"""Syntax check delivered HTML scripts/styles; no application API mutations."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys

import tinycss2


class Assets(HTMLParser):
    def __init__(self):
        super().__init__(); self.kind = None; self.parts = []; self.assets = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            values = dict(attrs)
            self.kind = None if tag == 'script' and values.get('type', '').lower() not in {'', 'text/javascript', 'application/javascript', 'module'} else tag
            self.parts = []
    def handle_data(self, data):
        if self.kind: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == self.kind:
            self.assets.append((tag, ''.join(self.parts))); self.kind = None


def css_errors(nodes):
    errors = []
    for node in nodes:
        if node.type == 'error': errors.append(str(node))
        content = getattr(node, 'content', None)
        if content is not None:
            if node.type == 'at-rule' and node.lower_at_keyword in {'media','supports','layer','container','keyframes','-webkit-keyframes'}:
                errors += css_errors(tinycss2.parse_rule_list(content, skip_comments=True, skip_whitespace=True))
            elif node.type in {'qualified-rule', 'at-rule'}:
                errors += css_errors(tinycss2.parse_declaration_list(content, skip_comments=True, skip_whitespace=True))
        if node.type == 'declaration':
            errors += css_errors(node.value)
        if node.type == 'function': errors += css_errors(node.arguments)
    return errors


def check_pages(pages, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    counts = {'pages': len(pages), 'scripts': 0, 'styles': 0}
    for name, html in pages.items():
        parser = Assets(); parser.feed(html)
        for index, (kind, content) in enumerate(parser.assets):
            if kind == 'script':
                path = output / f'{name}-{index}.js'; path.write_text(content)
                subprocess.run(['node', '--check', str(path)], capture_output=True, text=True, check=True)
                counts['scripts'] += 1
            else:
                errors = css_errors(tinycss2.parse_stylesheet(content, skip_comments=True, skip_whitespace=True))
                assert not errors, (name, index, errors)
                counts['styles'] += 1
    (output/'syntax.json').write_text(json.dumps(counts, indent=2))
    return counts
