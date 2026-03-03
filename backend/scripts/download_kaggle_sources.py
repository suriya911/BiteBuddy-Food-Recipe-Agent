from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download selected Kaggle datasets from the checked-in manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("backend/data/source_manifest.json"),
        help="Manifest containing Kaggle dataset slugs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backend/data/raw"),
        help="Directory to place downloaded raw files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the dataset directory already exists.",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    api = get_kaggle_api()

    for dataset in manifest["datasets"]:
        slug = dataset["slug"]
        destination = args.output_dir / slug.replace("/", "__")
        if destination.exists() and not args.force:
            print(f"Skipping {slug} because {destination} already exists.")
            continue

        destination.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {slug} -> {destination}")
        api.dataset_download_files(
            slug,
            path=str(destination),
            unzip=True,
            quiet=False,
        )


def get_kaggle_api() -> Any:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as error:
        raise SystemExit(
            "The kaggle package is not installed. Run `pip install -r backend/requirements.txt` first.",
        ) from error

    api = KaggleApi()
    try:
        api.authenticate()
    except OSError as error:
        raise SystemExit(
            "Kaggle credentials not found. Set KAGGLE_USERNAME and KAGGLE_KEY or configure ~/.kaggle/kaggle.json.",
        ) from error
    return api


if __name__ == "__main__":
    main()
