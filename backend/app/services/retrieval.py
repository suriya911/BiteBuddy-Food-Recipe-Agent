from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.schemas import AgentInput, RecipeMatch, RecipeRecord, RetrievalTrace

if TYPE_CHECKING:
    from app.repositories.indexed_recipe_repository import IndexedRecipeRepository
    from app.services.neural_reranker import NeuralReranker
    from app.services.qdrant_retrieval import QdrantRetrievalService
    from app.services.graph_traversal import GraphTraversalService


RELAXATION_ORDER = (
    'available_ingredients',
    'max_cooking_time_minutes',
    'cuisines',
    'diet',
)

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
class RetrievalResult:
    matches: list[RecipeMatch]
    trace: RetrievalTrace


@dataclass
class CandidateSearchResult:
    total_recipes: int
    candidates: list[RecipeRecord]
    base_scores: dict[str, float]


class RetrievalService:
    def __init__(
        self,
        search_index: IndexedRecipeRepository | None = None,
        neural_reranker: NeuralReranker | None = None,
        qdrant_retrieval: QdrantRetrievalService | None = None,
        graph_traversal: GraphTraversalService | None = None,
        graph_weight: float = 0.3,
        vector_weight: float = 0.7,
        rerank_top_k: int = 25,
        indexed_candidate_limit: int = 120,
    ) -> None:
        self.search_index = search_index
        self.neural_reranker = neural_reranker
        self.qdrant_retrieval = qdrant_retrieval
        self.graph_traversal = graph_traversal
        self.graph_weight = graph_weight
        self.vector_weight = vector_weight
        self.rerank_top_k = rerank_top_k
        self.indexed_candidate_limit = indexed_candidate_limit

    def uses_index(self) -> bool:
        return bool(self.search_index and self.search_index.is_available())

    def find_matches(
        self,
        *,
        recipes: list[RecipeRecord] | None,
        agent_input: AgentInput,
        limit: int = 10,
    ) -> RetrievalResult:
        if self.qdrant_retrieval is not None:
            qdrant_result = self.qdrant_retrieval.search(agent_input)
            if self.graph_traversal is None:
                return RetrievalResult(
                    matches=qdrant_result.matches[:limit],
                    trace=qdrant_result.trace,
                )
            merged = self._merge_graph_vector(
                qdrant_result.matches,
                self.graph_traversal.traverse(agent_input),
            )
            return RetrievalResult(
                matches=merged[:limit],
                trace=qdrant_result.trace,
            )
        candidate_result = self._get_candidates(recipes=recipes, agent_input=agent_input)
        fallback_applied = False
        fallback_reason: str | None = None

        if not candidate_result.candidates:
            candidate_result, fallback_reason = self._relax_constraints(recipes, agent_input)
            fallback_applied = bool(candidate_result.candidates)

        ranked_items = self._rank(
            candidate_result.candidates,
            agent_input,
            candidate_result.base_scores,
        )
        if self.neural_reranker is not None:
            ranked_items = self.neural_reranker.rerank(
                query=agent_input.normalized_query,
                ranked_items=ranked_items,
                top_k=self.rerank_top_k,
            )
        ranked = [match for _, match in ranked_items[:limit]]
        return RetrievalResult(
            matches=ranked,
            trace=RetrievalTrace(
                total_recipes=candidate_result.total_recipes,
                metadata_matches=len(candidate_result.candidates),
                vector_matches=len(ranked),
                fallback_applied=fallback_applied,
                fallback_reason=fallback_reason,
            ),
        )

    def _merge_graph_vector(
        self,
        vector_matches: list[RecipeMatch],
        graph_candidates,
    ) -> list[RecipeMatch]:
        vector_scores = {match.recipe_id: match.score for match in vector_matches}
        graph_scores = {str(item.recipe_id): item for item in graph_candidates}
        combined_ids = set(vector_scores) | set(graph_scores)

        merged: list[RecipeMatch] = []
        for recipe_id in combined_ids:
            vec_score = vector_scores.get(recipe_id, 0.0)
            graph = graph_scores.get(recipe_id)
            graph_score = graph.score if graph else 0.0
            score = self.vector_weight * vec_score + self.graph_weight * graph_score
            base_match = next((m for m in vector_matches if m.recipe_id == recipe_id), None)
            if base_match:
                reasons = list(base_match.match_reasons)
                if graph:
                    reasons.extend(graph.reasons[:3])
                merged.append(
                    RecipeMatch(
                        recipe_id=base_match.recipe_id,
                        title=base_match.title,
                        cuisine=base_match.cuisine,
                        cuisines=base_match.cuisines,
                        diet=base_match.diet,
                        total_time_minutes=base_match.total_time_minutes,
                        ingredients=base_match.ingredients,
                        score=round(score, 4),
                        match_reasons=reasons[:5],
                    )
                )
            elif graph:
                merged.append(
                    RecipeMatch(
                        recipe_id=str(graph.recipe_id),
                        title=graph.title,
                        cuisine=None,
                        cuisines=[],
                        diet=None,
                        total_time_minutes=graph.total_time_minutes,
                        ingredients=[],
                        score=round(score, 4),
                        match_reasons=graph.reasons[:5],
                    )
                )
        return sorted(merged, key=lambda item: item.score, reverse=True)

    def _get_candidates(
        self,
        *,
        recipes: list[RecipeRecord] | None,
        agent_input: AgentInput,
    ) -> CandidateSearchResult:
        if self.uses_index():
            indexed = self.search_index.search(agent_input=agent_input, limit=self.indexed_candidate_limit)
            return CandidateSearchResult(
                total_recipes=indexed.total_recipes,
                candidates=indexed.candidates,
                base_scores=indexed.base_scores,
            )

        recipe_list = recipes or []
        filtered = self._filter_metadata(recipe_list, agent_input)
        return CandidateSearchResult(
            total_recipes=len(recipe_list),
            candidates=filtered,
            base_scores={},
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
                if self._recipe_matches_cuisines(recipe, target_cuisines)
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

        blocked_ingredients = self.expand_blocked_terms(
            preferences.excluded_ingredients,
            preferences.allergies,
        )
        if blocked_ingredients:
            filtered = [
                recipe
                for recipe in filtered
                if not blocked_ingredients.intersection(
                    {item.lower() for item in recipe.ingredients},
                )
            ]

        return filtered

    def _relax_constraints(
        self,
        recipes: list[RecipeRecord] | None,
        agent_input: AgentInput,
    ) -> tuple[CandidateSearchResult, str | None]:
        preferences = agent_input.detected_preferences.model_copy(deep=True)
        for field_name in RELAXATION_ORDER:
            if not getattr(preferences, field_name):
                continue
            if field_name == 'available_ingredients':
                preferences.available_ingredients = []
            elif field_name == 'max_cooking_time_minutes':
                preferences.max_cooking_time_minutes = None
            elif field_name == 'cuisines':
                preferences.cuisines = []
            elif field_name == 'diet':
                preferences.diet = None

            relaxed_input = agent_input.model_copy(deep=True)
            relaxed_input.detected_preferences = preferences
            candidate_result = self._get_candidates(recipes=recipes, agent_input=relaxed_input)
            if candidate_result.candidates:
                return candidate_result, f"Relaxed {field_name.replace('_', ' ')} constraint."

        return CandidateSearchResult(total_recipes=len(recipes or []), candidates=[], base_scores={}), None

    def _rank(
        self,
        recipes: list[RecipeRecord],
        agent_input: AgentInput,
        base_scores: dict[str, float] | None = None,
    ) -> list[tuple[RecipeRecord, RecipeMatch]]:
        query_tokens = set(agent_input.query_tokens)
        matches: list[tuple[RecipeRecord, RecipeMatch]] = []
        for recipe in recipes:
            searchable = ' '.join(
                [
                    recipe.title,
                    recipe.description or '',
                    ' '.join(recipe.ingredients),
                    ' '.join(recipe.tags),
                    ' '.join(recipe.instructions),
                ],
            ).lower()
            recipe_tokens = set(re.findall(r'[a-zA-Z]+', searchable))
            overlap = query_tokens.intersection(recipe_tokens)
            score = float(len(overlap))
            if base_scores:
                score += base_scores.get(recipe.recipe_id, 0.0) * 4.0
            if recipe.rating is not None:
                score += recipe.rating / 5
            if agent_input.detected_preferences.available_ingredients:
                ingredient_overlap = set(
                    item.lower() for item in agent_input.detected_preferences.available_ingredients
                ).intersection({item.lower() for item in recipe.ingredients})
                score += len(ingredient_overlap) * 1.5

            reasons = self._build_match_reasons(recipe, agent_input, overlap)
            match = RecipeMatch(
                recipe_id=recipe.recipe_id,
                title=recipe.title,
                cuisine=recipe.cuisine,
                cuisines=recipe.cuisines,
                diet=recipe.diet,
                total_time_minutes=recipe.total_time_minutes,
                ingredients=recipe.ingredients,
                score=round(score, 2),
                match_reasons=reasons,
            )
            matches.append((recipe, match))

        return sorted(matches, key=lambda item: item[1].score, reverse=True)

    def _build_match_reasons(
        self,
        recipe: RecipeRecord,
        agent_input: AgentInput,
        overlap: set[str],
    ) -> list[str]:
        reasons: list[str] = []
        preferences = agent_input.detected_preferences
        if preferences.cuisines and self._recipe_matches_cuisines(
            recipe,
            {item.lower() for item in preferences.cuisines},
        ):
            reasons.append('Matches preferred cuisine.')
        if preferences.diet and recipe.diet and self._diet_compatible(recipe.diet, preferences.diet):
            reasons.append('Matches diet preference.')
        if preferences.max_cooking_time_minutes and recipe.total_time_minutes is not None:
            if recipe.total_time_minutes <= preferences.max_cooking_time_minutes:
                reasons.append('Fits cooking time limit.')
        if preferences.available_ingredients:
            requested = {item.lower() for item in preferences.available_ingredients}
            available = {item.lower() for item in recipe.ingredients}
            ingredient_overlap = requested.intersection(available)
            if ingredient_overlap:
                reasons.append(
                    'Uses requested ingredients: ' + ', '.join(sorted(ingredient_overlap)[:5]),
                )
        if overlap:
            reasons.append('Relevant query terms: ' + ', '.join(sorted(overlap)[:5]))
        blocked = self.expand_blocked_terms(
            preferences.excluded_ingredients,
            preferences.allergies,
        )
        if blocked and not blocked.intersection({item.lower() for item in recipe.ingredients}):
            reasons.append('Avoids excluded ingredients.')
        return reasons

    def _recipe_matches_cuisines(
        self,
        recipe: RecipeRecord,
        target_cuisines: set[str],
    ) -> bool:
        recipe_cuisines = {item.lower() for item in recipe.cuisines}
        if recipe.cuisine:
            recipe_cuisines.add(recipe.cuisine.lower())
        return bool(recipe_cuisines.intersection(target_cuisines))

    def _diet_compatible(self, recipe_diet: str | None, requested_diet: str) -> bool:
        if recipe_diet is None:
            return True
        recipe_key = recipe_diet.lower()
        requested_key = requested_diet.lower()
        if requested_key == 'vegetarian':
            return recipe_key in {'vegetarian', 'vegan', 'eggetarian'}
        if requested_key == 'vegan':
            return recipe_key == 'vegan'
        if requested_key == 'eggetarian':
            return recipe_key in {'eggetarian', 'vegetarian'}
        if requested_key == 'pescatarian':
            return recipe_key in {'pescatarian', 'vegetarian', 'vegan'}
        if requested_key == 'non_vegetarian':
            return recipe_key in {'non_vegetarian', 'pescatarian', 'eggetarian'}
        return recipe_key == requested_key

    def expand_blocked_terms(
        self,
        excluded_ingredients: list[str],
        allergies: list[str],
    ) -> set[str]:
        blocked = {item.lower() for item in excluded_ingredients}
        for allergy in allergies:
            allergy_key = allergy.lower()
            blocked.add(allergy_key)
            blocked.update(ALLERGY_ALIASES.get(allergy_key, {allergy_key}))
        return {term for term in blocked if term}
