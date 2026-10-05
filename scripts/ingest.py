#!/usr/bin/env python3
"""Validate a generator's JSON envelope and add an issue without publishing it."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from build import ROOT, ValidationError, load, read_json, validate_issue

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='schema v1 issue JSON (use - for stdin)')
    parser.add_argument('--original', type=Path, help='Optional original HTML file, matching original.path and sha256')
    args = parser.parse_args()
    incoming = json.load(sys.stdin) if args.input == '-' else read_json(args.input)
    _, columns, _ = load()
    # Validate the entire candidate in an isolated staging tree before writing anything.
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(ROOT / 'content', staging / 'content')
        if args.original:
            if 'original' not in incoming:
                raise ValidationError('--original requires issue.original')
            name = incoming['original'].get('path', '')
            if Path(name).name != name or not name.endswith('.html'):
                raise ValidationError('Unsafe original filename')
            target = staging / 'content/originals' / name
            if target.exists() and target.read_bytes() != args.original.read_bytes():
                raise ValidationError('Original filename already exists with different content')
            shutil.copyfile(args.original, target)
        validate_issue(incoming, columns, staging)
        target = ROOT / 'content/issues' / incoming['date'] / (incoming['column'] + '.json')
        if target.exists():
            raise ValidationError(f'Issue already exists: {incoming["date"]}/{incoming["column"]}; review edits explicitly')
        if args.original:
            artifact = ROOT / 'content/originals' / incoming['original']['path']
            if not artifact.exists():
                shutil.copyfile(args.original, artifact)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(incoming,ensure_ascii=False,indent=2)+'\n')
        print(f'Ingested {target.relative_to(ROOT)}; publication is a separate authorized step.')

if __name__ == '__main__':
    try:
        main()
    except (ValidationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Ingestion failed: {exc}', file=sys.stderr)
        sys.exit(1)
