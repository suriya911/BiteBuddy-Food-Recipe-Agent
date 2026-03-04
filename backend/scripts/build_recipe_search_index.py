from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a SQLite FTS recipe search index from normalized JSONL.')
    parser.add_argument('--input', type=Path, default=Path('backend/data/processed/recipes_full_deduped.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/recipe_search.sqlite'))
    parser.add_argument(
        '--interactions-path',
        type=Path,
        default=Path('backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_interactions.csv'),
    )
    parser.add_argument('--batch-size', type=int, default=5000)
    return parser.parse_args()


def extract_foodcom_numeric_id(recipe_id: str) -> int | None:
    if not recipe_id.startswith('foodcom-'):
        return None
    match = re.search(r'(\d+)$', recipe_id)
    if match is None:
        return None
    return int(match.group(1))


def build_popularity_counts(path: Path) -> dict[int, int]:
    counts: dict[int, int] = {}
    if not path.exists():
        return counts
    with path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_recipe_id = row.get('recipe_id')
            if not raw_recipe_id:
                continue
            recipe_id = int(raw_recipe_id)
            counts[recipe_id] = counts.get(recipe_id, 0) + 1
    return counts


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS recipes;
        DROP TABLE IF EXISTS recipe_fts;

        CREATE TABLE recipes (
            recipe_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            cuisine TEXT,
            cuisines_text TEXT,
            cuisines_json TEXT NOT NULL,
            diet TEXT,
            total_time_minutes INTEGER,
            prep_time_minutes INTEGER,
            cook_time_minutes INTEGER,
            servings TEXT,
            ingredients_text TEXT,
            ingredients_json TEXT NOT NULL,
            instructions_json TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            rating REAL,
            image_url TEXT,
            source_url TEXT,
            source TEXT NOT NULL,
            source_dataset TEXT NOT NULL,
            popularity_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX idx_recipes_source_dataset ON recipes(source_dataset);
        CREATE INDEX idx_recipes_cuisine ON recipes(cuisine);
        CREATE INDEX idx_recipes_diet ON recipes(diet);
        CREATE INDEX idx_recipes_total_time ON recipes(total_time_minutes);
        CREATE INDEX idx_recipes_popularity ON recipes(popularity_count DESC);

        CREATE VIRTUAL TABLE recipe_fts USING fts5(
            recipe_id UNINDEXED,
            searchable_text,
            tokenize='unicode61'
        );
        """
    )


def recipe_row_payload(row: dict, popularity_counts: dict[int, int]) -> tuple[tuple, tuple]:
    recipe_id = str(row['recipe_id'])
    numeric_foodcom_id = extract_foodcom_numeric_id(recipe_id)
    popularity_count = popularity_counts.get(numeric_foodcom_id, 0) if numeric_foodcom_id is not None else 0

    title = str(row.get('title') or '')
    description = row.get('description') or None
    cuisine = row.get('cuisine') or None
    cuisines = row.get('cuisines') or []
    diet = row.get('diet') or None
    ingredients = row.get('ingredients') or []
    instructions = row.get('instructions') or []
    tags = row.get('tags') or []

    cuisines_text = ' '.join(str(item) for item in cuisines)
    ingredients_text = ' '.join(str(item) for item in ingredients)
    searchable_text = ' '.join(
        part
        for part in [
            title,
            description or '',
            cuisine or '',
            cuisines_text,
            diet or '',
            ingredients_text,
            ' '.join(str(item) for item in tags),
            ' '.join(str(item) for item in instructions[:10]),
        ]
        if part
    )

    recipe_row = (
        recipe_id,
        title,
        description,
        cuisine,
        cuisines_text,
        json.dumps(cuisines, ensure_ascii=True),
        diet,
        row.get('total_time_minutes'),
        row.get('prep_time_minutes'),
        row.get('cook_time_minutes'),
        row.get('servings'),
        ingredients_text,
        json.dumps(ingredients, ensure_ascii=True),
        json.dumps(instructions, ensure_ascii=True),
        json.dumps(tags, ensure_ascii=True),
        row.get('rating'),
        row.get('image_url'),
        row.get('source_url'),
        row.get('source'),
        row.get('source_dataset'),
        popularity_count,
    )
    fts_row = (recipe_id, searchable_text)
    return recipe_row, fts_row


def flush_batches(conn: sqlite3.Connection, recipe_batch: list[tuple], fts_batch: list[tuple]) -> None:
    if not recipe_batch:
        return
    conn.executemany(
        """
        INSERT INTO recipes(
            recipe_id,
            title,
            description,
            cuisine,
            cuisines_text,
            cuisines_json,
            diet,
            total_time_minutes,
            prep_time_minutes,
            cook_time_minutes,
            servings,
            ingredients_text,
            ingredients_json,
            instructions_json,
            tags_json,
            rating,
            image_url,
            source_url,
            source,
            source_dataset,
            popularity_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        recipe_batch,
    )
    conn.executemany(
        'INSERT INTO recipe_fts(recipe_id, searchable_text) VALUES (?, ?)',
        fts_batch,
    )
    conn.commit()
    recipe_batch.clear()
    fts_batch.clear()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    popularity_counts = build_popularity_counts(args.interactions_path)

    conn = sqlite3.connect(args.output)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA cache_size=-200000')
    create_schema(conn)

    recipe_batch: list[tuple] = []
    fts_batch: list[tuple] = []
    total = 0

    with args.input.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            recipe_row, fts_row = recipe_row_payload(row, popularity_counts)
            recipe_batch.append(recipe_row)
            fts_batch.append(fts_row)
            total += 1
            if len(recipe_batch) >= args.batch_size:
                flush_batches(conn, recipe_batch, fts_batch)
                if total % 50000 == 0:
                    print(f'Indexed {total} recipes...')

    flush_batches(conn, recipe_batch, fts_batch)
    conn.execute('ANALYZE')
    conn.commit()
    conn.close()
    print(f'Built search index at {args.output} with {total} recipes.')


if __name__ == '__main__':
    main()
