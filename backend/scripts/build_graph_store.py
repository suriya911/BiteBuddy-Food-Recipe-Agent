from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pandas as pd
import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a graph store in Postgres from Food.com recipes.")
    parser.add_argument(
        "--recipes-csv",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv"),
    )
    parser.add_argument(
        "--postgres-dsn",
        type=str,
        default="postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(
        args.recipes_csv,
        usecols=[
            "RecipeId",
            "Name",
            "RecipeCategory",
            "Keywords",
            "RecipeIngredientParts",
            "TotalTime",
        ],
    )

    with psycopg.connect(args.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            create_tables(cur)
            load_recipe_nodes(cur, frame)
            load_attribute_nodes(cur, frame)
            load_edges(cur, frame)
    print("Graph store built.")


def create_tables(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id BIGINT PRIMARY KEY,
            node_type TEXT NOT NULL,
            node_value TEXT NOT NULL,
            value_lc TEXT NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_edges (
            src_id BIGINT NOT NULL,
            dst_id BIGINT NOT NULL,
            edge_type TEXT NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_meta (
            recipe_id BIGINT PRIMARY KEY,
            title TEXT NOT NULL,
            total_time_minutes INTEGER
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_type_value ON graph_nodes(node_type, value_lc);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_src ON graph_edges(src_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_dst ON graph_edges(dst_id);")


def load_recipe_nodes(cur: psycopg.Cursor, frame: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE recipe_meta;")
    cur.execute("TRUNCATE TABLE graph_nodes;")
    rows = []
    meta_rows = []
    for row in frame.to_dict(orient="records"):
        recipe_id = int(row["RecipeId"])
        title = str(row.get("Name") or "")
        total_time = parse_iso_duration_minutes(row.get("TotalTime"))
        rows.append((recipe_id, "recipe", title, title.lower()))
        meta_rows.append((recipe_id, title, total_time))
    cur.executemany(
        "INSERT INTO graph_nodes (node_id, node_type, node_value, value_lc) VALUES (%s, %s, %s, %s)",
        rows,
    )
    cur.executemany(
        "INSERT INTO recipe_meta (recipe_id, title, total_time_minutes) VALUES (%s, %s, %s)",
        meta_rows,
    )


def load_attribute_nodes(cur: psycopg.Cursor, frame: pd.DataFrame) -> None:
    nodes: dict[tuple[str, str], int] = {}
    next_id = 1_000_000_000
    for row in frame.to_dict(orient="records"):
        cuisine = str(row.get("RecipeCategory") or "").strip()
        if cuisine:
            key = ("cuisine", cuisine)
            if key not in nodes:
                nodes[key] = next_id
                next_id += 1
        ingredients = parse_list_field(row.get("RecipeIngredientParts"))
        for ingredient in ingredients:
            if not ingredient:
                continue
            key = ("ingredient", ingredient)
            if key not in nodes:
                nodes[key] = next_id
                next_id += 1
        tags = parse_list_field(row.get("Keywords"))
        for tag in tags:
            if not tag:
                continue
            key = ("tag", tag)
            if key not in nodes:
                nodes[key] = next_id
                next_id += 1
    rows = [
        (node_id, node_type, node_value, node_value.lower())
        for (node_type, node_value), node_id in nodes.items()
    ]
    cur.executemany(
        "INSERT INTO graph_nodes (node_id, node_type, node_value, value_lc) VALUES (%s, %s, %s, %s)",
        rows,
    )


def load_edges(cur: psycopg.Cursor, frame: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE graph_edges;")
    edges = []
    node_lookup = {}
    for row in cur.execute("SELECT node_id, node_type, value_lc FROM graph_nodes"):
        node_lookup[(row[1], row[2])] = int(row[0])
    for row in frame.to_dict(orient="records"):
        recipe_id = int(row["RecipeId"])
        cuisine = str(row.get("RecipeCategory") or "").strip()
        if cuisine:
            dst = node_lookup.get(("cuisine", cuisine.lower()))
            if dst:
                edges.append((recipe_id, dst, "HAS_CUISINE"))
        for ingredient in parse_list_field(row.get("RecipeIngredientParts")):
            dst = node_lookup.get(("ingredient", ingredient.lower()))
            if dst:
                edges.append((recipe_id, dst, "HAS_INGREDIENT"))
        for tag in parse_list_field(row.get("Keywords")):
            dst = node_lookup.get(("tag", tag.lower()))
            if dst:
                edges.append((recipe_id, dst, "HAS_TAG"))
    cur.executemany(
        "INSERT INTO graph_edges (src_id, dst_id, edge_type) VALUES (%s, %s, %s)",
        edges,
    )


def parse_list_field(raw: object) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, str) and raw.startswith("c("):
        return parse_r_c_vector(raw)
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
    if isinstance(raw, str):
        return [token.strip() for token in raw.split(",") if token.strip()]
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
    return [item for item in (token.strip().lower() for token in items) if item]


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
