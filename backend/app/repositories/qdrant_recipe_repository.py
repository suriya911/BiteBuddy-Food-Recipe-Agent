from __future__ import annotations

from typing import Iterable
import ast
import html
import pandas as pd
import sqlite3
import json
from pathlib import Path

from qdrant_client import QdrantClient

from app.schemas import RecipeRecord


class QdrantRecipeRepository:
    def __init__(
        self,
        *,
        qdrant_url: str,
        collections: Iterable[str],
        recipes_csv_path: str | None = None,
        details_db_path: str | None = None,
    ) -> None:
        self.client = QdrantClient(url=qdrant_url)
        self.collections = list(collections)
        self.recipes_csv_path = recipes_csv_path
        self.details_db_path = details_db_path
        self._recipe_cache: dict[int, RecipeRecord] = {}

    def list_recipes(self) -> list[RecipeRecord]:
        return []

    def get_recipe(self, recipe_id: str) -> RecipeRecord | None:
        try:
            point_id = int(recipe_id)
        except ValueError:
            point_id = recipe_id
        for collection in self.collections:
            try:
                points = self.client.retrieve(
                    collection_name=collection,
                    ids=[point_id],
                    with_payload=True,
                )
            except Exception:
                continue
            if not points:
                continue
            payload = points[0].payload or {}
            base = RecipeRecord(
                recipe_id=str(payload.get("recipe_id") or recipe_id),
                source="qdrant",
                source_dataset=collection,
                title=str(payload.get("title") or ""),
                description=None,
                cuisine=payload.get("cuisine"),
                cuisines=[],
                diet=payload.get("diet"),
                total_time_minutes=payload.get("total_time_minutes"),
                prep_time_minutes=None,
                cook_time_minutes=None,
                servings=None,
                ingredients=normalize_list(payload.get("ingredients")) or [],
                instructions=normalize_list(payload.get("instructions")) or [],
                tags=[],
                rating=None,
                image_url=None,
                source_url=None,
            )
            if (not base.instructions or not base.ingredients) and self.recipes_csv_path:
                enriched = self._load_from_csv(int(base.recipe_id))
                if enriched:
                    return enriched
            return base
        if self.recipes_csv_path:
            return self._load_from_csv(int(recipe_id))
        return None

    def _load_from_csv(self, recipe_id: int) -> RecipeRecord | None:
        cached = self._recipe_cache.get(recipe_id)
        if cached:
            return cached
        from_db = self._load_from_db(recipe_id)
        if from_db:
            self._recipe_cache[recipe_id] = from_db
            return from_db
        if not self.recipes_csv_path:
            return None
        for chunk in pd.read_csv(
            self.recipes_csv_path,
            usecols=[
                "RecipeId",
                "Name",
                "Description",
                "TotalTime",
                "RecipeIngredientParts",
                "RecipeInstructions",
                "RecipeCategory",
                "Keywords",
                "RecipeYield",
            ],
            chunksize=5000,
        ):
            match = chunk[chunk["RecipeId"] == recipe_id]
            if match.empty:
                continue
            row = match.iloc[0].to_dict()
            ingredients = normalize_list(row.get("RecipeIngredientParts"))
            instructions = normalize_list(row.get("RecipeInstructions"))
            tags = normalize_list(row.get("Keywords"))
            title = html.unescape(str(row.get("Name") or ""))
            record = RecipeRecord(
                recipe_id=str(recipe_id),
                source="foodcom",
                source_dataset="recipes.csv",
                title=title,
                description=html.unescape(str(row.get("Description") or "")) or None,
                cuisine=str(row.get("RecipeCategory") or None) if row.get("RecipeCategory") else None,
                cuisines=[],
                diet=None,
                total_time_minutes=parse_iso_duration_minutes(row.get("TotalTime")),
                prep_time_minutes=None,
                cook_time_minutes=None,
                servings=str(row.get("RecipeYield") or "") or None,
                ingredients=ingredients,
                instructions=instructions,
                tags=tags,
                rating=None,
                image_url=None,
                source_url=None,
            )
            self._recipe_cache[recipe_id] = record
            return record
        return None

    def _load_from_db(self, recipe_id: int) -> RecipeRecord | None:
        if not self.details_db_path:
            return None
        db_path = Path(self.details_db_path)
        if not db_path.exists():
            return None
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT recipe_id, title, description, total_time_minutes, ingredients_json,
                       instructions_json, tags_json, category, recipe_yield
                FROM recipe_details
                WHERE recipe_id = ?
                """,
                (recipe_id,),
            ).fetchone()
        if row is None:
            return None
        ingredients = json_to_list(row["ingredients_json"])
        instructions = json_to_list(row["instructions_json"])
        tags = json_to_list(row["tags_json"])
        record = RecipeRecord(
            recipe_id=str(row["recipe_id"]),
            source="foodcom",
            source_dataset="recipes.csv",
            title=str(row["title"] or ""),
            description=str(row["description"] or "") or None,
            cuisine=str(row["category"] or None) if row["category"] else None,
            cuisines=[],
            diet=None,
            total_time_minutes=row["total_time_minutes"],
            prep_time_minutes=None,
            cook_time_minutes=None,
            servings=str(row["recipe_yield"] or "") or None,
            ingredients=ingredients,
            instructions=instructions,
            tags=tags,
            rating=None,
            image_url=None,
            source_url=None,
        )
        return record


def normalize_list(raw: object) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.startswith("c("):
        return parse_r_c_vector(raw)
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    if isinstance(raw, str):
        return [token.strip() for token in raw.split(",") if token.strip()]
    return [str(raw)]


def json_to_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return []


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
