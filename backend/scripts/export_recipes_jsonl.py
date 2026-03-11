from __future__ import annotations

import ast
import csv
import json
from pathlib import Path


def parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_minutes(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("PT"):
        minutes = 0
        num = ""
        for ch in value[2:]:
            if ch.isdigit():
                num += ch
                continue
            if ch == "H" and num:
                minutes += int(num) * 60
                num = ""
            elif ch == "M" and num:
                minutes += int(num)
                num = ""
        return minutes or None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    raw_dir = root / "backend" / "data" / "raw" / "shuyangli94__food-com-recipes-and-user-interactions"
    csv_path = raw_dir / "recipes.csv"
    if not csv_path.exists():
        csv_path = raw_dir / "RAW_recipes.csv"
    if not csv_path.exists():
        raise FileNotFoundError("Food.com recipes CSV not found.")

    output_path = root / "backend" / "data" / "processed" / "recipes.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle, output_path.open(
        "w",
        encoding="utf-8",
    ) as out:
        reader = csv.DictReader(handle)
        for row in reader:
            recipe_id = str(row.get("RecipeId") or row.get("id") or "").strip()
            if not recipe_id:
                continue
            title = str(row.get("Name") or row.get("name") or "Recipe").strip()
            description = row.get("Description") or row.get("description")
            cuisine = (row.get("RecipeCategory") or "").strip() or None
            keywords = parse_list(row.get("Keywords") or row.get("tags"))
            cuisines = [cuisine] if cuisine else []
            images = parse_list(row.get("Images"))
            ingredients = parse_list(row.get("RecipeIngredientParts") or row.get("ingredients"))
            instructions = parse_list(row.get("RecipeInstructions") or row.get("steps"))

            rating_raw = row.get("AggregatedRating")
            rating = None
            if rating_raw and rating_raw.upper() != "NA":
                try:
                    rating = float(rating_raw)
                except ValueError:
                    rating = None

            record = {
                "recipe_id": recipe_id,
                "source": "foodcom",
                "source_dataset": "shuyangli94__food-com-recipes-and-user-interactions",
                "title": title,
                "description": (description.strip() if isinstance(description, str) and description.strip() else None),
                "cuisine": cuisine,
                "cuisines": cuisines,
                "diet": None,
                "total_time_minutes": parse_minutes(row.get("TotalTime") or row.get("total_time_minutes")),
                "prep_time_minutes": parse_minutes(row.get("PrepTime") or row.get("prep_time_minutes")),
                "cook_time_minutes": parse_minutes(row.get("CookTime") or row.get("cook_time_minutes")),
                "servings": row.get("RecipeServings") or row.get("servings"),
                "ingredients": ingredients,
                "instructions": instructions,
                "tags": keywords,
                "rating": rating,
                "image_url": images[0] if images else None,
                "source_url": None,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
