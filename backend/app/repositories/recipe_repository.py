from __future__ import annotations

import json
from pathlib import Path

from app.schemas import RecipeRecord


class RecipeRepository:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self._recipes: dict[str, RecipeRecord] | None = None

    def list_recipes(self) -> list[RecipeRecord]:
        return list(self._load().values())

    def get_recipe(self, recipe_id: str) -> RecipeRecord | None:
        return self._load().get(recipe_id)

    def _load(self) -> dict[str, RecipeRecord]:
        if self._recipes is not None:
            return self._recipes

        recipes: dict[str, RecipeRecord] = {}
        if self.data_path.exists():
            for line in self.data_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                recipe = RecipeRecord.model_validate_json(line)
                recipes[recipe.recipe_id] = recipe

        self._recipes = recipes
        return recipes
