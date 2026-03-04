from __future__ import annotations

from app.schemas import AgentReply, ChatMessage, ChatRequest, UserProfile
from app.services.agent_workflow import AgentWorkflowService
from app.services.query_understanding import build_agent_input
from app.services.retrieval import RetrievalService
from app.services.session_store import InMemorySessionStore


class ChatService:
    def __init__(
        self,
        *,
        recipe_repository,
        agent_workflow_service: AgentWorkflowService,
        retrieval_service: RetrievalService,
        session_store: InMemorySessionStore,
    ) -> None:
        self.recipe_repository = recipe_repository
        self.agent_workflow_service = agent_workflow_service
        self.retrieval_service = retrieval_service
        self.session_store = session_store

    def handle_chat(self, payload: ChatRequest) -> AgentReply:
        session = self.session_store.get_or_create(payload.session_id)
        merged_profile = self._merge_profiles(session.profile, payload.profile)
        merged_history = [*session.history, *payload.history]
        merged_history.append(ChatMessage(role='user', content=payload.message))

        agent_input = build_agent_input(payload.message, merged_profile)
        persisted_profile = self._apply_detected_preferences(
            merged_profile,
            agent_input.detected_preferences.cuisines,
            agent_input.detected_preferences.diet,
            agent_input.detected_preferences.allergies,
            agent_input.detected_preferences.excluded_ingredients,
            agent_input.detected_preferences.available_ingredients,
            agent_input.detected_preferences.max_cooking_time_minutes,
        )
        conflicts = self.agent_workflow_service.build_conflicts(agent_input)
        substitutions = self.agent_workflow_service.build_substitutions(agent_input)
        self.session_store.update(
            session_id=session.session_id,
            profile=persisted_profile,
            history=merged_history,
        )

        if agent_input.should_answer_general_food_question:
            return AgentReply(
                reply=(
                    'I parsed this as a general food question rather than a recipe search. '
                    'The next step is to answer it with the LLM and optional retrieved context.'
                ),
                agent_input=agent_input,
                session_id=session.session_id,
                recipe_matches=[],
                retrieval_trace=None,
                conflicts=conflicts,
                substitution_suggestions=substitutions,
                next_actions=[
                    'extract_preferences',
                    'answer_general_food_question',
                ],
            )

        recipes = None if self.retrieval_service.uses_index() else self.recipe_repository.list_recipes()
        retrieval_result = self.retrieval_service.find_matches(
            recipes=recipes,
            agent_input=agent_input,
        )
        reply = self.agent_workflow_service.build_recipe_reply(
            retrieval_result.matches,
            fallback_reason=retrieval_result.trace.fallback_reason,
            conflicts=conflicts,
            substitutions=substitutions,
        )
        return AgentReply(
            reply=reply,
            agent_input=agent_input,
            session_id=session.session_id,
            recipe_matches=retrieval_result.matches,
            retrieval_trace=retrieval_result.trace,
            conflicts=conflicts,
            substitution_suggestions=substitutions,
            next_actions=[
                'extract_preferences',
                'build_retrieval_query',
                'filter_recipe_metadata',
                'query_rag_store',
                'rank_recipe_candidates',
            ],
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
