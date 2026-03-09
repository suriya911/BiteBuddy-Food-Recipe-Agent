from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import os
import time
import math
import torch
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build recipe embeddings and upsert into Qdrant.")
    parser.add_argument(
        "--recipes-path",
        type=Path,
        default=Path("backend/data/processed/recipes.jsonl"),
    )
    parser.add_argument(
        "--recipes-csv",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_recipes.csv"),
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="recipes",
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="http://localhost:6333",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    parser.add_argument(
        "--foodcom",
        action="store_true",
        help="Embed Food.com RAW_recipes.csv (uses numeric recipe_id).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Embedding device: auto|cpu|cuda",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Use fp16 mixed precision on CUDA for faster embedding.",
    )
    parser.add_argument("--batch-size", type=int, default=1024, help="SentenceTransformer encode batch size.")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Rows per chunk to process.")
    parser.add_argument(
        "--upload-batch-size",
        type=int,
        default=2000,
        help="Qdrant upload batch size (2000-5000 recommended).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for smoke runs.")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of rows to skip before embedding (for chunked runs).",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop/recreate the Qdrant collection before upload.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["TOKENIZERS_PARALLELISM"] = "true"
    torch.set_num_threads(16)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")
        torch.backends.cudnn.benchmark = True

    device = resolve_device(args.device)
    if device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but not available. Install a CUDA-enabled PyTorch build.")
    model = SentenceTransformer(args.model, device=device)
    model.max_seq_length = 256
    if device == "cuda":
        name = torch.cuda.get_device_name(0)
        print(f"Using CUDA device: {name}")
    else:
        print("Using CPU for embeddings.")
    vector_size = model.get_sentence_embedding_dimension()

    client = QdrantClient(url=args.qdrant_url)
    ensure_collection(client, args.collection, vector_size, args.recreate)

    if args.upload_batch_size < 2000 or args.upload_batch_size > 5000:
        raise SystemExit("upload-batch-size must be between 2000 and 5000.")

    uploaded = 0
    total_rows = count_total_rows(args)
    row_iter = iter_recipe_rows(args)
    start_time = time.perf_counter()
    for chunk_idx, chunk in enumerate(chunked_rows(row_iter, args.chunk_size), start=1):
        chunk_start = time.perf_counter()
        texts = [row["document_text"] for row in chunk]
        vectors = model.encode(
            texts,
            batch_size=args.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()

        points: list[PointStruct] = []
        for row, vector in zip(chunk, vectors):
            recipe_id = row["recipe_id"]
            point_id = recipe_id if isinstance(recipe_id, int) else stable_int_id(str(recipe_id))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "recipe_id": recipe_id,
                        "title": row["title"],
                        "cuisine": row["cuisine"],
                        "diet": row["diet"],
                        "ingredients": row["ingredients"],
                        "total_time_minutes": row["total_time_minutes"],
                    },
                )
            )

        for start in range(0, len(points), args.upload_batch_size):
            batch_points = points[start : start + args.upload_batch_size]
            client.upsert(collection_name=args.collection, points=batch_points, wait=True)
            uploaded += len(batch_points)
            if total_rows:
                print(f"Uploaded {uploaded}/{total_rows}")
            else:
                print(f"Uploaded {uploaded}")
        chunk_elapsed = time.perf_counter() - chunk_start
        if chunk_elapsed > 0:
            eps = len(chunk) / chunk_elapsed
            print(
                f"Chunk {chunk_idx}: {len(chunk)} rows in {chunk_elapsed:.2f}s "
                f"({eps:.1f} embeddings/s)"
            )

    info = client.get_collection(args.collection)
    actual = int(info.points_count or 0)
    if actual < uploaded:
        raise RuntimeError(f"Qdrant validation failed: points_count={actual}, expected_at_least={uploaded}")

    total_elapsed = time.perf_counter() - start_time
    throughput = uploaded / total_elapsed if total_elapsed > 0 else None
    print(
        json.dumps(
            {
                "collection": args.collection,
                "uploaded_points": uploaded,
                "qdrant_points_count": actual,
                "model": args.model,
                "elapsed_seconds": round(total_elapsed, 2),
                "throughput_embeddings_per_sec": round(throughput, 2) if throughput else None,
            },
            indent=2,
        )
    )


def read_recipes(path: Path, limit: int, offset: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if offset > 0 and idx < offset:
                continue
            if not line.strip():
                continue
            item = json.loads(line)
            ingredients = item.get("ingredients") or []
            instructions = item.get("instructions") or []
            tags = item.get("tags") or []
            text = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("description") or ""),
                    "Ingredients: " + ", ".join(str(x) for x in ingredients),
                    "Instructions: " + " ".join(str(x) for x in instructions[:12]),
                    "Tags: " + ", ".join(str(x) for x in tags),
                ]
            ).strip()
            rows.append(
                {
                    "recipe_id": str(item.get("recipe_id")),
                    "title": str(item.get("title") or ""),
                    "cuisine": item.get("cuisine"),
                    "diet": item.get("diet"),
                    "ingredients": ingredients[:25],
                    "total_time_minutes": item.get("total_time_minutes"),
                    "document_text": text,
                }
            )
            if limit > 0 and len(rows) >= limit:
                break
    return rows


def read_foodcom_recipes(path: Path, limit: int, offset: int) -> list[dict]:
    header = pd.read_csv(path, nrows=1).columns
    if "RecipeId" in header:
        return read_foodcom_recipes_v2(path, limit, offset)
    return read_foodcom_recipes_v1(path, limit, offset)


def read_foodcom_recipes_v1(path: Path, limit: int, offset: int) -> list[dict]:
    frame = pd.read_csv(path, usecols=["id", "name", "ingredients", "tags", "minutes"])
    rows: list[dict] = []
    for idx, row in enumerate(frame.to_dict(orient="records")):
        if offset > 0 and idx < offset:
            continue
        ingredients = parse_list_field(row.get("ingredients"))
        tags = parse_list_field(row.get("tags"))
        text = " ".join(
            [
                str(row.get("name") or ""),
                "Ingredients: " + ", ".join(ingredients),
                "Tags: " + ", ".join(tags),
            ]
        ).strip()
        rows.append(
            {
                "recipe_id": int(row["id"]),
                "title": str(row.get("name") or ""),
                "cuisine": None,
                "diet": None,
                "ingredients": ingredients[:25],
                "total_time_minutes": int(row["minutes"]) if not pd.isna(row["minutes"]) else None,
                "document_text": text,
            }
        )
        if limit > 0 and len(rows) >= limit:
            break
    return rows


def iter_recipe_rows(args: argparse.Namespace):
    if args.foodcom:
        yield from iter_foodcom_recipes(args.recipes_csv, args.limit, args.offset)
        return
    yield from iter_recipes_jsonl(args.recipes_path, args.limit, args.offset)


def iter_recipes_jsonl(path: Path, limit: int, offset: int):
    seen = 0
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if offset > 0 and idx < offset:
                continue
            if not line.strip():
                continue
            item = json.loads(line)
            ingredients = item.get("ingredients") or []
            instructions = item.get("instructions") or []
            tags = item.get("tags") or []
            text = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("description") or ""),
                    "Ingredients: " + ", ".join(str(x) for x in ingredients),
                    "Instructions: " + " ".join(str(x) for x in instructions[:12]),
                    "Tags: " + ", ".join(str(x) for x in tags),
                ]
            ).strip()
            yield {
                "recipe_id": str(item.get("recipe_id")),
                "title": str(item.get("title") or ""),
                "cuisine": item.get("cuisine"),
                "diet": item.get("diet"),
                "ingredients": ingredients[:25],
                "total_time_minutes": item.get("total_time_minutes"),
                "document_text": text,
            }
            seen += 1
            if limit > 0 and seen >= limit:
                break


def iter_foodcom_recipes(path: Path, limit: int, offset: int):
    header = pd.read_csv(path, nrows=1).columns
    if "RecipeId" in header:
        yield from iter_foodcom_recipes_v2(path, limit, offset)
        return
    yield from iter_foodcom_recipes_v1(path, limit, offset)


def iter_foodcom_recipes_v1(path: Path, limit: int, offset: int):
    seen = 0
    for chunk in pd.read_csv(path, usecols=["id", "name", "ingredients", "tags", "minutes"], chunksize=5000):
        for idx, row in chunk.iterrows():
            if offset > 0 and seen < offset:
                seen += 1
                continue
            ingredients = parse_list_field(row.get("ingredients"))
            tags = parse_list_field(row.get("tags"))
            text = " ".join(
                [
                    str(row.get("name") or ""),
                    "Ingredients: " + ", ".join(ingredients),
                    "Tags: " + ", ".join(tags),
                ]
            ).strip()
            yield {
                "recipe_id": int(row["id"]),
                "title": str(row.get("name") or ""),
                "cuisine": None,
                "diet": None,
                "ingredients": ingredients[:25],
                "total_time_minutes": int(row["minutes"]) if not pd.isna(row["minutes"]) else None,
                "document_text": text,
            }
            seen += 1
            if limit > 0 and seen >= limit:
                return


def iter_foodcom_recipes_v2(path: Path, limit: int, offset: int):
    seen = 0
    for chunk in pd.read_csv(
        path,
        usecols=[
            "RecipeId",
            "Name",
            "TotalTime",
            "RecipeIngredientParts",
            "RecipeInstructions",
            "Keywords",
        ],
        chunksize=5000,
    ):
        for idx, row in chunk.iterrows():
            if offset > 0 and seen < offset:
                seen += 1
                continue
            ingredients = parse_list_field(row.get("RecipeIngredientParts"))
            tags = parse_list_field(row.get("Keywords"))
            instructions = parse_list_field(row.get("RecipeInstructions"))
            text = " ".join(
                [
                    str(row.get("Name") or ""),
                    "Ingredients: " + ", ".join(ingredients),
                    "Instructions: " + " ".join(instructions[:12]),
                    "Tags: " + ", ".join(tags),
                ]
            ).strip()
            yield {
                "recipe_id": int(row["RecipeId"]),
                "title": str(row.get("Name") or ""),
                "cuisine": None,
                "diet": None,
                "ingredients": ingredients[:25],
                "total_time_minutes": parse_iso_duration_minutes(row.get("TotalTime")),
                "document_text": text,
            }
            seen += 1
            if limit > 0 and seen >= limit:
                return


def chunked_rows(iterator, chunk_size: int):
    batch: list[dict] = []
    for row in iterator:
        batch.append(row)
        if len(batch) >= chunk_size:
            yield batch
            batch = []
    if batch:
        yield batch


def count_total_rows(args: argparse.Namespace) -> int | None:
    if args.limit > 0:
        return args.limit
    if args.foodcom:
        try:
            with args.recipes_csv.open("r", encoding="utf-8") as handle:
                return sum(1 for _ in handle) - 1
        except Exception:
            return None
    try:
        with args.recipes_path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return None


def read_foodcom_recipes_v2(path: Path, limit: int, offset: int) -> list[dict]:
    frame = pd.read_csv(
        path,
        usecols=[
            "RecipeId",
            "Name",
            "TotalTime",
            "RecipeIngredientParts",
            "RecipeInstructions",
            "Keywords",
        ],
    )
    rows: list[dict] = []
    for idx, row in enumerate(frame.to_dict(orient="records")):
        if offset > 0 and idx < offset:
            continue
        ingredients = parse_list_field(row.get("RecipeIngredientParts"))
        tags = parse_list_field(row.get("Keywords"))
        instructions = parse_list_field(row.get("RecipeInstructions"))
        text = " ".join(
            [
                str(row.get("Name") or ""),
                "Ingredients: " + ", ".join(ingredients),
                "Instructions: " + " ".join(instructions[:12]),
                "Tags: " + ", ".join(tags),
            ]
        ).strip()
        rows.append(
            {
                "recipe_id": int(row["RecipeId"]),
                "title": str(row.get("Name") or ""),
                "cuisine": None,
                "diet": None,
                "ingredients": ingredients[:25],
                "total_time_minutes": parse_iso_duration_minutes(row.get("TotalTime")),
                "document_text": text,
            }
        )
        if limit > 0 and len(rows) >= limit:
            break
    return rows


def parse_list_field(raw: object) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, str) and raw.startswith("c("):
        return parse_r_c_vector(raw)
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return [str(raw)]


def parse_r_c_vector(value: str) -> list[str]:
    inner = value.strip()
    if inner.startswith("c(") and inner.endswith(")"):
        inner = inner[2:-1]
    items: list[str] = []
    current = ""
    in_quotes = False
    for char in inner:
        if char == '"':
            in_quotes = not in_quotes
            continue
        if char == "," and not in_quotes:
            if current.strip():
                items.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        items.append(current.strip())
    return [item for item in (token.strip() for token in items) if item]


def parse_iso_duration_minutes(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if not isinstance(value, str):
        try:
            return int(value)
        except Exception:
            return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text.startswith("PT"):
        minutes = 0
        hours = 0
        days = 0
        try:
            if "D" in text:
                days_part, time_part = text[2:].split("D", 1)
                days = int(days_part) if days_part else 0
                text = "PT" + time_part
            if "H" in text:
                h_part = text.split("H")[0].replace("PT", "")
                hours = int(h_part) if h_part else 0
                text = "PT" + text.split("H")[1]
            if "M" in text:
                m_part = text.split("M")[0].replace("PT", "")
                minutes = int(m_part) if m_part else 0
        except Exception:
            return None
        return days * 1440 + hours * 60 + minutes
    return None


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int, recreate: bool) -> None:
    exists = client.collection_exists(collection_name=collection_name)
    if exists and recreate:
        client.delete_collection(collection_name=collection_name)
        exists = False
    if not exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def stable_int_id(text: str) -> int:
    import hashlib

    digest = hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
    return int(digest[:15], 16)


def resolve_device(value: str) -> str:
    if value in {"cpu", "cuda"}:
        return value
    try:
        import torch
    except Exception:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


if __name__ == "__main__":
    main()
