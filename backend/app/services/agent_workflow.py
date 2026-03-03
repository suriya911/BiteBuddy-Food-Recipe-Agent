from __future__ import annotations

from app.schemas import (
    AgentConflict,
    AgentInput,
    IngredientSubstitution,
    RecipeMatch,
)


SUBSTITUTION_MAP = {
    "chicken": ["paneer", "tofu", "cauliflower"],
    "paneer": ["tofu", "halloumi", "mushroom"],
    "beef": ["mushroom", "jackfruit", "lamb"],
    "pasta": ["rice noodles", "zucchini noodles", "quinoa"],
    "egg": ["tofu scramble", "chickpea flour batter", "mashed banana"],
    "milk": ["oat milk", "almond milk", "coconut milk"],
    "cheese": ["nutritional yeast", "vegan cheese", "paneer"],
    "tofu": ["paneer", "tempeh", "mushroom"],
    "fish": ["tofu", "cauliflower", "paneer"],
}

NON_VEG_INGREDIENTS = {
    "chicken",
    "beef",
    "pork",
    "mutton",
    "lamb",
    "fish",
    "shrimp",
    "prawn",
    "bacon",
    "turkey",
}


class AgentWorkflowService:
    def build_conflicts(self, agent_input: AgentInput) -> list[AgentConflict]:
        conflicts: list[AgentConflict] = []
        preferences = agent_input.detected_preferences
        if preferences.diet in {"vegetarian", "vegan"}:
            requested_non_veg = sorted(
                NON_VEG_INGREDIENTS.intersection(
                    {item.lower() for item in preferences.available_ingredients},
                ),
            )
            if requested_non_veg:
                conflicts.append(
                    AgentConflict(
                        type="dietary_conflict",
                        message=(
                            "The request mixes a vegetarian preference with non-vegetarian "
                            f"ingredients: {', '.join(requested_non_veg)}."
                        ),
                    )
                )
        if preferences.allergies and preferences.available_ingredients:
            overlaps = sorted(
                {item.lower() for item in preferences.available_ingredients}.intersection(
                    {item.lower() for item in preferences.allergies},
                ),
            )
            if overlaps:
                conflicts.append(
                    AgentConflict(
                        type="allergy_conflict",
                        message=(
                            "The request includes ingredients that overlap with allergy "
                            f"constraints: {', '.join(overlaps)}."
                        ),
                    )
                )
        return conflicts

    def build_substitutions(self, agent_input: AgentInput) -> list[IngredientSubstitution]:
        substitutions: list[IngredientSubstitution] = []
        blocked = [
            *agent_input.detected_preferences.excluded_ingredients,
            *agent_input.profile.excluded_ingredients,
            *agent_input.profile.disliked_ingredients,
        ]
        seen: set[str] = set()
        for ingredient in blocked:
            key = ingredient.lower()
            if key in seen:
                continue
            seen.add(key)
            substitutes = SUBSTITUTION_MAP.get(key)
            if substitutes:
                substitutions.append(
                    IngredientSubstitution(
                        ingredient=ingredient,
                        substitutes=substitutes,
                    )
                )
        return substitutions

    def build_recipe_reply(
        self,
        matches: list[RecipeMatch],
        *,
        fallback_reason: str | None,
        conflicts: list[AgentConflict],
        substitutions: list[IngredientSubstitution],
    ) -> str:
        if conflicts:
            return conflicts[0].message
        if matches:
            lead = ", ".join(match.title for match in matches[:3])
            detail = matches[0].match_reasons[0] if matches[0].match_reasons else "Best overall match."
            if fallback_reason:
                return f"I found {len(matches)} options: {lead}. {detail} {fallback_reason}"
            if substitutions:
                first = substitutions[0]
                return (
                    f"I found {len(matches)} options: {lead}. {detail} "
                    f"If you want to avoid {first.ingredient}, try {', '.join(first.substitutes)}."
                )
            return f"I found {len(matches)} options: {lead}. {detail}"
        if substitutions:
            first = substitutions[0]
            return (
                "I could not find a direct match with the current constraints. "
                f"For {first.ingredient}, try {', '.join(first.substitutes)}."
            )
        return (
            "I could not find a recipe with the current constraints. "
            "Try changing the cuisine, diet, ingredients, or cooking time."
        )
