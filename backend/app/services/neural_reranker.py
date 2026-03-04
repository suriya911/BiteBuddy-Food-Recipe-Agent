from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.schemas import RecipeMatch, RecipeRecord


class NeuralReranker:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any | None = None
        self._load_failed = False

    def is_available(self) -> bool:
        return self._get_model() is not None

    def rerank(
        self,
        *,
        query: str,
        ranked_items: Sequence[tuple[RecipeRecord, RecipeMatch]],
        top_k: int,
    ) -> list[tuple[RecipeRecord, RecipeMatch]]:
        if top_k <= 0 or not ranked_items:
            return list(ranked_items)

        model = self._get_model()
        if model is None:
            return list(ranked_items)

        rerank_count = min(top_k, len(ranked_items))
        top_items = list(ranked_items[:rerank_count])
        trailing_items = list(ranked_items[rerank_count:])
        pairs = [(query, self._recipe_text(recipe)) for recipe, _ in top_items]
        neural_scores = model.predict(pairs, batch_size=16, show_progress_bar=False)

        base_norm = self._normalize([match.score for _, match in top_items])
        neural_norm = self._normalize([float(score) for score in neural_scores])

        combined: list[tuple[float, RecipeRecord, RecipeMatch]] = []
        for idx, (recipe, match) in enumerate(top_items):
            blended_rank_score = (0.7 * base_norm[idx]) + (0.3 * neural_norm[idx])
            final_score = round(float(match.score) + (neural_norm[idx] * 2.0), 2)
            updated_match = match.model_copy(update={'score': final_score})
            combined.append((blended_rank_score, recipe, updated_match))

        combined.sort(key=lambda item: (item[0], item[2].score), reverse=True)
        reranked = [(recipe, match) for _, recipe, match in combined]
        reranked.extend(trailing_items)
        return reranked

    def _get_model(self) -> Any | None:
        if self._load_failed:
            return None
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except Exception:
            self._load_failed = True
            return None
        try:
            self._model = CrossEncoder(self.model_name)
        except Exception:
            self._load_failed = True
            self._model = None
        return self._model

    def _recipe_text(self, recipe: RecipeRecord) -> str:
        return ' '.join(
            part
            for part in [
                recipe.title,
                recipe.description or '',
                recipe.cuisine or '',
                ' '.join(recipe.cuisines),
                recipe.diet or '',
                ' '.join(recipe.ingredients[:20]),
                ' '.join(recipe.tags[:10]),
                ' '.join(recipe.instructions[:6]),
            ]
            if part
        )

    def _normalize(self, values: Sequence[float]) -> list[float]:
        if not values:
            return []
        low = min(values)
        high = max(values)
        if abs(high - low) < 1e-12:
            return [0.0 for _ in values]
        return [(value - low) / (high - low) for value in values]
