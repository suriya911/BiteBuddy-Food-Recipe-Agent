from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))


SEARCH_QUERIES = [
    "indian food recipes",
    "indian cuisine recipes",
    "international recipes",
    "food.com recipes",
    "RecipeNLG",
]

PREFERRED_KEYWORDS = (
    "recipe",
    "recipes",
    "indian",
    "cuisine",
    "food",
    "ingredients",
    "instructions",
)


@dataclass
class DatasetCandidate:
    ref: str
    title: str
    subtitle: str
    size_mb: float | None
    score: int


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Kaggle for recipe datasets and rank likely candidates.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Results per query.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/data/processed/kaggle_search_results.json"),
        help="Where to write ranked search results.",
    )
    args = parser.parse_args()

    api = get_kaggle_api()
    all_candidates: dict[str, DatasetCandidate] = {}
    for query in SEARCH_QUERIES:
        results = api.dataset_list(search=query)
        for dataset in list(results)[: args.limit]:
            ref = getattr(dataset, "ref", "")
            if not ref:
                continue
            candidate = DatasetCandidate(
                ref=ref,
                title=getattr(dataset, "title", ref),
                subtitle=getattr(dataset, "subtitle", ""),
                size_mb=bytes_to_mb(getattr(dataset, "totalBytes", None)),
                score=score_candidate(dataset),
            )
            current = all_candidates.get(ref)
            if current is None or candidate.score > current.score:
                all_candidates[ref] = candidate

    ranked = sorted(all_candidates.values(), key=lambda item: item.score, reverse=True)
    payload = [asdict(candidate) for candidate in ranked]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {len(payload)} ranked datasets to {args.output}")
    for candidate in ranked[:10]:
        print(
            f"- {candidate.ref} | score={candidate.score} | "
            f"title={candidate.title} | size_mb={candidate.size_mb}"
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


def score_candidate(dataset: Any) -> int:
    haystack = " ".join(
        [
            str(getattr(dataset, "title", "")),
            str(getattr(dataset, "subtitle", "")),
            str(getattr(dataset, "ref", "")),
        ],
    ).lower()
    score = 0
    for keyword in PREFERRED_KEYWORDS:
        if keyword in haystack:
            score += 2
    if "indian" in haystack:
        score += 3
    if "recipeqa" in haystack:
        score -= 2
    return score


def bytes_to_mb(total_bytes: Any) -> float | None:
    try:
        return round(float(total_bytes) / (1024 * 1024), 2)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
