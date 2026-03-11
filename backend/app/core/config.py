from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default='BiteBuddy API', alias='APP_NAME')
    app_env: str = Field(default='development', alias='APP_ENV')
    api_v1_prefix: str = Field(default='/api', alias='API_V1_PREFIX')
    host: str = Field(default='0.0.0.0', alias='HOST')
    port: int = Field(default=8000, alias='PORT')
    cors_origins: list[str] = Field(
        default_factory=lambda: ['http://localhost:5173', 'http://localhost:8080'],
        alias='CORS_ORIGINS',
    )
    cors_origin_regex: str | None = Field(default=None, alias='CORS_ORIGIN_REGEX')

    openai_api_key: str | None = Field(default=None, alias='OPENAI_API_KEY')
    supabase_url: str | None = Field(default=None, alias='SUPABASE_URL')
    supabase_service_role_key: str | None = Field(
        default=None,
        alias='SUPABASE_SERVICE_ROLE_KEY',
    )
    pinecone_api_key: str | None = Field(default=None, alias='PINECONE_API_KEY')
    pinecone_index: str | None = Field(default=None, alias='PINECONE_INDEX')
    youtube_api_key: str | None = Field(default=None, alias='YOUTUBE_API_KEY')

    use_large_corpus_index: bool = Field(default=False, alias='USE_LARGE_CORPUS_INDEX')
    recipe_search_index_path: str = Field(
        default='backend/data/processed/recipe_search.sqlite',
        alias='RECIPE_SEARCH_INDEX_PATH',
    )
    indexed_candidate_limit: int = Field(default=120, alias='INDEXED_CANDIDATE_LIMIT')
    enable_neural_reranker: bool = Field(default=False, alias='ENABLE_NEURAL_RERANKER')
    neural_reranker_model: str = Field(
        default='cross-encoder/ms-marco-MiniLM-L-6-v2',
        alias='NEURAL_RERANKER_MODEL',
    )
    neural_rerank_top_k: int = Field(default=25, alias='NEURAL_RERANK_TOP_K')
    auth_db_path: str = Field(default='backend/data/processed/auth.sqlite', alias='AUTH_DB_PATH')
    smtp_host: str | None = Field(default=None, alias='SMTP_HOST')
    smtp_port: int = Field(default=587, alias='SMTP_PORT')
    smtp_username: str | None = Field(default=None, alias='SMTP_USERNAME')
    smtp_password: str | None = Field(default=None, alias='SMTP_PASSWORD')
    smtp_from_email: str | None = Field(default=None, alias='SMTP_FROM_EMAIL')
    smtp_use_tls: bool = Field(default=True, alias='SMTP_USE_TLS')
    otp_expiry_minutes: int = Field(default=10, alias='OTP_EXPIRY_MINUTES')
    enable_langgraph: bool = Field(default=False, alias='ENABLE_LANGGRAPH')
    hf_api_key: str | None = Field(default=None, alias='HF_API_KEY')
    hf_model: str | None = Field(default=None, alias='HF_MODEL')
    hf_max_tokens: int = Field(default=220, alias='HF_MAX_TOKENS')
    hf_temperature: float = Field(default=0.4, alias='HF_TEMPERATURE')
    hf_timeout_seconds: int = Field(default=30, alias='HF_TIMEOUT_SECONDS')
    use_qdrant: bool = Field(default=False, alias='USE_QDRANT')
    qdrant_url: str = Field(default='http://localhost:6333', alias='QDRANT_URL')
    qdrant_collections: str = Field(
        default='recipes_foodcom_e5_base,recipes_foodcom_bge,recipes_foodcom_bge_small',
        alias='QDRANT_COLLECTIONS',
    )
    qdrant_models: str = Field(
        default='intfloat/e5-base-v2,BAAI/bge-base-en-v1.5,BAAI/bge-small-en-v1.5',
        alias='QDRANT_MODELS',
    )
    qdrant_default_collection: str = Field(
        default='recipes_foodcom_e5_base',
        alias='QDRANT_DEFAULT_COLLECTION',
    )
    qdrant_top_k: int = Field(default=10, alias='QDRANT_TOP_K')
    qdrant_low_score_threshold: float = Field(default=0.25, alias='QDRANT_LOW_SCORE_THRESHOLD')
    qdrant_short_query_tokens: int = Field(default=4, alias='QDRANT_SHORT_QUERY_TOKENS')
    foodcom_recipes_csv: str = Field(
        default='backend/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv',
        alias='FOODCOM_RECIPES_CSV',
    )
    foodcom_details_db: str = Field(
        default='backend/data/processed/recipe_details.sqlite',
        alias='FOODCOM_DETAILS_DB',
    )
    postgres_dsn: str = Field(
        default='postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy',
        alias='POSTGRES_DSN',
    )
    use_graph: bool = Field(default=False, alias='USE_GRAPH')
    graph_max_candidates: int = Field(default=200, alias='GRAPH_MAX_CANDIDATES')
    graph_weight: float = Field(default=0.3, alias='GRAPH_WEIGHT')
    vector_weight: float = Field(default=0.7, alias='VECTOR_WEIGHT')
    use_postgres_auth: bool = Field(default=False, alias='USE_POSTGRES_AUTH')
    postgres_auth_dsn: str = Field(
        default='postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy',
        alias='POSTGRES_AUTH_DSN',
    )

    model_config = SettingsConfigDict(
        env_file=('backend/.env', '.env'),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        if isinstance(value, list):
            return value
        if not value:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.startswith("[") and cleaned.endswith("]"):
                cleaned = cleaned[1:-1]
            parts = [part.strip().strip("'").strip('"') for part in cleaned.split(",")]
            return [part for part in parts if part]
        return value

    @property
    def qdrant_collection_map(self) -> dict[str, str]:
        collections = [item.strip() for item in self.qdrant_collections.split(",") if item.strip()]
        models = [item.strip() for item in self.qdrant_models.split(",") if item.strip()]
        if not collections or not models or len(collections) != len(models):
            return {}
        return dict(zip(collections, models, strict=True))


@lru_cache
def get_settings() -> Settings:
    return Settings()
