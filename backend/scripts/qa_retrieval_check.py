from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TEST_MATRIX = {
    "cuisine": [
        ("Italian pasta dinner", {"preferred_cuisines": ["Italian"]}),
        ("Spicy Thai noodles", {"preferred_cuisines": ["Thai"]}),
        ("Japanese quick lunch", {"preferred_cuisines": ["Japanese"]}),
        ("Mexican bean tacos", {"preferred_cuisines": ["Mexican"]}),
        ("Indian curry", {"preferred_cuisines": ["Indian"]}),
        ("Mediterranean salad", {"preferred_cuisines": ["Mediterranean"]}),
        ("Korean stir fry", {"preferred_cuisines": ["Korean"]}),
    ],
    "diet": [
        ("Vegan protein bowl", {"diet": "vegan"}),
        ("Vegetarian dinner", {"diet": "vegetarian"}),
        ("Eggetarian breakfast", {"diet": "eggetarian"}),
        ("Pescatarian meal", {"diet": "pescatarian"}),
        ("Non-veg high protein", {"diet": "non_vegetarian"}),
    ],
    "time": [
        ("Dinner under 15 minutes", {"max_cooking_time_minutes": 15}),
        ("Quick 30 minute meal", {"max_cooking_time_minutes": 30}),
        ("Slow cook under 90 minutes", {"max_cooking_time_minutes": 90}),
    ],
    "ingredients": [
        ("Chicken and rice dinner", {"available_ingredients": ["chicken", "rice"]}),
        ("Paneer and spinach curry", {"available_ingredients": ["paneer", "spinach"]}),
        ("Tofu stir fry", {"available_ingredients": ["tofu"]}),
        ("Lentils and tomato stew", {"available_ingredients": ["lentils", "tomato"]}),
        ("Shrimp garlic pasta", {"available_ingredients": ["shrimp", "garlic"]}),
    ],
    "combined": [
        (
            "Vegan mexican bean dinner under 30 minutes",
            {
                "preferred_cuisines": ["Mexican"],
                "diet": "vegan",
                "available_ingredients": ["beans"],
                "max_cooking_time_minutes": 30,
            },
        ),
        (
            "Italian vegetarian pasta under 20 minutes",
            {
                "preferred_cuisines": ["Italian"],
                "diet": "vegetarian",
                "available_ingredients": ["pasta"],
                "max_cooking_time_minutes": 20,
            },
        ),
        (
            "Indian chicken curry under 45 minutes",
            {
                "preferred_cuisines": ["Indian"],
                "diet": "non_vegetarian",
                "available_ingredients": ["chicken"],
                "max_cooking_time_minutes": 45,
            },
        ),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a QA matrix against /api/chat and summarize results.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/data/processed/retrieval_qa_report.json"),
        help="Where to write the JSON report.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="How many top titles to store per test.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from app.main import app

    client = TestClient(app)
    report = {"summary": {}, "cases": []}
    total = 0
    passed = 0

    for category, cases in TEST_MATRIX.items():
        for message, profile_overrides in cases:
            total += 1
            payload = build_payload(message, profile_overrides)
            response = client.post("/api/chat", json=payload)
            ok = response.status_code == 200
            data = response.json() if ok else {}
            matches = data.get("recipe_matches", []) if ok else []
            success = ok and len(matches) > 0
            if success:
                passed += 1
            report["cases"].append(
                {
                    "category": category,
                    "message": message,
                    "profile": payload["profile"],
                    "status_code": response.status_code,
                    "match_count": len(matches),
                    "top_titles": [item["title"] for item in matches[: args.limit]],
                    "reply": data.get("reply"),
                }
            )

    report["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote report to {args.output}")


def build_payload(message: str, overrides: dict) -> dict:
    profile = {
        "preferred_cuisines": [],
        "diet": None,
        "allergies": [],
        "disliked_ingredients": [],
        "excluded_ingredients": [],
        "available_ingredients": [],
        "max_cooking_time_minutes": None,
    }
    profile.update(overrides)
    return {"message": message, "profile": profile}


if __name__ == "__main__":
    main()
