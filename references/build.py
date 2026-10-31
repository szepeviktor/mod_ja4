#!/usr/bin/env python3
"""Build current JA4 references from original source files (requires PyYAML)."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

import yaml

JA4 = re.compile(r"[tqd](?:[0-9]{2}|s[123])[di][0-9]{4}[a-zA-Z0-9]{2}_[0-9a-f]{12}_[0-9a-f]{12}\Z")
RAW = re.compile(r"([^_]+)_([0-9a-f,]*)_([0-9a-f,]*)_([0-9a-f,]*)\Z")


def raw_hash(raw):
    match = RAW.fullmatch(raw)
    if not match:
        raise ValueError("Invalid RAW format")
    head, ciphers, extensions, signatures = match.groups()
    for part in (ciphers, extensions, signatures):
        if part and any(not re.fullmatch(r"[0-9a-f]{4}", item) for item in part.split(',')):
            raise ValueError("Invalid RAW token")
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()[:12] if value else '000000000000'
    tail = extensions + ('_' + signatures if signatures else '')
    return f"{head}_{digest(ciphers)}_{digest(tail)}"


def build(root):
    sources = root / 'sources'
    catalog = {}
    classifier = {}

    def add(ja4, raw, source, metadata, family=None, label=None, verified=False):
        if not isinstance(ja4, str) or not JA4.fullmatch(ja4):
            raise ValueError(f"Invalid JA4 in {source}: {ja4!r}")
        if raw is not None and (not isinstance(raw, str) or raw_hash(raw) != ja4):
            raise ValueError(f"JA4/RAW mismatch in {source}: {ja4}")
        item = catalog.setdefault(ja4, {'ja4': ja4, 'raw': [], 'observations': []})
        if raw is not None and raw not in item['raw']:
            item['raw'].append(raw)
        observation = {'source': source, 'raw': raw, 'metadata': metadata,
                       'family': family, 'label': label, 'verified': verified}
        if observation not in item['observations']:
            item['observations'].append(observation)
        if verified and raw and family and label:
            classifier[(family, label, raw)] = {'family': family, 'label': label, 'raw': raw}

    with (sources / 'foxio/mapping.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or 'ja4' not in reader.fieldnames:
            raise ValueError('FoXIO CSV needs a ja4 column')
        for row in reader:
            if row['ja4']:
                add(row['ja4'], None, 'foxio', row,
                    label=row.get('Application') or row.get('Library') or None)

    families = {'C': 'c-cpp-openssl', 'C++': 'c-cpp-openssl', 'Node.js': 'nodejs', 'PHP / cURL': 'php',
                'Swift / URLSession': 'swift-urlsession'}
    workflow = json.loads((sources / 'workflow/results.json').read_text())
    if not isinstance(workflow, list):
        raise ValueError('Workflow results must be a list')
    for capture in workflow:
        if capture.get('success') is True:
            label = capture['language']
            add(capture['ja4'], capture['ja4_raw'], 'workflow', capture,
                families.get(label, label.lower()), label, True)

    pending = None
    counts = {}
    for line in (sources / 'live-traffic/debug-request-headers.log').read_text().splitlines():
        if line.startswith('@@ja4 '):
            if pending is not None:
                counts[(pending, None)] = counts.get((pending, None), 0) + 1
            pending = line[6:].strip()
        elif line.startswith('@@ja4_raw '):
            if pending is None:
                raise ValueError('live-traffic RAW without preceding JA4')
            key = pending, line[10:].strip()
            counts[key] = counts.get(key, 0) + 1
            pending = None
    if pending is not None:
        counts[(pending, None)] = counts.get((pending, None), 0) + 1
    for (ja4, raw), count in sorted(counts.items(), key=lambda entry: str(entry[0])):
        add(ja4, raw, 'live-traffic', {'count': count})

    manual = yaml.safe_load((sources / 'manual.yaml').read_text())
    if not isinstance(manual, list):
        raise ValueError('Manual entries must be a YAML list')
    ids = set()
    for entry in manual:
        if not isinstance(entry, dict) or set(entry) - {'id', 'ja4', 'raw', 'family', 'label', 'verification', 'notes', 'evidence'}:
            raise ValueError('Invalid manual entry or unknown field')
        for field in ('id', 'ja4', 'label', 'verification', 'notes'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f'Manual entry needs a nonempty {field}')
        if entry['id'] in ids:
            raise ValueError('Duplicate manual id')
        ids.add(entry['id'])
        if entry['verification'] not in ('unverified', 'corroborated', 'verified'):
            raise ValueError('Invalid manual verification')
        if entry.get('family') is not None and (not isinstance(entry['family'], str) or not entry['family']):
            raise ValueError('Invalid manual family')
        if not isinstance(entry.get('evidence', []), list) or any(not isinstance(value, str) for value in entry.get('evidence', [])):
            raise ValueError('Manual evidence must be a list of strings')
        add(entry['ja4'], entry.get('raw'), 'manual', entry, entry.get('family'),
            entry['label'], entry['verification'] == 'verified')

    for item in catalog.values():
        item['raw'].sort()
        item['conflict'] = len({o['family'] for o in item['observations'] if o['family']}) > 1
    return [catalog[key] for key in sorted(catalog)], [classifier[key] for key in sorted(classifier)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    # Validate all sources before replacing either output; never retain stale outputs on failure.
    output = args.root / 'generated'
    try:
        catalog, classifier = build(args.root)
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError) as error:
        for name in ('catalog.json', 'classifier-references.json'):
            (output / name).unlink(missing_ok=True)
        print(f'Reference build failed: {error}', file=sys.stderr)
        return 1
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (('catalog.json', catalog), ('classifier-references.json', classifier)):
        (output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(f'Built {len(catalog)} JA4 entries and {len(classifier)} classifier references.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
