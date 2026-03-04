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

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

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
    holdout_index: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Evaluate advanced recipe recommenders on Food.com.')
    parser.add_argument('--recipes-path', type=Path, default=Path('backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_recipes.csv'))
    parser.add_argument('--interactions-path', type=Path, default=Path('backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_interactions.csv'))
    parser.add_argument('--output', type=Path, default=Path('backend/data/processed/recommender_eval_advanced.json'))
    parser.add_argument('--sample-users', type=int, default=300)
    parser.add_argument('--negatives-per-user', type=int, default=199)
    parser.add_argument('--min-positive-interactions', type=int, default=5)
    parser.add_argument('--positive-rating-threshold', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dense-model', type=str, default='sentence-transformers/all-MiniLM-L6-v2')
    parser.add_argument('--reranker-model', type=str, default='cross-encoder/ms-marco-MiniLM-L-6-v2')
    parser.add_argument('--rerank-top-k', type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    recipes = load_recipes(args.recipes_path)
    interactions = pd.read_csv(args.interactions_path, parse_dates=['date'])
    positives = interactions[interactions['rating'] >= args.positive_rating_threshold].copy()

    eval_users = build_eval_users(
        positives=positives,
        recipe_ids=set(recipes.keys()),
        sample_users=args.sample_users,
        negatives_per_user=args.negatives_per_user,
        min_positive_interactions=args.min_positive_interactions,
        rng=rng,
    )
    holdout_indices = {user.holdout_index for user in eval_users}
    train_positives = positives.loc[~positives.index.isin(holdout_indices)].copy()
    train_interactions = interactions.loc[~interactions.index.isin(holdout_indices)].copy()
    if not eval_users:
        raise SystemExit('No eligible evaluation users were found.')

    rating_stats = build_rating_stats(train_interactions)
    popularity = build_train_popularity(train_positives)
    user_profiles = build_user_profiles(eval_users, recipes)
    transition_graph = build_transition_graph(train_positives)

    dense_model = SentenceTransformer(args.dense_model)
    reranker = CrossEncoder(args.reranker_model)

    recipe_embeddings, user_embeddings = build_dense_embeddings(eval_users, recipes, user_profiles, dense_model)

    strategies = {
        'random': lambda user: score_random(user),
        'popularity': lambda user: score_popularity(user, popularity),
        'rating': lambda user: score_rating(user, rating_stats),
        'bm25': lambda user: score_bm25(user, recipes, user_profiles),
        'dense_vector': lambda user: score_dense(user, recipe_embeddings, user_embeddings),
        'graph_cf': lambda user: score_graph(user, transition_graph),
        'ingredient_hypergraph': lambda user: score_hypergraph(user, user_profiles, recipes),
        'advanced_hybrid': lambda user: score_advanced_hybrid(
            user,
            recipes=recipes,
            user_profiles=user_profiles,
            popularity=popularity,
            rating_stats=rating_stats,
            transition_graph=transition_graph,
            recipe_embeddings=recipe_embeddings,
            user_embeddings=user_embeddings,
        ),
    }

    strategy_reports: dict[str, dict] = {}
    precomputed_scores: dict[str, dict[int, dict[int, float]]] = {}
    for name, scorer in strategies.items():
        user_scores = {user.user_id: scorer(user) for user in eval_users}
        precomputed_scores[name] = user_scores
        strategy_reports[name] = evaluate_from_scores(eval_users, user_scores, catalog_size=len(recipes))

    reranker_scores = score_neural_reranker(
        eval_users,
        recipes,
        user_profiles,
        precomputed_scores['advanced_hybrid'],
        reranker,
        top_k=args.rerank_top_k,
    )
    strategy_reports['neural_reranker'] = evaluate_from_scores(eval_users, reranker_scores, catalog_size=len(recipes))

    report = {
        'config': {
            'sample_users': len(eval_users),
            'negatives_per_user': args.negatives_per_user,
            'min_positive_interactions': args.min_positive_interactions,
            'positive_rating_threshold': args.positive_rating_threshold,
            'seed': args.seed,
            'dense_model': args.dense_model,
            'reranker_model': args.reranker_model,
            'rerank_top_k': args.rerank_top_k,
            'openai_reranker': 'skipped_no_api_key',
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
    recipes: dict[int, dict] = {}
    for row in frame.to_dict(orient='records'):
        recipe_id = int(row['id'])
        ingredient_tokens = parse_list_field(row.get('ingredients'))
        tag_tokens = parse_list_field(row.get('tags'))
        name = str(row.get('name') or '')
        text_tokens = tokenize(' '.join([name, *ingredient_tokens, *tag_tokens]))
        ingredient_set = {tok for tok in ingredient_tokens if tok not in STOPWORDS}
        recipes[recipe_id] = {
            'title': name,
            'ingredients_list': ingredient_tokens,
            'ingredient_set': ingredient_set,
            'tags_list': tag_tokens,
            'tokens': Counter(text_tokens),
            'doc_tokens': text_tokens,
            'doc_text': ' '.join([name, 'Ingredients: ' + ', '.join(ingredient_tokens), 'Tags: ' + ', '.join(tag_tokens)]),
            'minutes': int(row['minutes']) if not pd.isna(row['minutes']) else None,
        }
    return recipes


def parse_list_field(raw) -> list[str]:
    if pd.isna(raw):
        return []
    if isinstance(raw, str) and raw.startswith('['):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return [str(raw)]


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall((text or '').lower()) if len(t) > 1 and t not in STOPWORDS]


def build_rating_stats(interactions: pd.DataFrame) -> dict[int, float]:
    grouped = interactions.groupby('recipe_id')['rating'].agg(['mean', 'count'])
    global_mean = float(interactions['rating'].mean())
    stats: dict[int, float] = {}
    prior_weight = 10.0
    for recipe_id, row in grouped.iterrows():
        bayes = ((row['count'] * row['mean']) + (prior_weight * global_mean)) / (row['count'] + prior_weight)
        stats[int(recipe_id)] = float(bayes)
    return stats


def build_eval_users(*, positives: pd.DataFrame, recipe_ids: set[int], sample_users: int, negatives_per_user: int, min_positive_interactions: int, rng: random.Random) -> list[EvalUser]:
    eligible: list[EvalUser] = []
    grouped = positives.sort_values(['user_id', 'date']).groupby('user_id')
    all_recipe_ids = list(recipe_ids)
    for user_id, frame in grouped:
        recipe_sequence = [int(rid) for rid in frame['recipe_id'].tolist()]
        unique_train = []
        seen = set()
        for rid in recipe_sequence[:-1]:
            if rid not in seen:
                seen.add(rid)
                unique_train.append(rid)
        test_id = int(recipe_sequence[-1])
        if test_id in seen:
            continue
        if len(unique_train) < (min_positive_interactions - 1):
            continue
        blocked = set(unique_train + [test_id])
        available = [rid for rid in all_recipe_ids if rid not in blocked]
        if len(available) < negatives_per_user:
            continue
        negatives = rng.sample(available, negatives_per_user)
        candidates = negatives + [test_id]
        rng.shuffle(candidates)
        eligible.append(EvalUser(int(user_id), unique_train, test_id, candidates, int(frame.index[-1])))
    if len(eligible) > sample_users:
        eligible = rng.sample(eligible, sample_users)
    return eligible


def build_train_popularity(train_positives: pd.DataFrame) -> Counter:
    return Counter(int(rid) for rid in train_positives['recipe_id'].tolist())


def score_random(user: EvalUser) -> dict[int, float]:
    return {rid: float(((user.user_id * 1315423911) ^ (rid * 2654435761)) % 1000000) for rid in user.candidate_ids}


def score_popularity(user: EvalUser, popularity: Counter) -> dict[int, float]:
    return {rid: float(math.log1p(popularity.get(rid, 0))) for rid in user.candidate_ids}


def score_rating(user: EvalUser, rating_stats: dict[int, float]) -> dict[int, float]:
    return {rid: float(rating_stats.get(rid, 0.0)) for rid in user.candidate_ids}


def build_user_profiles(eval_users: list[EvalUser], recipes: dict[int, dict]) -> dict[int, dict]:
    profiles = {}
    for user in eval_users:
        token_counter = Counter()
        ingredient_counter = Counter()
        texts = []
        for rid in user.train_recipe_ids:
            recipe = recipes.get(rid)
            if not recipe:
                continue
            token_counter.update(recipe['tokens'])
            ingredient_counter.update(recipe['ingredient_set'])
            texts.append(recipe['doc_text'])
        top_tokens = [token for token, _ in token_counter.most_common(40)]
        top_ingredients = [token for token, _ in ingredient_counter.most_common(40)]
        profiles[user.user_id] = {
            'token_counter': token_counter,
            'ingredient_counter': ingredient_counter,
            'query_tokens': top_tokens,
            'query_text': ' '.join(top_tokens),
            'profile_text': ' '.join(texts[:12])[:4000],
            'top_ingredients': top_ingredients,
        }
    return profiles


def build_transition_graph(positives: pd.DataFrame) -> dict[int, Counter]:
    graph: dict[int, Counter] = defaultdict(Counter)
    grouped = positives.sort_values(['user_id', 'date']).groupby('user_id')
    for _, frame in grouped:
        seq = [int(rid) for rid in frame['recipe_id'].tolist()]
        deduped = []
        seen = set()
        for rid in seq:
            if rid not in seen:
                seen.add(rid)
                deduped.append(rid)
        for prev, curr in zip(deduped, deduped[1:]):
            graph[prev][curr] += 1
            graph[curr][prev] += 1
    return graph


def build_dense_embeddings(eval_users: list[EvalUser], recipes: dict[int, dict], user_profiles: dict[int, dict], model: SentenceTransformer):
    candidate_recipe_ids = sorted({rid for user in eval_users for rid in user.candidate_ids})
    recipe_texts = [recipes[rid]['doc_text'] for rid in candidate_recipe_ids]
    recipe_matrix = model.encode(recipe_texts, batch_size=128, show_progress_bar=True, normalize_embeddings=True)
    recipe_embeddings = {rid: recipe_matrix[idx] for idx, rid in enumerate(candidate_recipe_ids)}

    user_ids = [user.user_id for user in eval_users]
    user_texts = [user_profiles[uid]['profile_text'] or user_profiles[uid]['query_text'] for uid in user_ids]
    user_matrix = model.encode(user_texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    user_embeddings = {uid: user_matrix[idx] for idx, uid in enumerate(user_ids)}
    return recipe_embeddings, user_embeddings


def score_bm25(user: EvalUser, recipes: dict[int, dict], user_profiles: dict[int, dict]) -> dict[int, float]:
    tokenized_docs = [recipes[rid]['doc_tokens'] for rid in user.candidate_ids]
    bm25 = BM25Okapi(tokenized_docs)
    query_tokens = user_profiles[user.user_id]['query_tokens'][:30]
    scores = bm25.get_scores(query_tokens)
    return {rid: float(score) for rid, score in zip(user.candidate_ids, scores)}


def score_dense(user: EvalUser, recipe_embeddings: dict[int, np.ndarray], user_embeddings: dict[int, np.ndarray]) -> dict[int, float]:
    query_vec = user_embeddings[user.user_id]
    return {rid: float(np.dot(query_vec, recipe_embeddings[rid])) for rid in user.candidate_ids}


def score_graph(user: EvalUser, transition_graph: dict[int, Counter]) -> dict[int, float]:
    recency_items = list(reversed(user.train_recipe_ids[-5:]))
    weights = [1.0, 0.8, 0.65, 0.5, 0.35]
    scores = {}
    for rid in user.candidate_ids:
        total = 0.0
        for item, weight in zip(recency_items, weights):
            total += weight * transition_graph.get(item, Counter()).get(rid, 0)
        scores[rid] = total
    return scores


def score_hypergraph(user: EvalUser, user_profiles: dict[int, dict], recipes: dict[int, dict]) -> dict[int, float]:
    profile = user_profiles[user.user_id]
    user_ing = profile['ingredient_counter']
    scores = {}
    for rid in user.candidate_ids:
        recipe_ing = recipes[rid]['ingredient_set']
        if not recipe_ing or not user_ing:
            scores[rid] = 0.0
            continue
        overlap = sum(math.log1p(user_ing.get(ing, 0)) for ing in recipe_ing if ing in user_ing)
        norm = math.sqrt(len(recipe_ing))
        scores[rid] = overlap / norm if norm else 0.0
    return scores


def score_advanced_hybrid(user: EvalUser, *, recipes: dict[int, dict], user_profiles: dict[int, dict], popularity: Counter, rating_stats: dict[int, float], transition_graph: dict[int, Counter], recipe_embeddings: dict[int, np.ndarray], user_embeddings: dict[int, np.ndarray]) -> dict[int, float]:
    bm25_scores = score_bm25(user, recipes, user_profiles)
    dense_scores = score_dense(user, recipe_embeddings, user_embeddings)
    graph_scores = score_graph(user, transition_graph)
    hyper_scores = score_hypergraph(user, user_profiles, recipes)
    pop_scores = {rid: math.log1p(popularity.get(rid, 0)) for rid in user.candidate_ids}
    rating_scores = {rid: rating_stats.get(rid, 0.0) / 5.0 for rid in user.candidate_ids}

    mats = {
        'bm25': normalize_scores(bm25_scores),
        'dense': normalize_scores(dense_scores),
        'graph': normalize_scores(graph_scores),
        'hyper': normalize_scores(hyper_scores),
        'pop': normalize_scores(pop_scores),
        'rating': normalize_scores(rating_scores),
    }
    return {
        rid: (0.18 * mats['bm25'][rid]) + (0.30 * mats['dense'][rid]) + (0.12 * mats['graph'][rid]) + (0.05 * mats['hyper'][rid]) + (0.20 * mats['pop'][rid]) + (0.15 * mats['rating'][rid])
        for rid in user.candidate_ids
    }


def normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    values = list(scores.values())
    if not values:
        return scores
    low = min(values)
    high = max(values)
    if high - low < 1e-12:
        return {rid: 0.0 for rid in scores}
    return {rid: (score - low) / (high - low) for rid, score in scores.items()}


def score_neural_reranker(eval_users: list[EvalUser], recipes: dict[int, dict], user_profiles: dict[int, dict], base_scores: dict[int, dict[int, float]], reranker: CrossEncoder, *, top_k: int) -> dict[int, dict[int, float]]:
    outputs: dict[int, dict[int, float]] = {}
    for idx, user in enumerate(eval_users, start=1):
        ranked = sorted(base_scores[user.user_id].items(), key=lambda item: item[1], reverse=True)
        top_ids = [rid for rid, _ in ranked[:top_k]]
        query = user_profiles[user.user_id]['profile_text'] or user_profiles[user.user_id]['query_text']
        pairs = [(query, recipes[rid]['doc_text']) for rid in top_ids]
        rerank_scores = reranker.predict(pairs, batch_size=32, show_progress_bar=False)
        score_map = {rid: base_scores[user.user_id][rid] for rid in user.candidate_ids}
        normed_base = normalize_scores({rid: base_scores[user.user_id][rid] for rid in top_ids})
        normed_rerank = normalize_scores({rid: float(score) for rid, score in zip(top_ids, rerank_scores)})
        for rid in top_ids:
            score_map[rid] = (0.75 * normed_base[rid]) + (0.25 * normed_rerank[rid]) + 1.0
        outputs[user.user_id] = score_map
        if idx % 25 == 0:
            print(f'Reranked {idx}/{len(eval_users)} users')
    return outputs


def evaluate_from_scores(eval_users: list[EvalUser], user_scores: dict[int, dict[int, float]], *, catalog_size: int) -> dict:
    hits_at_10 = 0
    recall_at_10 = 0.0
    ndcg_at_10 = 0.0
    mrr_at_10 = 0.0
    candidate_coverage = Counter()
    for user in eval_users:
        scores = user_scores[user.user_id]
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
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
