from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
import re

from app.schemas import AgentInput, RecipeRecord


ALLERGY_ALIASES: dict[str, set[str]] = {
    'dairy': {'milk', 'cheese', 'paneer', 'yogurt', 'butter', 'cream'},
    'peanut': {'peanut', 'peanuts'},
    'egg': {'egg', 'eggs'},
    'gluten': {'flour', 'bread', 'pasta', 'wheat', 'tortilla'},
    'shellfish': {'shrimp', 'prawn', 'crab', 'lobster'},
    'soy': {'soy', 'tofu', 'soy sauce'},
    'tree_nut': {'cashew', 'almond', 'walnut', 'pistachio'},
}


@dataclass
class IndexedCandidateResult:
    total_recipes: int
    candidates: list[RecipeRecord]
    base_scores: dict[str, float]


class IndexedRecipeRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._total_recipes: int | None = None

    def is_available(self) -> bool:
        return self.db_path.exists()

    def list_recipes(self) -> list[RecipeRecord]:
        if not self.is_available():
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    recipe_id,
                    title,
                    description,
                    cuisine,
                    cuisines_json,
                    diet,
                    total_time_minutes,
                    prep_time_minutes,
                    cook_time_minutes,
                    servings,
                    ingredients_json,
                    instructions_json,
                    tags_json,
                    rating,
                    image_url,
                    source_url,
                    source,
                    source_dataset,
                    popularity_count
                FROM recipes
                ORDER BY popularity_count DESC, rating DESC, title ASC
                LIMIT 1000
                """
            ).fetchall()
        return [self._row_to_recipe(row) for row in rows]

    def get_recipe(self, recipe_id: str) -> RecipeRecord | None:
        if not self.is_available():
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    recipe_id,
                    title,
                    description,
                    cuisine,
                    cuisines_json,
                    diet,
                    total_time_minutes,
                    prep_time_minutes,
                    cook_time_minutes,
                    servings,
                    ingredients_json,
                    instructions_json,
                    tags_json,
                    rating,
                    image_url,
                    source_url,
                    source,
                    source_dataset,
                    popularity_count
                FROM recipes
                WHERE recipe_id = ?
                """,
                (recipe_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_recipe(row)

    def search(self, *, agent_input: AgentInput, limit: int = 250) -> IndexedCandidateResult:
        if not self.is_available():
            return IndexedCandidateResult(total_recipes=0, candidates=[], base_scores={})

        query = self._build_search_query(agent_input)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total_recipes = self._get_total_recipes(conn)
            candidates, base_scores = self._search_with_filters(conn, agent_input, query, limit)
            if not candidates:
                candidates, base_scores = self._search_without_text(conn, agent_input, limit)
        return IndexedCandidateResult(
            total_recipes=total_recipes,
            candidates=candidates,
            base_scores=base_scores,
        )

    def _search_with_filters(
        self,
        conn: sqlite3.Connection,
        agent_input: AgentInput,
        query: str,
        limit: int,
    ) -> tuple[list[RecipeRecord], dict[str, float]]:
        if not query:
            return [], {}

        where_sql, params = self._build_metadata_sql(agent_input)
        sql = f"""
            SELECT
                r.recipe_id,
                r.title,
                r.description,
                r.cuisine,
                r.cuisines_json,
                r.diet,
                r.total_time_minutes,
                r.prep_time_minutes,
                r.cook_time_minutes,
                r.servings,
                r.ingredients_json,
                r.instructions_json,
                r.tags_json,
                r.rating,
                r.image_url,
                r.source_url,
                r.source,
                r.source_dataset,
                r.popularity_count,
                bm25(recipe_fts) AS fts_rank
            FROM recipe_fts
            JOIN recipes r ON r.recipe_id = recipe_fts.recipe_id
            WHERE recipe_fts MATCH ? {where_sql}
            ORDER BY bm25(recipe_fts), r.popularity_count DESC, r.rating DESC
            LIMIT ?
        """
        rows = conn.execute(sql, [query, *params, limit]).fetchall()
        if not rows:
            return [], {}
        recipes = [self._row_to_recipe(row) for row in rows]
        base_scores = {
            row['recipe_id']: self._compose_base_score(
                fts_rank=row['fts_rank'],
                popularity=row['popularity_count'],
                rating=row['rating'],
            )
            for row in rows
        }
        return recipes, base_scores

    def _search_without_text(
        self,
        conn: sqlite3.Connection,
        agent_input: AgentInput,
        limit: int,
    ) -> tuple[list[RecipeRecord], dict[str, float]]:
        where_sql, params = self._build_metadata_sql(agent_input)
        sql = f"""
            SELECT
                recipe_id,
                title,
                description,
                cuisine,
                cuisines_json,
                diet,
                total_time_minutes,
                prep_time_minutes,
                cook_time_minutes,
                servings,
                ingredients_json,
                instructions_json,
                tags_json,
                rating,
                image_url,
                source_url,
                source,
                source_dataset,
                popularity_count
            FROM recipes
            WHERE 1=1 {where_sql}
            ORDER BY popularity_count DESC, rating DESC, title ASC
            LIMIT ?
        """
        rows = conn.execute(sql, [*params, limit]).fetchall()
        recipes = [self._row_to_recipe(row) for row in rows]
        base_scores = {
            row['recipe_id']: self._compose_base_score(
                fts_rank=None,
                popularity=row['popularity_count'],
                rating=row['rating'],
            )
            for row in rows
        }
        return recipes, base_scores

    def _build_search_query(self, agent_input: AgentInput) -> str:
        preferred_terms: list[str] = []
        for cuisine in agent_input.detected_preferences.cuisines:
            preferred_terms.extend(item.lower() for item in cuisine.split())
        if agent_input.detected_preferences.diet:
            preferred_terms.extend(agent_input.detected_preferences.diet.replace('_', ' ').split())
        preferred_terms.extend(item.lower() for item in agent_input.detected_preferences.available_ingredients)

        candidate_terms = []
        seen: set[str] = set()
        for term in [*preferred_terms, *agent_input.query_tokens]:
            cleaned = term.strip().lower()
            if not cleaned or cleaned in seen or len(cleaned) <= 1:
                continue
            seen.add(cleaned)
            candidate_terms.append(cleaned)

        if not candidate_terms:
            return ''

        prioritized = candidate_terms[:6]
        return ' '.join(f'"{term}"' for term in prioritized)

    def _build_metadata_sql(self, agent_input: AgentInput) -> tuple[str, list[object]]:
        preferences = agent_input.detected_preferences
        clauses: list[str] = []
        params: list[object] = []

        if preferences.cuisines:
            cuisine_clauses = []
            for cuisine in preferences.cuisines:
                lowered = cuisine.lower()
                cuisine_clauses.append('(lower(cuisine) = ? OR lower(cuisines_text) LIKE ?)')
                params.extend([lowered, f'%{lowered}%'])
            clauses.append('AND (' + ' OR '.join(cuisine_clauses) + ')')

        if preferences.diet:
            allowed = sorted(self._allowed_diets(preferences.diet))
            placeholders = ', '.join('?' for _ in allowed)
            clauses.append(f'AND (diet IS NULL OR lower(diet) IN ({placeholders}))')
            params.extend(allowed)

        if preferences.max_cooking_time_minutes is not None:
            clauses.append('AND (total_time_minutes IS NULL OR total_time_minutes <= ?)')
            params.append(preferences.max_cooking_time_minutes)

        if preferences.available_ingredients:
            ingredient_clauses = []
            for item in preferences.available_ingredients[:8]:
                lowered = item.lower()
                ingredient_clauses.append('lower(ingredients_text) LIKE ?')
                params.append(f'%{lowered}%')
            clauses.append('AND (' + ' OR '.join(ingredient_clauses) + ')')

        blocked_terms = self._blocked_terms(agent_input)
        for term in sorted(blocked_terms)[:24]:
            clauses.append('AND lower(ingredients_text) NOT LIKE ?')
            params.append(f'%{term}%')

        return (' ' + ' '.join(clauses)) if clauses else '', params

    def _allowed_diets(self, requested: str) -> set[str]:
        requested_key = requested.lower()
        compatibility = {
            'vegetarian': {'vegetarian', 'vegan', 'eggetarian'},
            'vegan': {'vegan'},
            'eggetarian': {'eggetarian', 'vegetarian'},
            'pescatarian': {'pescatarian', 'vegetarian', 'vegan'},
            'non_vegetarian': {'non_vegetarian', 'pescatarian', 'eggetarian'},
        }
        return compatibility.get(requested_key, {requested_key})

    def _blocked_terms(self, agent_input: AgentInput) -> set[str]:
        terms = {item.lower() for item in agent_input.detected_preferences.excluded_ingredients}
        for allergy in agent_input.detected_preferences.allergies:
            allergy_key = allergy.lower()
            terms.add(allergy_key)
            terms.update(ALLERGY_ALIASES.get(allergy_key, {allergy_key}))
        return {term for term in terms if term}

    def _compose_base_score(
        self,
        *,
        fts_rank: float | None,
        popularity: int | None,
        rating: float | None,
    ) -> float:
        popularity_part = 0.2 * self._safe_log(popularity or 0)
        rating_part = 0.15 * ((rating or 0.0) / 5.0)
        if fts_rank is None:
            return popularity_part + rating_part
        lexical_part = 1.0 / (1.0 + max(fts_rank, 0.0))
        return (0.65 * lexical_part) + popularity_part + rating_part

    def _safe_log(self, value: int) -> float:
        import math
        return math.log1p(max(value, 0))

    def _row_to_recipe(self, row: sqlite3.Row) -> RecipeRecord:
        ingredients = _decode_list_field(row['ingredients_json'])
        instructions = _decode_list_field(row['instructions_json'])
        tags = _decode_list_field(row['tags_json'])
        cuisines = _decode_list_field(row['cuisines_json'])
        return RecipeRecord(
            recipe_id=row['recipe_id'],
            source=row['source'],
            source_dataset=row['source_dataset'],
            title=row['title'],
            description=row['description'],
            cuisine=row['cuisine'],
            cuisines=cuisines,
            diet=row['diet'],
            total_time_minutes=row['total_time_minutes'],
            prep_time_minutes=row['prep_time_minutes'],
            cook_time_minutes=row['cook_time_minutes'],
            servings=row['servings'],
            ingredients=ingredients,
            instructions=instructions,
            tags=tags,
            rating=row['rating'],
            image_url=row['image_url'],
            source_url=row['source_url'],
        )

    def _get_total_recipes(self, conn: sqlite3.Connection) -> int:
        if self._total_recipes is None:
            self._total_recipes = int(conn.execute('SELECT COUNT(*) FROM recipes').fetchone()[0])
        return self._total_recipes


def _decode_list_field(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = []
    if not isinstance(parsed, list):
        return []
    return _normalize_dirty_list(parsed)


def _normalize_dirty_list(values: list[object]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text.startswith('c("') or text == 'c(':
            text = text[2:].strip()
        text = text.strip()
        text = re.sub(r'^[\(\[]+', '', text)
        text = re.sub(r'[\)\]]+$', '', text)
        text = text.strip().strip('"').strip("'").strip()
        if text:
            normalized.append(text)
    return normalized
