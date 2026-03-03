from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas import RecipeDocument, RecipeRecord


TITLE_KEYS = ("title", "name", "recipe_name", "recipe", "translatedrecipeName")
DESCRIPTION_KEYS = ("description", "summary", "desc")
CUISINE_KEYS = ("cuisine", "region", "course", "category")
INGREDIENT_KEYS = (
    "ingredients",
    "ingredient",
    "ingredient_list",
    "ingredient_parts",
    "recipeingredientparts",
    "ner",
    "translatedingredients",
)
INSTRUCTION_KEYS = (
    "instructions",
    "directions",
    "steps",
    "method",
    "recipeinstructions",
    "translatedinstructions",
)
ID_KEYS = ("recipe_id", "id", "recipeid", "uid")
PREP_TIME_KEYS = ("prep_time", "prepminutes", "preptime", "prep")
COOK_TIME_KEYS = ("cook_time", "cookminutes", "cooktime", "cook")
TOTAL_TIME_KEYS = ("total_time", "minutes", "totalminutes", "totaltime")
SERVINGS_KEYS = ("servings", "yield", "recipeyield")
IMAGE_KEYS = ("image", "image_url", "photo_url")
URL_KEYS = ("url", "source_url", "recipe_url")
TAGS_KEYS = ("tags", "keywords", "category", "categories")
RATING_KEYS = ("rating", "aggregated_rating", "avg_rating")

KNOWN_CUISINES = {
    "indian",
    "south indian",
    "north indian",
    "punjabi",
    "gujarati",
    "bengali",
    "mughlai",
    "hyderabadi",
    "chettinad",
    "indo chinese",
    "chinese",
    "thai",
    "japanese",
    "korean",
    "vietnamese",
    "indonesian",
    "malaysian",
    "singaporean",
    "italian",
    "french",
    "spanish",
    "greek",
    "turkish",
    "mediterranean",
    "mexican",
    "tex mex",
    "american",
    "southern",
    "cajun",
    "caribbean",
    "jamaican",
    "middle eastern",
    "lebanese",
    "persian",
    "arabic",
    "african",
    "ethiopian",
    "moroccan",
    "brazilian",
    "peruvian",
    "continental",
    "fusion",
}

NON_VEGETARIAN_TERMS = {
    "chicken",
    "mutton",
    "lamb",
    "beef",
    "pork",
    "fish",
    "shrimp",
    "prawn",
    "bacon",
    "ham",
    "turkey",
    "sausage",
}
PESCATARIAN_TERMS = {"fish", "shrimp", "prawn", "salmon", "tuna", "sardine"}
EGG_TERMS = {"egg", "eggs"}
VEGAN_BLOCKERS = {"milk", "cream", "paneer", "cheese", "butter", "ghee", "yogurt", "curd"}


def load_records_from_path(input_path: Path) -> list[dict[str, Any]]:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(input_path)
        return frame.to_dict(orient="records")
    if suffix == ".json":
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "recipes" in data and isinstance(data["recipes"], list):
                return data["recipes"]
            return [data]
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in input_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    raise ValueError(f"Unsupported file type: {input_path}")


def normalize_records(
    records: list[dict[str, Any]],
    *,
    dataset_name: str,
    source_name: str,
) -> list[RecipeRecord]:
    normalized: list[RecipeRecord] = []
    for index, row in enumerate(records):
        title = first_non_empty(row, TITLE_KEYS)
        if not title:
            continue

        ingredients = normalize_list(first_non_empty(row, INGREDIENT_KEYS))
        instructions = normalize_instructions(first_non_empty(row, INSTRUCTION_KEYS))
        tags = normalize_list(first_non_empty(row, TAGS_KEYS))
        cuisine = normalize_text(first_non_empty(row, CUISINE_KEYS))
        cuisines = infer_cuisines(
            title=str(title),
            raw_cuisine=cuisine,
            tags=tags,
        )
        total_time = normalize_minutes(first_non_empty(row, TOTAL_TIME_KEYS))
        prep_time = normalize_minutes(first_non_empty(row, PREP_TIME_KEYS))
        cook_time = normalize_minutes(first_non_empty(row, COOK_TIME_KEYS))

        recipe = RecipeRecord(
            recipe_id=build_recipe_id(row, dataset_name, index),
            source=source_name,
            source_dataset=dataset_name,
            title=normalize_text(title) or "Untitled recipe",
            description=normalize_text(first_non_empty(row, DESCRIPTION_KEYS)),
            cuisine=cuisine or (cuisines[0] if cuisines else None),
            cuisines=cuisines,
            diet=infer_diet(title=str(title), ingredients=ingredients, tags=tags),
            total_time_minutes=total_time,
            prep_time_minutes=prep_time,
            cook_time_minutes=cook_time,
            servings=normalize_text(first_non_empty(row, SERVINGS_KEYS)),
            ingredients=ingredients,
            instructions=instructions,
            tags=tags,
            rating=normalize_rating(first_non_empty(row, RATING_KEYS)),
            image_url=normalize_text(first_non_empty(row, IMAGE_KEYS)),
            source_url=normalize_text(first_non_empty(row, URL_KEYS)),
        )
        normalized.append(recipe)
    return normalized


def build_documents(recipes: list[RecipeRecord]) -> list[RecipeDocument]:
    documents: list[RecipeDocument] = []
    for recipe in recipes:
        searchable_text = "\n".join(
            part
            for part in [
                recipe.title,
                recipe.description or "",
                f"Cuisine: {recipe.cuisine}" if recipe.cuisine else "",
                f"Diet: {recipe.diet}" if recipe.diet else "",
                f"Ingredients: {', '.join(recipe.ingredients)}" if recipe.ingredients else "",
                f"Instructions: {' '.join(recipe.instructions)}" if recipe.instructions else "",
                f"Tags: {', '.join(recipe.tags)}" if recipe.tags else "",
            ]
            if part
        )
        documents.append(
            RecipeDocument(
                recipe_id=recipe.recipe_id,
                title=recipe.title,
                cuisine=recipe.cuisine,
                cuisines=recipe.cuisines,
                diet=recipe.diet,
                searchable_text=searchable_text,
                chunks=chunk_text(searchable_text),
                metadata={
                    "source": recipe.source,
                    "source_dataset": recipe.source_dataset,
                    "cuisine": recipe.cuisine,
                    "cuisines": recipe.cuisines,
                    "diet": recipe.diet,
                    "total_time_minutes": recipe.total_time_minutes,
                    "ingredients": recipe.ingredients,
                    "tags": recipe.tags,
                    "rating": recipe.rating,
                },
            )
        )
    return documents


def export_jsonl(items: list[Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = item.model_dump() if hasattr(item, "model_dump") else item
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def chunk_text(text: str, max_chars: int = 700) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    return [cleaned[index : index + max_chars] for index in range(0, len(cleaned), max_chars)]


def build_recipe_id(row: dict[str, Any], dataset_name: str, index: int) -> str:
    original = first_non_empty(row, ID_KEYS)
    if original is None:
        return f"{slugify(dataset_name)}-{index}"
    return f"{slugify(dataset_name)}-{slugify(str(original))}"


def first_non_empty(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None and not is_nan(value):
            return value
    return None


def normalize_text(value: Any) -> str | None:
    if value is None or is_nan(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_list(value: Any) -> list[str]:
    if value is None or is_nan(value):
        return []
    if isinstance(value, list):
        return [clean_item(item) for item in value if clean_item(item)]
    if isinstance(value, str):
        parsed = try_parse_structured_text(value)
        if isinstance(parsed, list):
            return [clean_item(item) for item in parsed if clean_item(item)]
        separators = "\n" if "\n" in value else "|"
        if separators in value:
            return [clean_item(item) for item in value.split(separators) if clean_item(item)]
        if "," in value:
            return [clean_item(item) for item in value.split(",") if clean_item(item)]
        return [clean_item(value)] if clean_item(value) else []
    return [clean_item(value)] if clean_item(value) else []


def normalize_instructions(value: Any) -> list[str]:
    items = normalize_list(value)
    if len(items) == 1:
        single = items[0]
        split_steps = [
            clean_item(step)
            for step in re.split(r"(?:\d+\.\s+)|(?:\s*;\s*)", single)
            if clean_item(step)
        ]
        if len(split_steps) > 1:
            return split_steps
    return items


def normalize_minutes(value: Any) -> int | None:
    if value is None or is_nan(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text.startswith("pt"):
        hours = re.search(r"(\d+)h", text)
        minutes = re.search(r"(\d+)m", text)
        total = 0
        if hours:
            total += int(hours.group(1)) * 60
        if minutes:
            total += int(minutes.group(1))
        return total or None
    if text.isdigit():
        return int(text)

    hours_match = re.search(r"(\d+)\s*h", text)
    minutes_match = re.search(r"(\d+)\s*m", text)
    total = 0
    if hours_match:
        total += int(hours_match.group(1)) * 60
    if minutes_match:
        total += int(minutes_match.group(1))
    return total or None


def normalize_rating(value: Any) -> float | None:
    if value is None or is_nan(value):
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def infer_diet(*, title: str, ingredients: list[str], tags: list[str]) -> str | None:
    haystack = " ".join([title, *ingredients, *tags]).lower()
    if any(term in haystack for term in NON_VEGETARIAN_TERMS):
        if any(term in haystack for term in PESCATARIAN_TERMS):
            return "pescatarian"
        return "non_vegetarian"
    if any(term in haystack for term in EGG_TERMS):
        return "eggetarian"
    if any(term in haystack for term in VEGAN_BLOCKERS):
        return "vegetarian"
    if "vegan" in haystack:
        return "vegan"
    if "vegetarian" in haystack or "veg" in haystack:
        return "vegetarian"
    return None


def infer_cuisines(*, title: str, raw_cuisine: str | None, tags: list[str]) -> list[str]:
    candidates: list[str] = []
    if raw_cuisine:
        candidates.extend(normalize_list(raw_cuisine))
    candidates.extend(tags)
    candidates.append(title)

    haystack = " | ".join(candidates).lower()
    matches = [cuisine.title() for cuisine in sorted(KNOWN_CUISINES) if cuisine in haystack]

    if raw_cuisine:
        normalized_raw = [item.title() for item in normalize_list(raw_cuisine)]
        matches = normalized_raw + [item for item in matches if item not in normalized_raw]

    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in matches:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduplicated.append(item)
    return deduplicated


def clean_item(value: Any) -> str | None:
    if value is None or is_nan(value):
        return None
    text = str(value).strip().strip("\"'")
    return re.sub(r"\s+", " ", text) or None


def try_parse_structured_text(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    if text.startswith("[") or text.startswith("{"):
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(text)
            except (json.JSONDecodeError, SyntaxError, ValueError):
                continue
    return None


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)
