from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PROMPTS = [
    ('Need quick vegan mexican dinner with beans under 30 minutes', {'preferred_cuisines': ['Mexican'], 'diet': 'vegan', 'available_ingredients': ['beans'], 'max_cooking_time_minutes': 30}),
    ('Need vegetarian Indian dinner with paneer under 40 minutes', {'preferred_cuisines': ['Indian'], 'diet': 'vegetarian', 'available_ingredients': ['paneer'], 'max_cooking_time_minutes': 40}),
    ('Show me gluten free mediterranean lunch with chickpeas', {'preferred_cuisines': ['Mediterranean'], 'allergies': ['gluten'], 'available_ingredients': ['chickpeas']}),
    ('I want high protein chicken dinner under 45 minutes', {'diet': 'non_vegetarian', 'available_ingredients': ['chicken'], 'max_cooking_time_minutes': 45}),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Benchmark BiteBuddy chat latency.')
    parser.add_argument('--use-large-index', action='store_true')
    parser.add_argument('--index-path', type=Path, default=Path('backend/data/processed/recipe_search.sqlite'))
    parser.add_argument('--indexed-candidate-limit', type=int, default=120)
    parser.add_argument('--enable-neural-reranker', action='store_true')
    parser.add_argument('--rerank-top-k', type=int, default=25)
    parser.add_argument('--warmup', type=int, default=1)
    parser.add_argument('--iterations', type=int, default=2)
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/chat_latency_benchmark.json'))
    return parser.parse_args()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * q
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    frac = idx - lower
    return ordered[lower] * (1 - frac) + ordered[upper] * frac


def main() -> None:
    args = parse_args()
    if args.use_large_index:
        os.environ['USE_LARGE_CORPUS_INDEX'] = 'true'
        os.environ['RECIPE_SEARCH_INDEX_PATH'] = str(args.index_path)
    os.environ['INDEXED_CANDIDATE_LIMIT'] = str(args.indexed_candidate_limit)
    if args.enable_neural_reranker:
        os.environ['ENABLE_NEURAL_RERANKER'] = 'true'
        os.environ['NEURAL_RERANK_TOP_K'] = str(args.rerank_top_k)

    from app.main import app

    client = TestClient(app)
    measurements: list[dict[str, object]] = []

    for warmup_idx in range(args.warmup):
        message, profile_updates = PROMPTS[warmup_idx % len(PROMPTS)]
        profile = {
            'preferred_cuisines': [],
            'diet': None,
            'allergies': [],
            'disliked_ingredients': [],
            'excluded_ingredients': [],
            'available_ingredients': [],
            'max_cooking_time_minutes': None,
        }
        profile.update(profile_updates)
        client.post('/api/chat', json={'message': message, 'profile': profile}).raise_for_status()

    for iteration in range(args.iterations):
        for message, profile_updates in PROMPTS:
            profile = {
                'preferred_cuisines': [],
                'diet': None,
                'allergies': [],
                'disliked_ingredients': [],
                'excluded_ingredients': [],
                'available_ingredients': [],
                'max_cooking_time_minutes': None,
            }
            profile.update(profile_updates)
            started = time.perf_counter()
            response = client.post('/api/chat', json={'message': message, 'profile': profile})
            elapsed = (time.perf_counter() - started) * 1000.0
            response.raise_for_status()
            data = response.json()
            measurements.append({
                'iteration': iteration + 1,
                'message': message,
                'elapsed_ms': round(elapsed, 2),
                'matches': len(data.get('recipe_matches') or []),
                'fallback_applied': bool((data.get('retrieval_trace') or {}).get('fallback_applied')),
            })

    latencies = [item['elapsed_ms'] for item in measurements]
    summary = {
        'config': {
            'use_large_index': args.use_large_index,
            'indexed_candidate_limit': args.indexed_candidate_limit,
            'enable_neural_reranker': args.enable_neural_reranker,
            'rerank_top_k': args.rerank_top_k,
            'warmup': args.warmup,
            'iterations': args.iterations,
            'requests': len(measurements),
        },
        'summary_ms': {
            'mean': round(statistics.fmean(latencies), 2) if latencies else 0.0,
            'median': round(statistics.median(latencies), 2) if latencies else 0.0,
            'p95': round(percentile(latencies, 0.95), 2) if latencies else 0.0,
            'min': round(min(latencies), 2) if latencies else 0.0,
            'max': round(max(latencies), 2) if latencies else 0.0,
        },
        'measurements': measurements,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
