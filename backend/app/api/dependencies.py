from functools import lru_cache
from pathlib import Path

from app.repositories.recipe_repository import RecipeRepository
from app.services.agent_workflow import AgentWorkflowService
from app.services.chat_service import ChatService
from app.services.retrieval import RetrievalService
from app.services.session_store import InMemorySessionStore


BASE_DIR = Path(__file__).resolve().parents[3]


@lru_cache
def get_session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@lru_cache
def get_recipe_repository() -> RecipeRepository:
    data_path = BASE_DIR / "backend" / "data" / "processed" / "recipes.jsonl"
    if not data_path.exists():
        data_path = BASE_DIR / "backend" / "data" / "processed" / "sample_recipes.jsonl"
    return RecipeRepository(data_path)


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(
        agent_workflow_service=get_agent_workflow_service(),
        recipe_repository=get_recipe_repository(),
        retrieval_service=get_retrieval_service(),
        session_store=get_session_store(),
    )


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


@lru_cache
def get_agent_workflow_service() -> AgentWorkflowService:
    return AgentWorkflowService()
