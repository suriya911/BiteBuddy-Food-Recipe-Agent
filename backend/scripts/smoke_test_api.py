from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Smoke test the BiteBuddy API.')
    parser.add_argument(
        '--use-large-index',
        action='store_true',
        help='Enable the SQLite large-corpus search index for this test run.',
    )
    parser.add_argument(
        '--index-path',
        type=Path,
        default=Path('backend/data/processed/recipe_search.sqlite'),
        help='Path to the SQLite recipe search index.',
    )
    parser.add_argument(
        '--message',
        default='Need quick vegan mexican dinner with beans under 30 minutes',
        help='Chat prompt to send to the API.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.use_large_index:
        os.environ['USE_LARGE_CORPUS_INDEX'] = 'true'
        os.environ['RECIPE_SEARCH_INDEX_PATH'] = str(args.index_path)

    from app.main import app

    client = TestClient(app)
    health = client.get('/api/health')
    health.raise_for_status()

    payload = {
        'message': args.message,
        'profile': {
            'preferred_cuisines': ['Mexican'],
            'diet': 'vegan',
            'allergies': [],
            'disliked_ingredients': [],
            'excluded_ingredients': [],
            'available_ingredients': ['beans'],
            'max_cooking_time_minutes': 30,
        },
    }
    chat = client.post('/api/chat', json=payload)
    chat.raise_for_status()
    data = chat.json()

    output = {
        'health': health.json(),
        'reply': data['reply'],
        'session_id': data['session_id'],
        'retrieval_trace': data['retrieval_trace'],
        'top_recipe_ids': [item['recipe_id'] for item in data['recipe_matches'][:3]],
        'top_recipe_titles': [item['title'] for item in data['recipe_matches'][:3]],
    }

    if data['recipe_matches']:
        recipe_id = data['recipe_matches'][0]['recipe_id']
        detail = client.get(f'/api/recipes/{recipe_id}')
        detail.raise_for_status()
        recipe = detail.json()
        output['detail_check'] = {
            'recipe_id': recipe['recipe_id'],
            'title': recipe['title'],
            'ingredients': recipe['ingredients'][:5],
        }

    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
