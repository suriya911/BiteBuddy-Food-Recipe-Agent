from __future__ import annotations

import argparse
import ast
import json
import sqlite3
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a recipe details cache for fast lookup.")
    parser.add_argument(
        "--recipes-csv",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv"),
    )
    parser.add_argument(
        "--output-db",
        type=Path,
        default=Path("backend/data/processed/recipe_details.sqlite"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS recipe_details;
            CREATE TABLE recipe_details (
                recipe_id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                total_time_minutes INTEGER,
                ingredients_json TEXT,
                instructions_json TEXT,
                tags_json TEXT,
                category TEXT,
                recipe_yield TEXT
            );
            """
        )
        insert_rows(conn, args.recipes_csv)
    print(f"Wrote {args.output_db}")


def insert_rows(conn: sqlite3.Connection, path: Path) -> None:
    for chunk in pd.read_csv(
        path,
        usecols=[
            "RecipeId",
            "Name",
            "Description",
            "TotalTime",
            "RecipeIngredientParts",
            "RecipeInstructions",
            "Keywords",
            "RecipeCategory",
            "RecipeYield",
        ],
        chunksize=5000,
    ):
        records = []
        for row in chunk.to_dict(orient="records"):
            recipe_id = int(row["RecipeId"])
            ingredients = normalize_list(row.get("RecipeIngredientParts"))
            instructions = normalize_list(row.get("RecipeInstructions"))
            tags = normalize_list(row.get("Keywords"))
            total_time = parse_iso_duration_minutes(row.get("TotalTime"))
            records.append(
                (
                    recipe_id,
                    str(row.get("Name") or ""),
                    str(row.get("Description") or ""),
                    total_time,
                    json.dumps(ingredients),
                    json.dumps(instructions),
                    json.dumps(tags),
                    str(row.get("RecipeCategory") or ""),
                    str(row.get("RecipeYield") or ""),
                )
            )
        conn.executemany(
            """
            INSERT INTO recipe_details (
                recipe_id, title, description, total_time_minutes, ingredients_json,
                instructions_json, tags_json, category, recipe_yield
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()


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


if __name__ == "__main__":
    main()
