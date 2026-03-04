from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.normalization import (
    build_documents,
    load_records_from_path,
    normalize_records,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize raw Kaggle recipe datasets into JSONL corpora.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("backend/data/raw"),
        help="Directory containing downloaded Kaggle datasets.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("backend/data/source_manifest.json"),
        help="Dataset manifest used to map raw folders to source names.",
    )
    parser.add_argument(
        "--records-output",
        type=Path,
        default=Path("backend/data/processed/recipes.jsonl"),
        help="Normalized recipe records output path.",
    )
    parser.add_argument(
        "--documents-output",
        type=Path,
        default=Path("backend/data/processed/recipe_documents.jsonl"),
        help="Searchable recipe document output path.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="CSV chunk size for large datasets.",
    )
    parser.add_argument(
        "--skip-documents",
        action="store_true",
        help="Skip building the document corpus when only normalized records are needed.",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reset_output(args.records_output)
    if not args.skip_documents:
        reset_output(args.documents_output)

    total_recipes = 0
    total_documents = 0

    for dataset in manifest["datasets"]:
        folder_name = dataset["slug"].replace("/", "__")
        dataset_dir = args.raw_dir / folder_name
        if not dataset_dir.exists():
            print(f"Skipping {dataset['slug']} because {dataset_dir} was not found.")
            continue

        for file_path in discover_supported_files(dataset_dir):
            file_total = 0
            for records in iter_record_batches(file_path, chunk_size=args.chunk_size):
                normalized = normalize_records(
                    records,
                    dataset_name=dataset["slug"],
                    source_name=file_path.name,
                )
                if not normalized:
                    continue
                append_jsonl(normalized, args.records_output)
                total_recipes += len(normalized)
                file_total += len(normalized)

                if not args.skip_documents:
                    documents = build_documents(normalized)
                    append_jsonl(documents, args.documents_output)
                    total_documents += len(documents)

            print(
                f"Normalized {file_total} recipes from {file_path.relative_to(args.raw_dir)}",
            )

    print(f"Wrote {total_recipes} recipes to {args.records_output}")
    if args.skip_documents:
        print("Skipped document export by request.")
    else:
        print(f"Wrote {total_documents} documents to {args.documents_output}")


def discover_supported_files(dataset_dir: Path) -> list[Path]:
    preferred_files = {
        "raw_recipes.csv",
        "indain_food_cuisine_dataset.csv",
        "recipenlg_dataset.csv",
        "recipes.json",
        "recipes.jsonl",
    }
    discovered = [
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".json", ".jsonl"}
    ]
    prioritized = [path for path in discovered if path.name.lower() in preferred_files]
    return sorted(prioritized or discovered)


def iter_record_batches(file_path: Path, *, chunk_size: int) -> Iterable[list[dict]]:
    if file_path.suffix.lower() == ".csv":
        for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
            yield chunk.to_dict(orient="records")
        return
    yield load_records_from_path(file_path)


def reset_output(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()


def append_jsonl(items: list[object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        for item in items:
            payload = item.model_dump() if hasattr(item, "model_dump") else item
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
