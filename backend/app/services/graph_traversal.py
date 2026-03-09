from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import psycopg

from app.schemas import AgentInput


@dataclass
class GraphCandidate:
    recipe_id: int
    title: str
    total_time_minutes: int | None
    score: float
    reasons: list[str]


class GraphTraversalService:
    def __init__(self, postgres_dsn: str, *, max_candidates: int = 200) -> None:
        self.postgres_dsn = postgres_dsn
        self.max_candidates = max_candidates

    def traverse(self, agent_input: AgentInput) -> list[GraphCandidate]:
        terms, types = build_graph_terms(agent_input)
        if not terms:
            return []
        rows = self._fetch_matches(terms, types, agent_input.detected_preferences.max_cooking_time_minutes)
        return rank_graph_candidates(rows, agent_input)

    def _fetch_matches(
        self,
        terms: list[str],
        types: list[str],
        max_time: int | None,
    ) -> list[dict]:
        where_time = ""
        params: list[object] = [terms, types]
        if max_time is not None:
            where_time = "AND (m.total_time_minutes IS NULL OR m.total_time_minutes <= %s)"
            params.append(max_time)
        query = f"""
            SELECT e.src_id AS recipe_id,
                   n.node_type,
                   n.node_value,
                   m.title,
                   m.total_time_minutes
            FROM graph_nodes n
            JOIN graph_edges e ON e.dst_id = n.node_id
            JOIN recipe_meta m ON m.recipe_id = e.src_id
            WHERE n.value_lc = ANY(%s)
              AND n.node_type = ANY(%s)
              {where_time}
        """
        with psycopg.connect(self.postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        results = []
        for row in rows:
            results.append(
                {
                    "recipe_id": int(row[0]),
                    "node_type": str(row[1]),
                    "node_value": str(row[2]),
                    "title": str(row[3]),
                    "total_time_minutes": row[4],
                }
            )
        return results


def build_graph_terms(agent_input: AgentInput) -> tuple[list[str], list[str]]:
    prefs = agent_input.detected_preferences
    terms: list[str] = []
    types: list[str] = []

    for cuisine in prefs.cuisines:
        terms.append(cuisine.lower())
        types.append("cuisine")
    for ingredient in prefs.available_ingredients:
        terms.append(ingredient.lower())
        types.append("ingredient")
    for token in agent_input.query_tokens:
        terms.append(token.lower())
        types.append("tag")

    if not terms:
        return [], []
    return terms, types


def rank_graph_candidates(rows: list[dict], agent_input: AgentInput) -> list[GraphCandidate]:
    prefs = agent_input.detected_preferences
    buckets: dict[int, GraphCandidate] = {}
    for row in rows:
        recipe_id = row["recipe_id"]
        candidate = buckets.get(recipe_id)
        if candidate is None:
            candidate = GraphCandidate(
                recipe_id=recipe_id,
                title=row["title"],
                total_time_minutes=row["total_time_minutes"],
                score=0.0,
                reasons=[],
            )
            buckets[recipe_id] = candidate

        node_type = row["node_type"]
        node_value = row["node_value"]
        if node_type == "cuisine":
            candidate.score += 2.5
            candidate.reasons.append(f"Matches cuisine: {node_value}.")
        elif node_type == "ingredient":
            candidate.score += 1.5
            candidate.reasons.append(f"Uses ingredient: {node_value}.")
        else:
            candidate.score += 0.5
            candidate.reasons.append(f"Related tag: {node_value}.")

    ordered = sorted(buckets.values(), key=lambda item: item.score, reverse=True)
    return ordered[: min(200, len(ordered))]
