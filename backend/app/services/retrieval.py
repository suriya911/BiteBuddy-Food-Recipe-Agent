from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import AgentInput, RecipeMatch, RecipeRecord, RetrievalTrace


RELAXATION_ORDER = (
    "available_ingredients",
    "max_cooking_time_minutes",
    "cuisines",
    "diet",
)


@dataclass
class RetrievalResult:
    matches: list[RecipeMatch]
    trace: RetrievalTrace


class RetrievalService:
    def find_matches(
        self,
        *,
        recipes: list[RecipeRecord],
        agent_input: AgentInput,
        limit: int = 5,
    ) -> RetrievalResult:
        filtered = self._filter_metadata(recipes, agent_input)
        fallback_applied = False
        fallback_reason: str | None = None

        if not filtered:
            filtered, fallback_reason = self._relax_constraints(recipes, agent_input)
            fallback_applied = bool(filtered)

        ranked = self._rank(filtered, agent_input)[:limit]
        return RetrievalResult(
            matches=ranked,
            trace=RetrievalTrace(
                total_recipes=len(recipes),
                metadata_matches=len(filtered),
                vector_matches=len(ranked),
                fallback_applied=fallback_applied,
                fallback_reason=fallback_reason,
            ),
        )

    def _filter_metadata(
        self,
        recipes: list[RecipeRecord],
        agent_input: AgentInput,
    ) -> list[RecipeRecord]:
        preferences = agent_input.detected_preferences
        filtered = recipes

        if preferences.cuisines:
            target_cuisines = {item.lower() for item in preferences.cuisines}
            filtered = [
                recipe
                for recipe in filtered
                if recipe.cuisine
                and recipe.cuisine.lower() in target_cuisines
                or any(item.lower() in target_cuisines for item in recipe.cuisines)
            ]

        if preferences.diet:
            filtered = [
                recipe
                for recipe in filtered
                if self._diet_compatible(recipe.diet, preferences.diet)
            ]

        if preferences.max_cooking_time_minutes is not None:
            filtered = [
                recipe
                for recipe in filtered
                if recipe.total_time_minutes is None
                or recipe.total_time_minutes <= preferences.max_cooking_time_minutes
            ]

        if preferences.available_ingredients:
            wanted = {item.lower() for item in preferences.available_ingredients}
            filtered = [
                recipe
                for recipe in filtered
                if wanted.intersection({item.lower() for item in recipe.ingredients})
            ]

        if preferences.excluded_ingredients:
            blocked_ingredients = {item.lower() for item in preferences.excluded_ingredients}
            filtered = [
                recipe
                for recipe in filtered
                if not blocked_ingredients.intersection(
                    {item.lower() for item in recipe.ingredients},
                )
            ]

        if preferences.allergies:
            blocked = {item.lower() for item in preferences.allergies}
            filtered = [
                recipe
                for recipe in filtered
                if not self._contains_allergy(recipe, blocked)
            ]

        return filtered

    def _relax_constraints(
        self,
        recipes: list[RecipeRecord],
        agent_input: AgentInput,
    ) -> tuple[list[RecipeRecord], str | None]:
        preferences = agent_input.detected_preferences.model_copy(deep=True)
        for field_name in RELAXATION_ORDER:
            if not getattr(preferences, field_name):
                continue
            if field_name == "available_ingredients":
                preferences.available_ingredients = []
            elif field_name == "max_cooking_time_minutes":
                preferences.max_cooking_time_minutes = None
            elif field_name == "cuisines":
                preferences.cuisines = []
            elif field_name == "diet":
                preferences.diet = None

            relaxed_input = agent_input.model_copy(deep=True)
            relaxed_input.detected_preferences = preferences
            filtered = self._filter_metadata(recipes, relaxed_input)
            if filtered:
                return filtered, f"Relaxed {field_name.replace('_', ' ')} constraint."

        return [], None

    def _rank(
        self,
        recipes: list[RecipeRecord],
        agent_input: AgentInput,
    ) -> list[RecipeMatch]:
        query_tokens = set(agent_input.query_tokens)
        matches: list[RecipeMatch] = []
        for recipe in recipes:
            searchable = " ".join(
                [
                    recipe.title,
                    recipe.description or "",
                    " ".join(recipe.ingredients),
                    " ".join(recipe.tags),
                    " ".join(recipe.instructions),
                ],
            ).lower()
            recipe_tokens = set(re.findall(r"[a-zA-Z]+", searchable))
            overlap = query_tokens.intersection(recipe_tokens)
            score = float(len(overlap))
            if recipe.rating is not None:
                score += recipe.rating / 5
            if agent_input.detected_preferences.available_ingredients:
                ingredient_overlap = set(
                    item.lower() for item in agent_input.detected_preferences.available_ingredients
                ).intersection({item.lower() for item in recipe.ingredients})
                score += len(ingredient_overlap) * 1.5

            reasons = self._build_match_reasons(recipe, agent_input, overlap)
            matches.append(
                RecipeMatch(
                    recipe_id=recipe.recipe_id,
                    title=recipe.title,
                    cuisine=recipe.cuisine,
                    cuisines=recipe.cuisines,
                    diet=recipe.diet,
                    total_time_minutes=recipe.total_time_minutes,
                    ingredients=recipe.ingredients,
                    score=round(score, 2),
                    match_reasons=reasons,
                ),
            )

        return sorted(matches, key=lambda item: item.score, reverse=True)

    def _build_match_reasons(
        self,
        recipe: RecipeRecord,
        agent_input: AgentInput,
        overlap: set[str],
    ) -> list[str]:
        reasons: list[str] = []
        preferences = agent_input.detected_preferences
        if preferences.cuisines and any(
            cuisine.lower() in {recipe.cuisine.lower()} if recipe.cuisine else set()
            for cuisine in preferences.cuisines
        ):
            reasons.append("Matches preferred cuisine.")
        if preferences.diet and recipe.diet == preferences.diet:
            reasons.append("Matches diet preference.")
        if preferences.max_cooking_time_minutes and recipe.total_time_minutes is not None:
            if recipe.total_time_minutes <= preferences.max_cooking_time_minutes:
                reasons.append("Fits cooking time limit.")
        if preferences.available_ingredients:
            requested = {item.lower() for item in preferences.available_ingredients}
            available = {item.lower() for item in recipe.ingredients}
            ingredient_overlap = requested.intersection(available)
            if ingredient_overlap:
                reasons.append(
                    "Uses requested ingredients: " + ", ".join(sorted(ingredient_overlap)),
                )
        if overlap:
            reasons.append("Relevant query terms: " + ", ".join(sorted(overlap)[:5]))
        if preferences.excluded_ingredients:
            blocked = {item.lower() for item in preferences.excluded_ingredients}
            if not blocked.intersection({item.lower() for item in recipe.ingredients}):
                reasons.append("Avoids excluded ingredients.")
        return reasons

    def _diet_compatible(self, recipe_diet: str | None, requested_diet: str) -> bool:
        if requested_diet == "vegetarian":
            return recipe_diet in {"vegetarian", "vegan", "eggetarian"}
        if requested_diet == "vegan":
            return recipe_diet == "vegan"
        if requested_diet == "eggetarian":
            return recipe_diet in {"eggetarian", "vegetarian"}
        if requested_diet == "pescatarian":
            return recipe_diet in {"pescatarian", "vegetarian", "vegan"}
        if requested_diet == "non_vegetarian":
            return recipe_diet in {"non_vegetarian", "pescatarian", "eggetarian"}
        return recipe_diet == requested_diet

    def _contains_allergy(self, recipe: RecipeRecord, blocked: set[str]) -> bool:
        haystack = " ".join(recipe.ingredients + recipe.tags + [recipe.title]).lower()
        aliases = {
            "dairy": {"milk", "cheese", "paneer", "yogurt", "butter", "cream"},
            "peanut": {"peanut", "peanuts"},
            "egg": {"egg", "eggs"},
            "gluten": {"flour", "bread", "pasta", "wheat", "tortilla"},
            "shellfish": {"shrimp", "prawn", "crab", "lobster"},
            "soy": {"soy", "tofu", "soy sauce"},
            "tree_nut": {"cashew", "almond", "walnut", "pistachio"},
        }
        for allergy in blocked:
            terms = aliases.get(allergy, {allergy})
            if any(term in haystack for term in terms):
                return True
        return False
