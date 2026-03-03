from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.normalization import (
    build_documents,
    export_jsonl,
    load_records_from_path,
    normalize_records,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize raw Kaggle recipe datasets into a single JSONL corpus.",
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
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    all_recipes = []
    for dataset in manifest["datasets"]:
        folder_name = dataset["slug"].replace("/", "__")
        dataset_dir = args.raw_dir / folder_name
        if not dataset_dir.exists():
            print(f"Skipping {dataset['slug']} because {dataset_dir} was not found.")
            continue

        for file_path in discover_supported_files(dataset_dir):
            records = load_records_from_path(file_path)
            normalized = normalize_records(
                records,
                dataset_name=dataset["slug"],
                source_name=file_path.name,
            )
            all_recipes.extend(normalized)
            print(
                f"Normalized {len(normalized)} recipes from {file_path.relative_to(args.raw_dir)}",
            )

    documents = build_documents(all_recipes)
    export_jsonl(all_recipes, args.records_output)
    export_jsonl(documents, args.documents_output)
    print(f"Wrote {len(all_recipes)} recipes to {args.records_output}")
    print(f"Wrote {len(documents)} documents to {args.documents_output}")


def discover_supported_files(dataset_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".json", ".jsonl"}
    )


if __name__ == "__main__":
    main()
