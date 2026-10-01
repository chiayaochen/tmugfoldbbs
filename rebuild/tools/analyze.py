#!/usr/bin/env python3
import argparse
import collections
import hashlib
import json
import pathlib
import re
from bbs import CSI, normalize_newlines, parse_metadata, read_source, strip_ansi

ap = argparse.ArgumentParser()
ap.add_argument('source', type=pathlib.Path)
ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('bbs-rebuild/reports/source-analysis.json'))
args = ap.parse_args()
stats = collections.Counter()
commands = collections.Counter()
records = []
seen = set()
for path in sorted(args.source.rglob('*')):
    if path.suffix.lower() not in ('.eml', '.txt'):
        continue
    match = re.search(r'__gmail-([a-f0-9]+)__', path.name)
    mid = match.group(1) if match else hashlib.sha256(str(path.relative_to(args.source)).encode()).hexdigest()[:16]
    if mid in seen:
        continue
    seen.add(mid)
    try:
        s = read_source(path)
        m = parse_metadata(s['body'], s['headers'])
        seq = list(CSI.finditer(s['body']))
        commands.update(x.group(3) for x in seq)
        stats['articles'] += 1
        stats['encoding:' + s['decode']['encoding']] += 1
        stats['parser:' + m['parser']] += 1
        stats['date_source:' + m['date_source']] += 1
        stats['year:' + m['date_iso'][:4]] += 1
        stats['board:' + m['board']] += 1
        stats['ansi_articles'] += bool(seq)
        stats['ansi_sequences'] += len(seq)
        for kind, count in s['newlines'].items():
            stats['newline:' + kind] += count
        plain = normalize_newlines(strip_ansi(s['body']))
        art = bool(re.search(r'[╭╮╰╯┌┐└┘─│═║█▁▂▃▄▅▆▇]|[=*_\\/|+\-]{5,}', plain))
        records.append({'id': mid, 'file': str(path.relative_to(args.source)), 'sha256': s['raw_sha256'], 'decode': s['decode'], 'newlines': s['newlines'], 'metadata': m, 'ansi_count': len(seq), 'ansi_examples': list(dict.fromkeys(x.group() for x in seq))[:12], 'art_candidate': art, 'body_preview': plain[:350]})
    except Exception as e:
        stats['read_errors'] += 1
        records.append({'id': mid, 'file': str(path), 'error': str(e)})
samples = []
keys = set()
for r in sorted(records, key=lambda x: (x.get('metadata', {}).get('date_iso', ''), x['id'])):
    m = r.get('metadata', {})
    key = (m.get('date_iso', '')[:4], bool(r.get('ansi_count')), r.get('art_candidate'), m.get('board'))
    if key not in keys and len(samples) < 18:
        samples.append(r)
        keys.add(key)
for r in records:
    if any(w in r.get('decode', {}).get('warnings', []) for w in ('undecodable_bytes_preserved_as_hex', 'legacy_codec_candidates_differ')) and len(samples) < 24:
        samples.append(r)
report = {'statistics': dict(stats), 'ansi_commands': dict(commands), 'samples': samples, 'articles': records}
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'statistics': dict(stats), 'ansi_commands': dict(commands), 'samples': [{k: r.get(k) for k in ('id', 'decode', 'metadata', 'ansi_count', 'art_candidate', 'body_preview')} for r in samples[:10]]}, ensure_ascii=False))
