from __future__ import annotations

import re

from app.schemas import AgentInput, PreferenceSnapshot, UserProfile


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "with",
    "want",
}

CUISINE_KEYWORDS = {
    "indian": "Indian",
    "south indian": "South Indian",
    "north indian": "North Indian",
    "punjabi": "Punjabi",
    "gujarati": "Gujarati",
    "bengali": "Bengali",
    "mughlai": "Mughlai",
    "hyderabadi": "Hyderabadi",
    "italian": "Italian",
    "mexican": "Mexican",
    "thai": "Thai",
    "chinese": "Chinese",
    "japanese": "Japanese",
    "korean": "Korean",
    "mediterranean": "Mediterranean",
    "american": "American",
    "french": "French",
    "greek": "Greek",
    "turkish": "Turkish",
    "middle eastern": "Middle Eastern",
    "lebanese": "Lebanese",
    "spanish": "Spanish",
    "caribbean": "Caribbean",
}

DIET_KEYWORDS = (
    ("non vegetarian", "non_vegetarian"),
    ("non-vegetarian", "non_vegetarian"),
    ("non veg", "non_vegetarian"),
    ("non-veg", "non_vegetarian"),
    ("pescatarian", "pescatarian"),
    ("eggetarian", "eggetarian"),
    ("eggitarian", "eggetarian"),
    ("vegan", "vegan"),
    ("vegetarian", "vegetarian"),
    ("veg", "vegetarian"),
)

ALLERGY_KEYWORDS = (
    ("tree nut", "tree_nut"),
    ("peanuts", "peanut"),
    ("peanut", "peanut"),
    ("dairy", "dairy"),
    ("milk", "dairy"),
    ("gluten", "gluten"),
    ("soy", "soy"),
    ("eggs", "egg"),
    ("egg", "egg"),
    ("shellfish", "shellfish"),
)

INGREDIENT_HINTS = {
    "chicken",
    "paneer",
    "rice",
    "egg",
    "eggs",
    "potato",
    "tomato",
    "onion",
    "garlic",
    "mushroom",
    "tofu",
    "beef",
    "fish",
    "pasta",
    "cheese",
    "spinach",
    "lentils",
    "dal",
}

QUESTION_PATTERNS = (
    "what is",
    "how to",
    "difference between",
    "tell me about",
)


def build_agent_input(message: str, profile: UserProfile) -> AgentInput:
    normalized_query = normalize_query(message)
    query_tokens = tokenize_query(normalized_query)
    detected_preferences = merge_preferences(
        profile=profile,
        inferred=extract_preferences(normalized_query),
    )
    retrieval_query = build_retrieval_query(normalized_query, detected_preferences)
    should_answer_general_food_question = any(
        pattern in normalized_query for pattern in QUESTION_PATTERNS
    )

    return AgentInput(
        raw_query=message,
        normalized_query=normalized_query,
        query_tokens=query_tokens,
        retrieval_query=retrieval_query,
        detected_preferences=detected_preferences,
        profile=profile,
        should_retrieve_recipes=not should_answer_general_food_question,
        should_answer_general_food_question=should_answer_general_food_question,
    )


def normalize_query(message: str) -> str:
    lowered = message.lower().strip()
    return re.sub(r"\s+", " ", lowered)


def tokenize_query(normalized_query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]+", normalized_query)
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def extract_preferences(normalized_query: str) -> PreferenceSnapshot:
    cuisines = find_cuisines(normalized_query)
    diet = find_first_match(normalized_query, DIET_KEYWORDS)
    allergies = find_all_matches(normalized_query, ALLERGY_KEYWORDS)
    excluded_ingredients = find_excluded_ingredients(normalized_query)
    max_time = find_max_time(normalized_query)
    ingredients = find_ingredient_mentions(normalized_query)
    ingredients = [item for item in ingredients if item not in excluded_ingredients]
    return PreferenceSnapshot(
        cuisines=cuisines,
        diet=diet,
        allergies=allergies,
        excluded_ingredients=excluded_ingredients,
        available_ingredients=ingredients,
        max_cooking_time_minutes=max_time,
    )


def merge_preferences(
    *,
    profile: UserProfile,
    inferred: PreferenceSnapshot,
) -> PreferenceSnapshot:
    return PreferenceSnapshot(
        cuisines=dedupe(profile.preferred_cuisines + inferred.cuisines),
        diet=inferred.diet or profile.diet,
        allergies=dedupe(profile.allergies + inferred.allergies),
        excluded_ingredients=dedupe(
            profile.excluded_ingredients
            + profile.disliked_ingredients
            + inferred.excluded_ingredients,
        ),
        available_ingredients=dedupe(
            [
                item
                for item in profile.available_ingredients + inferred.available_ingredients
                if item
                not in {
                    *profile.excluded_ingredients,
                    *profile.disliked_ingredients,
                    *inferred.excluded_ingredients,
                }
            ],
        ),
        max_cooking_time_minutes=(
            inferred.max_cooking_time_minutes or profile.max_cooking_time_minutes
        ),
    )


def build_retrieval_query(
    normalized_query: str,
    preferences: PreferenceSnapshot,
) -> str:
    parts = [normalized_query]
    if preferences.cuisines:
        parts.append("cuisines " + " ".join(preferences.cuisines))
    if preferences.diet:
        parts.append("diet " + preferences.diet.replace("_", " "))
    if preferences.available_ingredients:
        parts.append("ingredients " + " ".join(preferences.available_ingredients))
    if preferences.excluded_ingredients:
        parts.append("exclude " + " ".join(preferences.excluded_ingredients))
    if preferences.max_cooking_time_minutes:
        parts.append(f"under {preferences.max_cooking_time_minutes} minutes")
    return " | ".join(parts)


def find_cuisines(text: str) -> list[str]:
    return [value for key, value in CUISINE_KEYWORDS.items() if key in text]


def find_first_match(text: str, mapping: tuple[tuple[str, str], ...]) -> str | None:
    for key, value in mapping:
        if contains_phrase(text, key):
            return value
    return None


def find_all_matches(text: str, mapping: tuple[tuple[str, str], ...]) -> list[str]:
    matches = [value for key, value in mapping if contains_phrase(text, key)]
    return dedupe(matches)


def find_max_time(text: str) -> int | None:
    patterns = (
        r"(\d+)\s*minutes",
        r"(\d+)\s*mins",
        r"under\s*(\d+)",
        r"within\s*(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def find_ingredient_mentions(text: str) -> list[str]:
    return [item for item in sorted(INGREDIENT_HINTS) if item in text]


def find_excluded_ingredients(text: str) -> list[str]:
    matches: list[str] = []
    for ingredient in sorted(INGREDIENT_HINTS):
        patterns = (
            rf"\bdon'?t have\s+{re.escape(ingredient)}s?\b",
            rf"\bwithout\s+{re.escape(ingredient)}s?\b",
            rf"\bno\s+{re.escape(ingredient)}s?\b",
            rf"\bavoid\s+{re.escape(ingredient)}s?\b",
            rf"\bskip\s+{re.escape(ingredient)}s?\b",
            rf"\binstead of\s+{re.escape(ingredient)}s?\b",
        )
        if any(re.search(pattern, text) for pattern in patterns):
            matches.append(ingredient)
    return dedupe(matches)


def contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return re.search(pattern, text) is not None


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped
