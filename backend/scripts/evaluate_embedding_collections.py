from __future__ import annotations

import argparse
import ast
import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


@dataclass
class EvalQuery:
    recipe_id: int
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Qdrant embedding collections on Food.com data.")
    parser.add_argument(
        "--collection-model",
        action="append",
        default=[],
        help="Collection=model_name mapping, e.g. recipes=sentence-transformers/all-MiniLM-L6-v2",
    )
    parser.add_argument(
        "--recipes-csv",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv"),
    )
    parser.add_argument(
        "--reviews-csv",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/reviews.csv"),
    )
    parser.add_argument("--qdrant-url", type=str, default="http://localhost:6333")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-users", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.collection_model:
        raise SystemExit("Provide at least one --collection-model mapping.")

    collections = parse_collection_models(args.collection_model)
    recipe_texts = load_recipe_texts(args.recipes_csv)
    queries = build_eval_queries(args.reviews_csv, recipe_texts, args.max_users, args.seed)
    if not queries:
        raise SystemExit("No evaluation queries were created. Check reviews.csv and recipes.csv.")

    client = QdrantClient(url=args.qdrant_url)
    results = {}
    for collection, model_name in collections.items():
        print(f"Evaluating collection={collection} model={model_name}")
        model = SentenceTransformer(model_name, device="cuda" if has_cuda() else "cpu")
        model.max_seq_length = 256
        metrics = evaluate_collection(client, collection, model, queries, args.top_k)
        results[collection] = {
            "model": model_name,
            "users_evaluated": len(queries),
            **metrics,
        }

    print(
        {
            "config": {
                "recipes_csv": str(args.recipes_csv),
                "reviews_csv": str(args.reviews_csv),
                "qdrant_url": args.qdrant_url,
                "top_k": args.top_k,
                "users": len(queries),
            },
            "collections": results,
        }
    )


def parse_collection_models(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Invalid collection mapping: {item}")
        collection, model_name = item.split("=", 1)
        parsed[collection.strip()] = model_name.strip()
    return parsed


def load_recipe_texts(path: Path) -> dict[int, str]:
    frame = pd.read_csv(
        path,
        usecols=["RecipeId", "Name", "RecipeIngredientParts", "Keywords"],
        dtype={"RecipeId": "int64"},
    )
    texts: dict[int, str] = {}
    for row in frame.to_dict(orient="records"):
        ingredients = parse_list_field(row.get("RecipeIngredientParts"))
        tags = parse_list_field(row.get("Keywords"))
        text = " ".join(
            [
                str(row.get("Name") or ""),
                "Ingredients: " + ", ".join(ingredients),
                "Tags: " + ", ".join(tags),
            ]
        ).strip()
        texts[int(row["RecipeId"])] = text
    return texts


def build_eval_queries(
    reviews_csv: Path,
    recipe_texts: dict[int, str],
    max_users: int,
    seed: int,
) -> list[EvalQuery]:
    reviews = pd.read_csv(
        reviews_csv,
        usecols=["AuthorId", "RecipeId", "Rating", "DateSubmitted"],
        parse_dates=["DateSubmitted"],
        dtype={"AuthorId": "int64", "RecipeId": "int64"},
    ).rename(columns={"AuthorId": "user_id", "RecipeId": "recipe_id"})

    grouped = reviews.sort_values("DateSubmitted").groupby("user_id")
    candidates = []
    for user_id, frame in grouped:
        if len(frame) < 2:
            continue
        target = frame.iloc[-1]
        rid = int(target["recipe_id"])
        text = recipe_texts.get(rid)
        if not text:
            continue
        candidates.append(EvalQuery(recipe_id=rid, text=text))

    random.Random(seed).shuffle(candidates)
    return candidates[:max_users]


def evaluate_collection(
    client: QdrantClient,
    collection: str,
    model: SentenceTransformer,
    queries: list[EvalQuery],
    top_k: int,
) -> dict[str, float]:
    texts = [item.text for item in queries]
    vectors = model.encode(
        texts,
        batch_size=128,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).tolist()

    hits = 0
    mrr_total = 0.0
    for query, vector in zip(queries, vectors):
        results = client.search(collection_name=collection, query_vector=vector, limit=top_k)
        rank = None
        for idx, hit in enumerate(results, start=1):
            payload = hit.payload or {}
            if int(payload.get("recipe_id", -1)) == query.recipe_id:
                rank = idx
                break
        if rank is not None:
            hits += 1
            mrr_total += 1.0 / rank

    total = len(queries)
    hit_rate = hits / total if total else 0.0
    mrr = mrr_total / total if total else 0.0
    return {
        f"HitRate@{top_k}": round(hit_rate, 4),
        f"MRR@{top_k}": round(mrr, 4),
    }


def parse_list_field(raw: object) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return [str(raw)]


def has_cuda() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


if __name__ == "__main__":
    main()
