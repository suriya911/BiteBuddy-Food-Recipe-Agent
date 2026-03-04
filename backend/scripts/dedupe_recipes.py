from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Deduplicate a normalized recipe JSONL corpus.')
    parser.add_argument('--input', type=Path, default=Path('backend/data/processed/recipes_full.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/recipes_full_deduped.jsonl'))
    parser.add_argument('--report', type=Path, default=Path('backend/data/processed/recipes_full_dedup_report.json'))
    parser.add_argument('--db-path', type=Path, default=Path('backend/data/processed/recipes_full_dedup.sqlite'))
    return parser.parse_args()


def canonicalize_text(value: str) -> str:
    return ' '.join((value or '').lower().strip().split())


def canonical_ingredients(values: list[str]) -> str:
    cleaned = sorted({canonicalize_text(item) for item in values if canonicalize_text(item)})
    return '|'.join(cleaned)


def fingerprint_for(row: dict) -> str:
    title = canonicalize_text(row.get('title') or '')
    ingredients = canonical_ingredients(row.get('ingredients') or [])
    base = f'{title}##{ingredients}' if ingredients else title
    return hashlib.sha1(base.encode('utf-8')).hexdigest()


def score_for(row: dict) -> int:
    score = 0
    score += 10 if row.get('description') else 0
    score += min(len(row.get('ingredients') or []), 30)
    score += min(len(row.get('instructions') or []), 30) * 2
    score += 5 if row.get('cuisine') else 0
    score += 5 if row.get('diet') else 0
    score += 3 if row.get('total_time_minutes') else 0
    score += 3 if row.get('rating') else 0
    score += 2 if row.get('image_url') else 0
    score += 1 if row.get('source_url') else 0
    return score


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS dedupe (
            fingerprint TEXT PRIMARY KEY,
            score INTEGER NOT NULL,
            title TEXT,
            source_dataset TEXT,
            payload TEXT NOT NULL
        )
        '''
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_dedupe_source ON dedupe(source_dataset)')


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()
    if args.db_path.exists():
        args.db_path.unlink()

    conn = sqlite3.connect(args.db_path)
    ensure_db(conn)

    total = 0
    replaced = 0
    kept = 0

    with args.input.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            fingerprint = fingerprint_for(row)
            score = score_for(row)
            existing = conn.execute('SELECT score FROM dedupe WHERE fingerprint = ?', (fingerprint,)).fetchone()
            payload = json.dumps(row, ensure_ascii=True)
            if existing is None:
                conn.execute(
                    'INSERT INTO dedupe(fingerprint, score, title, source_dataset, payload) VALUES (?, ?, ?, ?, ?)',
                    (fingerprint, score, row.get('title'), row.get('source_dataset'), payload),
                )
                kept += 1
            elif score > existing[0]:
                conn.execute(
                    'UPDATE dedupe SET score = ?, title = ?, source_dataset = ?, payload = ? WHERE fingerprint = ?',
                    (score, row.get('title'), row.get('source_dataset'), payload, fingerprint),
                )
                replaced += 1
            if total % 10000 == 0:
                conn.commit()

    conn.commit()

    unique_total = conn.execute('SELECT COUNT(*) FROM dedupe').fetchone()[0]
    source_counts = dict(conn.execute('SELECT source_dataset, COUNT(*) FROM dedupe GROUP BY source_dataset ORDER BY COUNT(*) DESC').fetchall())

    with args.output.open('w', encoding='utf-8') as out:
        for (payload,) in conn.execute('SELECT payload FROM dedupe ORDER BY title COLLATE NOCASE'):
            out.write(payload + '\n')

    report = {
        'input_path': str(args.input),
        'output_path': str(args.output),
        'db_path': str(args.db_path),
        'total_input_rows': total,
        'unique_rows': unique_total,
        'duplicate_rows_removed': total - unique_total,
        'replacement_updates': replaced,
        'duplicate_rate': round((total - unique_total) / total, 6) if total else 0,
        'unique_source_counts': source_counts,
    }
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    conn.close()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
