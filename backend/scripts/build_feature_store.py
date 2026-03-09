from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pandas as pd
import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build feature-store tables in Postgres from Food.com data.")
    parser.add_argument(
        "--recipes-path",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_recipes.csv"),
    )
    parser.add_argument(
        "--interactions-path",
        type=Path,
        default=Path("backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/RAW_interactions.csv"),
    )
    parser.add_argument(
        "--postgres-dsn",
        type=str,
        default="postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy",
    )
    parser.add_argument(
        "--min-rating-threshold",
        type=float,
        default=4.0,
        help="Used for positive interaction counts in user features.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run row-count/null checks after table build.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    recipes_path = resolve_foodcom_path(
        args.recipes_path,
        fallback=Path(
            "backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv"
        ),
    )
    interactions_path = resolve_foodcom_path(
        args.interactions_path,
        fallback=Path(
            "backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/reviews.csv"
        ),
    )

    recipes = read_recipes(recipes_path)
    interactions = read_interactions(interactions_path)

    recipe_features = build_recipe_features(recipes, interactions)
    user_features = build_user_features(interactions, args.min_rating_threshold)
    interaction_features = build_interaction_features(interactions)

    with psycopg.connect(args.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            create_tables(cur)
            load_dataframe(cur, "recipe_features", recipe_features)
            load_dataframe(cur, "user_features", user_features)
            load_dataframe(cur, "interaction_features", interaction_features)

            if args.validate:
                run_validations(cur, recipe_features, user_features, interaction_features)

    print(
        {
            "recipe_features_rows": int(len(recipe_features)),
            "user_features_rows": int(len(user_features)),
            "interaction_features_rows": int(len(interaction_features)),
        }
    )


def build_recipe_features(recipes: pd.DataFrame, interactions: pd.DataFrame) -> pd.DataFrame:
    agg = interactions.groupby("recipe_id").agg(
        popularity_count=("recipe_id", "count"),
        avg_rating=("rating", "mean"),
        rating_count=("rating", "count"),
        rating_std=("rating", "std"),
    )
    result = recipes.merge(agg, how="left", left_on="recipe_id", right_index=True)
    result["popularity_count"] = result["popularity_count"].fillna(0).astype("int64")
    result["avg_rating"] = result["avg_rating"].fillna(0.0).astype("float64")
    result["rating_count"] = result["rating_count"].fillna(0).astype("int64")
    result["rating_std"] = result["rating_std"].fillna(0.0).astype("float64")
    result["minutes"] = result["minutes"].fillna(0).astype("int64")
    result["n_ingredients"] = result["n_ingredients"].fillna(0).astype("int64")
    return result[
        [
            "recipe_id",
            "minutes",
            "n_ingredients",
            "popularity_count",
            "avg_rating",
            "rating_count",
            "rating_std",
        ]
    ]


def build_user_features(interactions: pd.DataFrame, positive_threshold: float) -> pd.DataFrame:
    temp = interactions.copy()
    temp["is_positive"] = (temp["rating"] >= positive_threshold).astype("int64")
    agg = temp.groupby("user_id").agg(
        interaction_count=("recipe_id", "count"),
        unique_recipes=("recipe_id", pd.Series.nunique),
        avg_rating=("rating", "mean"),
        positive_count=("is_positive", "sum"),
        first_interaction=("date", "min"),
        last_interaction=("date", "max"),
    )
    agg["days_active"] = (
        (agg["last_interaction"] - agg["first_interaction"]).dt.days.clip(lower=0) + 1
    )
    agg["activity_per_day"] = agg["interaction_count"] / agg["days_active"]
    agg["avg_rating"] = agg["avg_rating"].fillna(0.0)
    agg["activity_per_day"] = agg["activity_per_day"].fillna(0.0)
    agg = agg.reset_index()
    return agg[
        [
            "user_id",
            "interaction_count",
            "unique_recipes",
            "avg_rating",
            "positive_count",
            "days_active",
            "activity_per_day",
            "first_interaction",
            "last_interaction",
        ]
    ]


def build_interaction_features(interactions: pd.DataFrame) -> pd.DataFrame:
    df = interactions.copy()
    df["rating_z"] = (df["rating"] - df["rating"].mean()) / max(df["rating"].std(), 1e-9)
    df["interaction_recency_days"] = (df["date"].max() - df["date"]).dt.days.astype("int64")
    return df[["user_id", "recipe_id", "rating", "rating_z", "date", "interaction_recency_days"]]


def create_tables(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_features (
            recipe_id BIGINT PRIMARY KEY,
            minutes INTEGER NOT NULL,
            n_ingredients INTEGER NOT NULL,
            popularity_count BIGINT NOT NULL,
            avg_rating DOUBLE PRECISION NOT NULL,
            rating_count BIGINT NOT NULL,
            rating_std DOUBLE PRECISION NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_features (
            user_id BIGINT PRIMARY KEY,
            interaction_count BIGINT NOT NULL,
            unique_recipes BIGINT NOT NULL,
            avg_rating DOUBLE PRECISION NOT NULL,
            positive_count BIGINT NOT NULL,
            days_active BIGINT NOT NULL,
            activity_per_day DOUBLE PRECISION NOT NULL,
            first_interaction TIMESTAMP NOT NULL,
            last_interaction TIMESTAMP NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS interaction_features (
            user_id BIGINT NOT NULL,
            recipe_id BIGINT NOT NULL,
            rating DOUBLE PRECISION NOT NULL,
            rating_z DOUBLE PRECISION NOT NULL,
            interaction_ts TIMESTAMP NOT NULL,
            interaction_recency_days BIGINT NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_interaction_features_user ON interaction_features(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_interaction_features_recipe ON interaction_features(recipe_id);")


def load_dataframe(cur: psycopg.Cursor, table_name: str, frame: pd.DataFrame) -> None:
    if table_name == "recipe_features":
        cur.execute("TRUNCATE TABLE recipe_features;")
        records = [
            tuple(row)
            for row in frame[
                [
                    "recipe_id",
                    "minutes",
                    "n_ingredients",
                    "popularity_count",
                    "avg_rating",
                    "rating_count",
                    "rating_std",
                ]
            ].itertuples(index=False, name=None)
        ]
        cur.executemany(
            """
            INSERT INTO recipe_features (
                recipe_id, minutes, n_ingredients, popularity_count, avg_rating, rating_count, rating_std
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            records,
        )
        return

    if table_name == "user_features":
        cur.execute("TRUNCATE TABLE user_features;")
        records = [
            tuple(row)
            for row in frame[
                [
                    "user_id",
                    "interaction_count",
                    "unique_recipes",
                    "avg_rating",
                    "positive_count",
                    "days_active",
                    "activity_per_day",
                    "first_interaction",
                    "last_interaction",
                ]
            ].itertuples(index=False, name=None)
        ]
        cur.executemany(
            """
            INSERT INTO user_features (
                user_id, interaction_count, unique_recipes, avg_rating, positive_count,
                days_active, activity_per_day, first_interaction, last_interaction
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            records,
        )
        return

    if table_name == "interaction_features":
        cur.execute("TRUNCATE TABLE interaction_features;")
        records = [
            tuple(row)
            for row in frame[
                ["user_id", "recipe_id", "rating", "rating_z", "date", "interaction_recency_days"]
            ].itertuples(index=False, name=None)
        ]
        cur.executemany(
            """
            INSERT INTO interaction_features (
                user_id, recipe_id, rating, rating_z, interaction_ts, interaction_recency_days
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            records,
        )
        return

    raise ValueError(f"Unsupported table name: {table_name}")


def run_validations(
    cur: psycopg.Cursor,
    recipe_features: pd.DataFrame,
    user_features: pd.DataFrame,
    interaction_features: pd.DataFrame,
) -> None:
    expected = {
        "recipe_features": len(recipe_features),
        "user_features": len(user_features),
        "interaction_features": len(interaction_features),
    }
    for table_name, expected_rows in expected.items():
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        actual = int(cur.fetchone()[0])
        if actual != expected_rows:
            raise RuntimeError(
                f"Validation failed: {table_name} expected {expected_rows} rows, found {actual}."
            )

    null_checks = {
        "recipe_features": ["recipe_id", "minutes", "popularity_count"],
        "user_features": ["user_id", "interaction_count", "last_interaction"],
        "interaction_features": ["user_id", "recipe_id", "interaction_ts"],
    }
    for table_name, cols in null_checks.items():
        for col in cols:
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL")
            null_count = int(cur.fetchone()[0])
            if null_count != 0:
                raise RuntimeError(f"Validation failed: {table_name}.{col} has {null_count} NULL values.")


def read_recipes(path: Path) -> pd.DataFrame:
    if path.name.lower().startswith("raw_"):
        frame = pd.read_csv(
            path,
            usecols=["id", "minutes", "n_ingredients"],
            dtype={"id": "int64"},
        ).rename(columns={"id": "recipe_id"})
        return frame
    frame = pd.read_csv(
        path,
        usecols=["RecipeId", "TotalTime", "RecipeIngredientParts"],
        dtype={"RecipeId": "int64"},
    )
    frame = frame.rename(
        columns={
            "RecipeId": "recipe_id",
            "TotalTime": "total_time",
            "RecipeIngredientParts": "ingredients",
        }
    )
    frame["minutes"] = frame["total_time"].apply(parse_iso_duration_minutes)
    frame["n_ingredients"] = frame["ingredients"].apply(count_list_items)
    return frame[["recipe_id", "minutes", "n_ingredients"]]


def read_interactions(path: Path) -> pd.DataFrame:
    if path.name.lower().startswith("raw_"):
        frame = pd.read_csv(
            path,
            usecols=["user_id", "recipe_id", "rating", "date"],
            parse_dates=["date"],
            dtype={"user_id": "int64", "recipe_id": "int64"},
        )
        return frame
    frame = pd.read_csv(
        path,
        usecols=["AuthorId", "RecipeId", "Rating", "DateSubmitted"],
        parse_dates=["DateSubmitted"],
        dtype={"AuthorId": "int64", "RecipeId": "int64"},
    )
    frame = frame.rename(
        columns={
            "AuthorId": "user_id",
            "RecipeId": "recipe_id",
            "Rating": "rating",
            "DateSubmitted": "date",
        }
    )
    return frame[["user_id", "recipe_id", "rating", "date"]]


def parse_iso_duration_minutes(value: object) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if not isinstance(value, str):
        return int(value)
    text = value.strip()
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
            return 0
        return days * 1440 + hours * 60 + minutes
    return 0


def count_list_items(value: object) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if not isinstance(value, str):
        return 0
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, list):
                return len(parsed)
        except Exception:
            return 0
    return 0

def resolve_foodcom_path(primary: Path, *, fallback: Path) -> Path:
    if primary.exists():
        return primary
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Expected dataset at {primary} or {fallback}")


if __name__ == "__main__":
    main()
