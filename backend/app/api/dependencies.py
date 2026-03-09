from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings
from app.repositories.indexed_recipe_repository import IndexedRecipeRepository
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.qdrant_recipe_repository import QdrantRecipeRepository
from app.services.email_service import EmailService
from app.services.user_store import UserRecord, UserStore
from app.services.user_store_postgres import PostgresUserStore
from app.services.agent_workflow import AgentWorkflowService
from app.services.langgraph_service import HuggingFaceLLM, LangGraphChatService
from app.services.neural_reranker import NeuralReranker
from app.services.qdrant_retrieval import QdrantRetrievalService
from app.services.graph_traversal import GraphTraversalService
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
    settings = get_settings()
    if settings.use_qdrant and settings.qdrant_collection_map:
        return QdrantRecipeRepository(
            qdrant_url=settings.qdrant_url,
            collections=settings.qdrant_collection_map.keys(),
            recipes_csv_path=settings.foodcom_recipes_csv,
            details_db_path=settings.foodcom_details_db,
        )

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
def get_chat_service() -> LangGraphChatService:
    settings = get_settings()
    return LangGraphChatService(
        agent_workflow_service=get_agent_workflow_service(),
        recipe_repository=get_recipe_repository(),
        retrieval_service=get_retrieval_service(),
        session_store=get_session_store(),
        llm_client=HuggingFaceLLM(
            api_key=settings.hf_api_key,
            model=settings.hf_model,
            timeout_seconds=settings.hf_timeout_seconds,
        ),
        llm_max_tokens=settings.hf_max_tokens,
        llm_temperature=settings.hf_temperature,
    )


@lru_cache
def get_retrieval_service() -> RetrievalService:
    settings = get_settings()
    return RetrievalService(
        search_index=get_indexed_recipe_repository(),
        neural_reranker=get_neural_reranker(),
        qdrant_retrieval=get_qdrant_retrieval(),
        graph_traversal=get_graph_traversal(),
        graph_weight=settings.graph_weight,
        vector_weight=settings.vector_weight,
        rerank_top_k=settings.neural_rerank_top_k,
        indexed_candidate_limit=settings.indexed_candidate_limit,
    )


@lru_cache
def get_agent_workflow_service() -> AgentWorkflowService:
    return AgentWorkflowService()


@lru_cache
def get_user_store() -> UserStore:
    settings = get_settings()
    if settings.use_postgres_auth:
        return PostgresUserStore(settings.postgres_auth_dsn)
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


@lru_cache
def get_qdrant_retrieval() -> QdrantRetrievalService | None:
    settings = get_settings()
    if not settings.use_qdrant:
        return None
    collections = settings.qdrant_collection_map
    if not collections:
        return None
    return QdrantRetrievalService(
        qdrant_url=settings.qdrant_url,
        collections=collections,
        default_collection=settings.qdrant_default_collection,
        top_k=settings.qdrant_top_k,
        low_score_threshold=settings.qdrant_low_score_threshold,
        short_query_tokens=settings.qdrant_short_query_tokens,
    )


@lru_cache
def get_graph_traversal() -> GraphTraversalService | None:
    settings = get_settings()
    if not settings.use_graph:
        return None
    return GraphTraversalService(settings.postgres_dsn, max_candidates=settings.graph_max_candidates)
