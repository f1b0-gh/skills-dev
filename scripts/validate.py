#!/usr/bin/env python3
"""Check skill metadata, local Markdown links, import deltas and the Rust index.

This validates repository structure, not YAML beyond required simple fields,
remote URLs, Markdown anchors, technical correctness or model behavior.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


def prose(text):
    """Exclude fenced examples so Rustdoc links are not treated as file links."""
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = None
            continue
        if fence is None:
            yield re.sub(r'(`+).*?\1', '', line)


def validate(root):
    root = Path(root).resolve()
    errors = []
    skills = sorted((root / 'skills').glob('*/SKILL.md'))
    if not skills:
        errors.append('No skill entry points')
    for path in skills:
        text = path.read_text()
        match = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        if not match:
            errors.append(f'{path.relative_to(root)}: missing frontmatter')
            continue
        fields = {}
        for key in ['name', 'description']:
            found = re.search(r'^' + key + r': (.+)$', match[1], re.M)
            fields[key] = found.group(1).strip() if found else ''
        if fields['name'] != path.parent.name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', fields['name']):
            errors.append(f'{path.relative_to(root)}: invalid name')
        if not fields['description'].startswith('Use when ') or len(fields['description']) > 1024:
            errors.append(f'{path.relative_to(root)}: invalid description')
    paths = list((root / 'skills').rglob('*.md')) + list(root.glob('*.md'))
    for path in paths:
        for line in prose(path.read_text()):
            for link in re.findall(r'\]\(([^)\s]+)\)', line):
                url = urlsplit(link)
                if url.scheme or not url.path:
                    continue
                dest = (path.parent / unquote(url.path)).resolve()
                if not dest.is_relative_to(root) or not dest.exists():
                    errors.append(f'{path.relative_to(root)}: broken or escaping link {link}')
    manifest = root / 'provenance/imports.json'
    if manifest.exists():
        data = json.loads(manifest.read_text())
        changed, omitted = set(), set()
        for item in data['files']:
            path = (root / item['path']).resolve()
            if not path.is_relative_to(root):
                errors.append('Import path escapes repository')
                continue
            if not path.is_file():
                omitted.add(item['path'])
            elif hashlib.sha256(path.read_bytes()).hexdigest() != item['source_sha256']:
                changed.add(item['path'])
        if changed != set(data['modified']):
            errors.append('Import modification inventory is stale: ' + str(sorted(changed ^ set(data['modified']))))
        if omitted != set(data['omitted']):
            errors.append('Import omission inventory is stale')
    else:
        errors.append('Missing import provenance')
    return errors


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        sys.exit(1)
    subprocess.run([sys.executable, str(root / 'skills/rust-skills/checks/validate.py')], check=True)
    print('Skill metadata, local links and import inventory valid')
