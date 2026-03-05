from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings
from app.repositories.indexed_recipe_repository import IndexedRecipeRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.email_service import EmailService
from app.services.user_store import UserRecord, UserStore
from app.services.agent_workflow import AgentWorkflowService
from app.services.chat_service import ChatService
from app.services.neural_reranker import NeuralReranker
from app.services.retrieval import RetrievalService
from app.services.session_store import InMemorySessionStore


BASE_DIR = Path(__file__).resolve().parents[3]


@lru_cache
def get_session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@lru_cache
def get_indexed_recipe_repository() -> IndexedRecipeRepository | None:
    settings = get_settings()
    if not settings.use_large_corpus_index:
        return None
    index_path = Path(settings.recipe_search_index_path)
    if not index_path.is_absolute():
        index_path = BASE_DIR / index_path
    repository = IndexedRecipeRepository(index_path)
    if not repository.is_available():
        return None
    return repository


@lru_cache
def get_recipe_repository():
    indexed_repository = get_indexed_recipe_repository()
    if indexed_repository is not None:
        return indexed_repository

    data_path = BASE_DIR / 'backend' / 'data' / 'processed' / 'recipes.jsonl'
    if not data_path.exists():
        data_path = BASE_DIR / 'backend' / 'data' / 'processed' / 'sample_recipes.jsonl'
    return RecipeRepository(data_path)


@lru_cache
def get_neural_reranker() -> NeuralReranker | None:
    settings = get_settings()
    if not settings.enable_neural_reranker:
        return None
    reranker = NeuralReranker(settings.neural_reranker_model)
    if not reranker.is_available():
        return None
    return reranker


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
    settings = get_settings()
    return RetrievalService(
        search_index=get_indexed_recipe_repository(),
        neural_reranker=get_neural_reranker(),
        rerank_top_k=settings.neural_rerank_top_k,
        indexed_candidate_limit=settings.indexed_candidate_limit,
    )


@lru_cache
def get_agent_workflow_service() -> AgentWorkflowService:
    return AgentWorkflowService()


@lru_cache
def get_user_store() -> UserStore:
    settings = get_settings()
    db_path = Path(settings.auth_db_path)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    return UserStore(db_path)


def get_current_user(
    authorization: str | None = Header(default=None),
    user_store: UserStore = Depends(get_user_store),
) -> UserRecord:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer token.')
    token = authorization.split(' ', 1)[1].strip()
    user = user_store.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail='Invalid or expired token.')
    return user


@lru_cache
def get_email_service() -> EmailService:
    settings = get_settings()
    return EmailService(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_email=settings.smtp_from_email,
        use_tls=settings.smtp_use_tls,
    )
