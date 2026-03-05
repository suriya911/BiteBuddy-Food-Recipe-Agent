from functools import lru_cache

from pydantic import Field
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

    model_config = SettingsConfigDict(
        env_file=('backend/.env', '.env'),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
