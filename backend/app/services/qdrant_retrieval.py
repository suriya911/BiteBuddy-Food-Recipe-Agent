from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter
import ast
import pandas as pd
from sentence_transformers import SentenceTransformer

from app.schemas import AgentInput, RecipeMatch, RetrievalTrace


@dataclass
class QdrantRetrievalResult:
    matches: list[RecipeMatch]
    trace: RetrievalTrace


class QdrantRetrievalService:
    def __init__(
        self,
        *,
        qdrant_url: str,
        collections: dict[str, str],
        default_collection: str,
        top_k: int,
        low_score_threshold: float,
        short_query_tokens: int,
    ) -> None:
        self.client = QdrantClient(url=qdrant_url)
        self.collections = collections
        self.default_collection = default_collection
        self.top_k = top_k
        self.low_score_threshold = low_score_threshold
        self.short_query_tokens = short_query_tokens
        self._models: dict[str, SentenceTransformer] = {}

    def search(self, agent_input: AgentInput) -> QdrantRetrievalResult:
        collection = self._select_collection(agent_input)
        search_order = self._build_search_order(collection)
        for candidate in search_order:
            matches, trace = self._search_collection(candidate, agent_input, apply_filter=True)
            if not matches:
                matches, trace = self._search_collection(candidate, agent_input, apply_filter=False)
            if matches:
                return QdrantRetrievalResult(matches=matches, trace=trace)
        return QdrantRetrievalResult(matches=[], trace=RetrievalTrace(
            total_recipes=0,
            metadata_matches=0,
            vector_matches=0,
            fallback_applied=True,
            fallback_reason="No matches across configured collections.",
        ))

    def _select_collection(self, agent_input: AgentInput) -> str:
        tokens = agent_input.query_tokens
        preferences = agent_input.detected_preferences
        complexity = sum(
            bool(value)
            for value in [
                preferences.cuisines,
                preferences.diet,
                preferences.allergies,
                preferences.available_ingredients,
                preferences.excluded_ingredients,
                preferences.max_cooking_time_minutes,
            ]
        )
        if len(tokens) <= self.short_query_tokens and complexity <= 1:
            return self._find_collection("e5") or self.default_collection
        if len(tokens) >= 12 or complexity >= 3:
            return self._find_collection("bge-base") or self.default_collection
        return self.default_collection

    def _search_collection(
        self,
        collection: str,
        agent_input: AgentInput,
        *,
        apply_filter: bool,
    ) -> tuple[list[RecipeMatch], RetrievalTrace]:
        model_name = self.collections[collection]
        model = self._get_model(model_name)
        query = agent_input.retrieval_query or agent_input.normalized_query
        vector = model.encode(
            [query],
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0].tolist()
        query_filter = build_filter(agent_input) if apply_filter else None
        results = self.client.search(
            collection_name=collection,
            query_vector=vector,
            limit=self.top_k,
            query_filter=query_filter,
        )
        matches = []
        top_score = results[0].score if results else 0.0
        for hit in results:
            payload = hit.payload or {}
            matches.append(
                RecipeMatch(
                    recipe_id=str(payload.get("recipe_id") or ""),
                    title=str(payload.get("title") or ""),
                    cuisine=payload.get("cuisine"),
                    cuisines=[],
                    diet=payload.get("diet"),
                    total_time_minutes=payload.get("total_time_minutes"),
                    ingredients=normalize_list(payload.get("ingredients")),
                    score=round(float(hit.score or 0.0), 4),
                    match_reasons=["Semantic match via vector search."],
                )
            )
        trace = RetrievalTrace(
            total_recipes=0,
            metadata_matches=len(matches),
            vector_matches=len(matches),
            fallback_applied=bool(results and top_score < self.low_score_threshold),
            fallback_reason=(
                "Low semantic score on primary collection, retrying default collection."
                if results and top_score < self.low_score_threshold
                else ("No matches with filters; retrying without filters." if apply_filter else None)
            ),
        )
        if results and top_score < self.low_score_threshold:
            return matches, trace
        return matches, trace

    def _find_collection(self, hint: str) -> str | None:
        for name in self.collections:
            if hint in name:
                return name
        return None

    def _build_search_order(self, selected: str) -> list[str]:
        ordered = [selected]
        if selected != self.default_collection:
            ordered.append(self.default_collection)
        for name in self.collections:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _get_model(self, model_name: str) -> SentenceTransformer:
        model = self._models.get(model_name)
        if model is None:
            model = SentenceTransformer(model_name, device="cuda" if has_cuda() else "cpu")
            model.max_seq_length = 256
            self._models[model_name] = model
        return model


def build_filter(agent_input: AgentInput) -> Filter | None:
    prefs = agent_input.detected_preferences
    must_filters = []
    must_not = []
    if prefs.max_cooking_time_minutes is not None:
        must_filters.append(
            {"key": "total_time_minutes", "range": {"lte": prefs.max_cooking_time_minutes}}
        )
    if prefs.available_ingredients:
        must_filters.append({"key": "ingredients", "match": {"any": prefs.available_ingredients}})
    if prefs.excluded_ingredients:
        must_not.append({"key": "ingredients", "match": {"any": prefs.excluded_ingredients}})
    if not must_filters and not must_not:
        return None
    return Filter(must=must_filters, must_not=must_not)


def has_cuda() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


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
