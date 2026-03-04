from __future__ import annotations

import argparse
import ast
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    'and', 'with', 'the', 'for', 'into', 'from', 'that', 'this', 'your', 'you', 'are',
    'recipe', 'dish', 'food', 'fresh', 'easy', 'quick', 'best', 'minutes', 'minute',
    'cup', 'cups', 'tablespoon', 'tablespoons', 'teaspoon', 'teaspoons', 'optional'
}


@dataclass
class EvalUser:
    user_id: int
    train_recipe_ids: list[int]
    test_recipe_id: int
    candidate_ids: list[int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Evaluate baseline recipe recommenders on Food.com.')
    parser.add_argument('--recipes-path', type=Path, default=Path('backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_recipes.csv'))
    parser.add_argument('--interactions-path', type=Path, default=Path('backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_interactions.csv'))
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/recommender_eval.json'))
    parser.add_argument('--sample-users', type=int, default=750)
    parser.add_argument('--negatives-per-user', type=int, default=199)
    parser.add_argument('--min-positive-interactions', type=int, default=5)
    parser.add_argument('--positive-rating-threshold', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    recipes = load_recipes(args.recipes_path)
    interactions = pd.read_csv(args.interactions_path, parse_dates=['date'])

    rating_stats = build_rating_stats(interactions)
    positives = interactions[interactions['rating'] >= args.positive_rating_threshold].copy()
    eval_users = build_eval_users(
        positives=positives,
        recipe_ids=set(recipes.keys()),
        sample_users=args.sample_users,
        negatives_per_user=args.negatives_per_user,
        min_positive_interactions=args.min_positive_interactions,
        rng=rng,
    )
    if not eval_users:
        raise SystemExit('No eligible evaluation users were found.')

    train_popularity = build_train_popularity(eval_users)
    user_profiles = build_user_profiles(eval_users, recipes)

    strategy_fns = {
        'random': lambda user, rid: random_score(user.user_id, rid),
        'popularity': lambda user, rid: popularity_score(rid, train_popularity),
        'rating': lambda user, rid: rating_score(rid, rating_stats),
        'content_profile': lambda user, rid: content_score(user.user_id, rid, user_profiles, recipes),
        'hybrid': lambda user, rid: hybrid_score(user.user_id, rid, user_profiles, recipes, train_popularity, rating_stats),
    }

    strategy_reports = {}
    for name, scorer in strategy_fns.items():
        strategy_reports[name] = evaluate_strategy(eval_users, scorer, catalog_size=len(recipes))

    report = {
        'config': {
            'sample_users': len(eval_users),
            'negatives_per_user': args.negatives_per_user,
            'min_positive_interactions': args.min_positive_interactions,
            'positive_rating_threshold': args.positive_rating_threshold,
            'seed': args.seed,
        },
        'dataset': {
            'recipes': len(recipes),
            'interactions': int(len(interactions)),
            'positive_interactions': int(len(positives)),
        },
        'strategies': strategy_reports,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def load_recipes(path: Path) -> dict[int, dict]:
    frame = pd.read_csv(path, usecols=['id', 'name', 'ingredients', 'tags', 'minutes'])
    recipes = {}
    for row in frame.to_dict(orient='records'):
        recipe_id = int(row['id'])
        recipes[recipe_id] = {
            'tokens': recipe_tokens(row),
            'minutes': int(row['minutes']) if not pd.isna(row['minutes']) else None,
        }
    return recipes


def recipe_tokens(row: dict) -> Counter:
    values = []
    for key in ('name', 'ingredients', 'tags'):
        raw = row.get(key)
        if pd.isna(raw):
            continue
        if isinstance(raw, str) and raw.startswith('['):
            try:
                parsed = ast.literal_eval(raw)
                if isinstance(parsed, list):
                    values.extend(str(item) for item in parsed)
                    continue
            except Exception:
                pass
        values.append(str(raw))

    counter: Counter[str] = Counter()
    for value in values:
        for token in TOKEN_RE.findall(value.lower()):
            if len(token) < 2 or token in STOPWORDS:
                continue
            counter[token] += 1
    return counter


def build_rating_stats(interactions: pd.DataFrame) -> dict[int, float]:
    grouped = interactions.groupby('recipe_id')['rating'].agg(['mean', 'count'])
    global_mean = float(interactions['rating'].mean())
    stats: dict[int, float] = {}
    prior_weight = 10.0
    for recipe_id, row in grouped.iterrows():
        bayes = ((row['count'] * row['mean']) + (prior_weight * global_mean)) / (row['count'] + prior_weight)
        stats[int(recipe_id)] = float(bayes)
    return stats


def build_eval_users(
    *,
    positives: pd.DataFrame,
    recipe_ids: set[int],
    sample_users: int,
    negatives_per_user: int,
    min_positive_interactions: int,
    rng: random.Random,
) -> list[EvalUser]:
    eligible: list[EvalUser] = []
    grouped = positives.sort_values(['user_id', 'date']).groupby('user_id')
    all_recipe_ids = list(recipe_ids)
    for user_id, frame in grouped:
        recipe_sequence = [int(rid) for rid in frame['recipe_id'].tolist()]
        deduped = []
        seen = set()
        for rid in recipe_sequence:
            if rid not in seen:
                seen.add(rid)
                deduped.append(rid)
        if len(deduped) < min_positive_interactions:
            continue
        train_ids = deduped[:-1]
        test_id = deduped[-1]
        blocked = set(deduped)
        available = [rid for rid in all_recipe_ids if rid not in blocked]
        if len(available) < negatives_per_user:
            continue
        negatives = rng.sample(available, negatives_per_user)
        candidates = negatives + [test_id]
        rng.shuffle(candidates)
        eligible.append(EvalUser(int(user_id), train_ids, test_id, candidates))

    if len(eligible) > sample_users:
        eligible = rng.sample(eligible, sample_users)
    return eligible


def build_train_popularity(eval_users: list[EvalUser]) -> Counter:
    counts = Counter()
    for user in eval_users:
        counts.update(user.train_recipe_ids)
    return counts


def build_user_profiles(eval_users: list[EvalUser], recipes: dict[int, dict]) -> dict[int, Counter]:
    profiles: dict[int, Counter] = {}
    for user in eval_users:
        profile = Counter()
        for recipe_id in user.train_recipe_ids:
            profile.update(recipes.get(recipe_id, {}).get('tokens', Counter()))
        profiles[user.user_id] = profile
    return profiles


def popularity_score(recipe_id: int, popularity: Counter) -> float:
    return float(popularity.get(recipe_id, 0))


def random_score(user_id: int, recipe_id: int) -> float:
    return ((user_id * 1315423911) ^ (recipe_id * 2654435761)) % 1000000


def rating_score(recipe_id: int, rating_stats: dict[int, float]) -> float:
    return float(rating_stats.get(recipe_id, 0.0))


def content_score(user_id: int, recipe_id: int, user_profiles: dict[int, Counter], recipes: dict[int, dict]) -> float:
    profile = user_profiles.get(user_id, Counter())
    recipe_tokens = recipes.get(recipe_id, {}).get('tokens', Counter())
    if not profile or not recipe_tokens:
        return 0.0
    overlap = 0.0
    norm = 0.0
    for token, count in recipe_tokens.items():
        overlap += min(profile.get(token, 0), count)
        norm += count
    return overlap / norm if norm else 0.0


def hybrid_score(
    user_id: int,
    recipe_id: int,
    user_profiles: dict[int, Counter],
    recipes: dict[int, dict],
    popularity: Counter,
    rating_stats: dict[int, float],
) -> float:
    c = content_score(user_id, recipe_id, user_profiles, recipes)
    p = math.log1p(popularity.get(recipe_id, 0))
    r = rating_stats.get(recipe_id, 0.0) / 5.0
    return (0.55 * c) + (0.25 * p) + (0.20 * r)


def evaluate_strategy(eval_users: list[EvalUser], scorer, *, catalog_size: int) -> dict:
    hits_at_10 = 0
    recall_at_10 = 0.0
    ndcg_at_10 = 0.0
    mrr_at_10 = 0.0
    candidate_coverage = Counter()

    for user in eval_users:
        ranked = sorted(
            ((rid, scorer(user, rid)) for rid in user.candidate_ids),
            key=lambda item: item[1],
            reverse=True,
        )
        top10 = [rid for rid, _ in ranked[:10]]
        candidate_coverage.update(top10)
        if user.test_recipe_id in top10:
            hits_at_10 += 1
            recall_at_10 += 1.0
            rank = top10.index(user.test_recipe_id) + 1
            ndcg_at_10 += 1.0 / math.log2(rank + 1)
            mrr_at_10 += 1.0 / rank

    total = len(eval_users)
    return {
        'users_evaluated': total,
        'HitRate@10': round(hits_at_10 / total, 4),
        'Recall@10': round(recall_at_10 / total, 4),
        'NDCG@10': round(ndcg_at_10 / total, 4),
        'MRR@10': round(mrr_at_10 / total, 4),
        'CatalogCoverage@10': round(len(candidate_coverage) / catalog_size, 4),
    }


if __name__ == '__main__':
    main()
