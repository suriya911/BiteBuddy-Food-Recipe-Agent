from __future__ import annotations

from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.schemas import AgentReply, ChatMessage, ChatRequest, UserProfile
from app.services.agent_workflow import AgentWorkflowService
from app.services.query_understanding import build_agent_input
from app.services.retrieval import RetrievalService, RetrievalResult
from app.services.session_store import InMemorySessionStore


class AgentState(TypedDict, total=False):
    message: str
    profile: UserProfile
    history: list[ChatMessage]
    agent_input: object
    conflicts: list
    substitutions: list
    retrieval_result: RetrievalResult | None
    reply: str
    next_actions: list[str]


class HuggingFaceLLM:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.api_key and self.model)

    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> str | None:
        if not self.is_available():
            return None
        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            },
            "options": {"wait_for_model": True},
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        if isinstance(data, list) and data:
            generated = data[0].get("generated_text")
            if isinstance(generated, str):
                return generated.strip()
        return None


class LangGraphChatService:
    def __init__(
        self,
        *,
        recipe_repository,
        agent_workflow_service: AgentWorkflowService,
        retrieval_service: RetrievalService,
        session_store: InMemorySessionStore,
        llm_client: HuggingFaceLLM,
        llm_max_tokens: int = 220,
        llm_temperature: float = 0.4,
    ) -> None:
        self.recipe_repository = recipe_repository
        self.agent_workflow_service = agent_workflow_service
        self.retrieval_service = retrieval_service
        self.session_store = session_store
        self.llm_client = llm_client
        self.llm_max_tokens = llm_max_tokens
        self.llm_temperature = llm_temperature
        self.graph = self._build_graph()

    def handle_chat(self, payload: ChatRequest) -> AgentReply:
        session = self.session_store.get_or_create(payload.session_id)
        merged_profile = self._merge_profiles(session.profile, payload.profile)
        merged_history = [*session.history, *payload.history]
        merged_history.append(ChatMessage(role="user", content=payload.message))

        state = AgentState(
            message=payload.message,
            profile=merged_profile,
            history=merged_history,
        )
        result = self.graph.invoke(state)

        updated_profile = result.get("profile", merged_profile)
        self.session_store.update(
            session_id=session.session_id,
            profile=updated_profile,
            history=merged_history,
        )

        agent_input = result.get("agent_input")
        if agent_input is None:
            agent_input = build_agent_input(payload.message, updated_profile)
        retrieval_result = result.get("retrieval_result")
        return AgentReply(
            reply=result.get("reply", "I could not generate a response right now."),
            agent_input=agent_input,
            session_id=session.session_id,
            recipe_matches=retrieval_result.matches if retrieval_result else [],
            retrieval_trace=retrieval_result.trace if retrieval_result else None,
            conflicts=result.get("conflicts", []),
            substitution_suggestions=result.get("substitutions", []),
            next_actions=result.get("next_actions", []),
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("parse", self._parse)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("respond", self._respond)
        graph.set_entry_point("parse")
        graph.add_conditional_edges(
            "parse",
            self._route_after_parse,
            {
                "retrieve": "retrieve",
                "respond": "respond",
            },
        )
        graph.add_edge("retrieve", "respond")
        graph.add_edge("respond", END)
        return graph.compile()

    def _route_after_parse(self, state: AgentState) -> str:
        agent_input = state.get("agent_input")
        if agent_input and getattr(agent_input, "should_retrieve_recipes", True):
            return "retrieve"
        return "respond"

    def _parse(self, state: AgentState) -> AgentState:
        profile = state["profile"]
        agent_input = build_agent_input(state["message"], profile)
        persisted_profile = self._apply_detected_preferences(
            profile,
            agent_input.detected_preferences.cuisines,
            agent_input.detected_preferences.diet,
            agent_input.detected_preferences.allergies,
            agent_input.detected_preferences.excluded_ingredients,
            agent_input.detected_preferences.available_ingredients,
            agent_input.detected_preferences.max_cooking_time_minutes,
        )
        conflicts = self.agent_workflow_service.build_conflicts(agent_input)
        substitutions = self.agent_workflow_service.build_substitutions(agent_input)
        return {
            "agent_input": agent_input,
            "profile": persisted_profile,
            "conflicts": conflicts,
            "substitutions": substitutions,
        }

    def _retrieve(self, state: AgentState) -> AgentState:
        recipes = None if self.retrieval_service.uses_index() else self.recipe_repository.list_recipes()
        retrieval_result = self.retrieval_service.find_matches(
            recipes=recipes,
            agent_input=state["agent_input"],
        )
        return {"retrieval_result": retrieval_result}

    def _respond(self, state: AgentState) -> AgentState:
        agent_input = state.get("agent_input")
        conflicts = state.get("conflicts", [])
        substitutions = state.get("substitutions", [])
        retrieval_result = state.get("retrieval_result")

        if agent_input and agent_input.should_answer_general_food_question:
            prompt = self._build_general_prompt(agent_input.raw_query)
            llm_reply = self.llm_client.generate(
                prompt,
                max_tokens=self.llm_max_tokens,
                temperature=self.llm_temperature,
            )
            reply = llm_reply or (
                "I parsed this as a general food question. "
                "Enable the hosted LLM to answer with more detail."
            )
            return {
                "reply": reply,
                "next_actions": [
                    "extract_preferences",
                    "answer_general_food_question",
                ],
            }

        matches = retrieval_result.matches if retrieval_result else []
        base_reply = self.agent_workflow_service.build_recipe_reply(
            matches,
            fallback_reason=(retrieval_result.trace.fallback_reason if retrieval_result else None),
            conflicts=conflicts,
            substitutions=substitutions,
        )
        prompt = self._build_recipe_prompt(agent_input, matches, base_reply)
        llm_reply = self.llm_client.generate(
            prompt,
            max_tokens=self.llm_max_tokens,
            temperature=self.llm_temperature,
        )
        reply = llm_reply or base_reply
        return {
            "reply": reply,
            "next_actions": [
                "extract_preferences",
                "build_retrieval_query",
                "filter_recipe_metadata",
                "query_rag_store",
                "rank_recipe_candidates",
            ],
        }

    def _build_general_prompt(self, question: str) -> str:
        return (
            "You are BiteBuddy, a helpful food and cooking assistant. "
            "Answer the user's question clearly in 3-5 sentences.\n\n"
            f"Question: {question}\nAnswer:"
        )

    def _build_recipe_prompt(self, agent_input, matches, base_reply: str) -> str:
        top_titles = ", ".join([match.title for match in matches[:3]]) or "No matches"
        return (
            "You are BiteBuddy, a food recommendation assistant. "
            "Reply in 2-4 sentences. Mention up to three recipe titles. "
            "Keep it concise and friendly.\n\n"
            f"User request: {agent_input.raw_query if agent_input else ''}\n"
            f"Detected preferences: {agent_input.detected_preferences if agent_input else ''}\n"
            f"Top matches: {top_titles}\n"
            f"Base reply: {base_reply}\n"
            "Final reply:"
        )

    def _merge_profiles(self, stored: UserProfile, incoming: UserProfile) -> UserProfile:
        return UserProfile(
            preferred_cuisines=self._dedupe(
                stored.preferred_cuisines + incoming.preferred_cuisines,
            ),
            diet=incoming.diet or stored.diet,
            allergies=self._dedupe(stored.allergies + incoming.allergies),
            disliked_ingredients=self._dedupe(
                stored.disliked_ingredients + incoming.disliked_ingredients,
            ),
            excluded_ingredients=self._dedupe(
                stored.excluded_ingredients + incoming.excluded_ingredients,
            ),
            available_ingredients=self._dedupe(
                [
                    item
                    for item in stored.available_ingredients + incoming.available_ingredients
                    if item
                    not in {
                        *stored.excluded_ingredients,
                        *incoming.excluded_ingredients,
                        *stored.disliked_ingredients,
                        *incoming.disliked_ingredients,
                    }
                ],
            ),
            max_cooking_time_minutes=(
                incoming.max_cooking_time_minutes or stored.max_cooking_time_minutes
            ),
        )

    def _apply_detected_preferences(
        self,
        profile: UserProfile,
        cuisines: list[str],
        diet: str | None,
        allergies: list[str],
        excluded_ingredients: list[str],
        available_ingredients: list[str],
        max_cooking_time_minutes: int | None,
    ) -> UserProfile:
        return UserProfile(
            preferred_cuisines=self._dedupe(profile.preferred_cuisines + cuisines),
            diet=diet or profile.diet,
            allergies=self._dedupe(profile.allergies + allergies),
            disliked_ingredients=profile.disliked_ingredients,
            excluded_ingredients=self._dedupe(
                profile.excluded_ingredients
                + profile.disliked_ingredients
                + excluded_ingredients,
            ),
            available_ingredients=self._dedupe(
                [
                    item
                    for item in profile.available_ingredients + available_ingredients
                    if item
                    not in {
                        *profile.excluded_ingredients,
                        *profile.disliked_ingredients,
                        *excluded_ingredients,
                    }
                ],
            ),
            max_cooking_time_minutes=(
                max_cooking_time_minutes or profile.max_cooking_time_minutes
            ),
        )

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped
