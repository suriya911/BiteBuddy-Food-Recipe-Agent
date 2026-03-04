from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit a normalized recipe JSONL corpus.')
    parser.add_argument('--input', type=Path, default=Path('backend/data/processed/recipes_full.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/recipes_full_audit.json'))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_counts = Counter()
    cuisine_counts = Counter()
    diet_counts = Counter()
    tag_counts = Counter()

    total = 0
    missing = Counter()
    total_ingredients = 0
    total_instructions = 0
    total_tags = 0
    timed = 0
    rated = 0

    with args.input.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            source_counts[row.get('source_dataset') or 'unknown'] += 1

            title = (row.get('title') or '').strip()
            description = (row.get('description') or '').strip()
            cuisine = (row.get('cuisine') or '').strip()
            diet = (row.get('diet') or '').strip()
            ingredients = row.get('ingredients') or []
            instructions = row.get('instructions') or []
            tags = row.get('tags') or []
            total_time = row.get('total_time_minutes')
            rating = row.get('rating')

            if not title:
                missing['title'] += 1
            if not description:
                missing['description'] += 1
            if not cuisine:
                missing['cuisine'] += 1
            else:
                cuisine_counts[cuisine] += 1
            if not diet:
                missing['diet'] += 1
            else:
                diet_counts[diet] += 1
            if not ingredients:
                missing['ingredients'] += 1
            if not instructions:
                missing['instructions'] += 1
            if total_time in (None, ''):
                missing['total_time_minutes'] += 1
            else:
                timed += 1
            if rating in (None, ''):
                missing['rating'] += 1
            else:
                rated += 1

            total_ingredients += len(ingredients)
            total_instructions += len(instructions)
            total_tags += len(tags)
            tag_counts.update(tags)

    report = {
        'input_path': str(args.input),
        'total_recipes': total,
        'source_counts': dict(source_counts.most_common()),
        'missing_field_counts': dict(missing),
        'missing_field_rates': {key: round(value / total, 6) for key, value in missing.items()},
        'field_coverage': {
            'description': round(1 - (missing['description'] / total), 6) if total else 0,
            'cuisine': round(1 - (missing['cuisine'] / total), 6) if total else 0,
            'diet': round(1 - (missing['diet'] / total), 6) if total else 0,
            'ingredients': round(1 - (missing['ingredients'] / total), 6) if total else 0,
            'instructions': round(1 - (missing['instructions'] / total), 6) if total else 0,
            'total_time_minutes': round(timed / total, 6) if total else 0,
            'rating': round(rated / total, 6) if total else 0,
        },
        'averages': {
            'ingredients_per_recipe': round(total_ingredients / total, 3) if total else 0,
            'instructions_per_recipe': round(total_instructions / total, 3) if total else 0,
            'tags_per_recipe': round(total_tags / total, 3) if total else 0,
        },
        'top_cuisines': cuisine_counts.most_common(25),
        'top_diets': diet_counts.most_common(10),
        'top_tags': tag_counts.most_common(30),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({
        'total_recipes': total,
        'sources': dict(source_counts),
        'audit_output': str(args.output),
    }, indent=2))


if __name__ == '__main__':
    main()
