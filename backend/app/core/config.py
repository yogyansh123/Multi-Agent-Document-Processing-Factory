"""
core/config.py
==============
Application configuration management.

All configuration values come from environment variables (or a .env file
loaded via python-dotenv). No secrets are hardcoded here.

Usage:
    from app.core.config import settings
    print(settings.DATABASE_URL)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field, PostgresDsn, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Validation is performed automatically by Pydantic on instantiation.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars gracefully
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "Multi-Agent Document Processing Factory"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -------------------------------------------------------------------------
    # API Server
    # -------------------------------------------------------------------------
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    PORT: int | None = None
    BACKEND_RELOAD: bool = False

    # CORS
    CORS_ORIGINS: list[str] | str = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )
    FRONTEND_URL: str | None = None
    CORS_ORIGIN_REGEX: str | None = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        origins: list[str] = []
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    origins = json.loads(v)
                except Exception:
                    pass
            else:
                origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            origins = [str(i).strip() for i in v if str(i).strip()]

        default_dev = ["http://localhost:5173", "http://localhost:3000"]
        for d in default_dev:
            if d not in origins:
                origins.append(d)
        return origins

    # -------------------------------------------------------------------------
    # PostgreSQL
    # -------------------------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "document_factory"
    POSTGRES_USER: str = "docfactory"
    POSTGRES_PASSWORD: str = Field(
        default="changeme_postgres_password",
        description="PostgreSQL password",
    )

    DATABASE_URL: str | None = None
    DATABASE_URL_SYNC: str | None = None

    @model_validator(mode="after")
    def assemble_deployment_settings(self) -> "Settings":
        # 1. Port mapping: PORT environment variable takes precedence if provided (e.g., Render)
        if self.PORT is not None:
            self.BACKEND_PORT = self.PORT

        # 2. CORS frontend URL binding: append FRONTEND_URL if provided
        if self.FRONTEND_URL:
            clean_fe = self.FRONTEND_URL.strip().rstrip("/")
            if clean_fe and clean_fe not in self.CORS_ORIGINS:
                if isinstance(self.CORS_ORIGINS, list):
                    self.CORS_ORIGINS.append(clean_fe)

        # 3. Database URL assembly and driver normalization
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        else:
            raw_url = str(self.DATABASE_URL).strip()
            if raw_url.startswith("postgres://"):
                self.DATABASE_URL = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
            elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
                self.DATABASE_URL = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]

        if not self.DATABASE_URL_SYNC:
            if self.DATABASE_URL and not self.DATABASE_URL.startswith("sqlite"):
                raw_url = self.DATABASE_URL
                if "+asyncpg" in raw_url:
                    self.DATABASE_URL_SYNC = raw_url.replace("+asyncpg", "+psycopg2")
                else:
                    self.DATABASE_URL_SYNC = raw_url
            else:
                self.DATABASE_URL_SYNC = (
                    f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
        return self

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_STATUS_TTL_SECONDS: int = 3600
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    # -------------------------------------------------------------------------
    # Temporal
    # -------------------------------------------------------------------------
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_HOST: str = "localhost"
    TEMPORAL_PORT: int = 7233
    TEMPORAL_NAMESPACE: str = "document-processing"
    TEMPORAL_TASK_QUEUE: str = "document-processing-queue"

    @model_validator(mode="before")
    @classmethod
    def resolve_service_urls(cls, data: Any) -> Any:
        """Resolve Redis and Temporal addresses if host/port or password are provided."""
        if isinstance(data, dict):
            if "REDIS_URL" not in data and data.get("REDIS_PASSWORD"):
                host = data.get("REDIS_HOST", "localhost")
                port = data.get("REDIS_PORT", 6379)
                pwd = data.get("REDIS_PASSWORD")
                db = data.get("REDIS_DB", 0)
                data["REDIS_URL"] = f"redis://:{pwd}@{host}:{port}/{db}"
            if "TEMPORAL_ADDRESS" not in data and ("TEMPORAL_HOST" in data or "TEMPORAL_PORT" in data):
                host = data.get("TEMPORAL_HOST", "localhost")
                port = data.get("TEMPORAL_PORT", 7233)
                data["TEMPORAL_ADDRESS"] = f"{host}:{port}"
        return data

    # -------------------------------------------------------------------------
    # LLM Provider
    # -------------------------------------------------------------------------
    LLM_PROVIDER: Literal["openai", "anthropic", "google", "azure_openai", "ollama"] = (
        "openai"
    )

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 4096

    # Anthropic
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Google
    GOOGLE_API_KEY: str | None = None
    GOOGLE_MODEL: str = "gemini-1.5-pro"

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # -------------------------------------------------------------------------
    # OCR Provider
    # -------------------------------------------------------------------------
    OCR_PROVIDER: Literal[
        "tesseract", "aws_textract", "google_vision", "azure_form_recognizer", "unstructured"
    ] = "tesseract"

    # Tesseract
    TESSERACT_CMD: str = ""
    """Path to the tesseract executable. Leave empty to use system PATH."""
    OCR_LANGUAGE: str = "eng"
    """Tesseract language code(s). Multiple languages: 'eng+fra'. Default: 'eng'."""
    OCR_DPI: int = 300
    """DPI for rendering PDF pages to images before OCR."""
    OCR_TEXT_PREVIEW_CHARS: int = 1000
    """Maximum characters returned in the OCR result preview endpoint."""

    # AWS
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"

    # Azure Form Recognizer
    AZURE_FORM_RECOGNIZER_ENDPOINT: str | None = None
    AZURE_FORM_RECOGNIZER_KEY: str | None = None

    # -------------------------------------------------------------------------
    # Vector Database & RAG (Step 9)
    # -------------------------------------------------------------------------
    VECTOR_DB_PROVIDER: Literal[
        "chromadb", "pinecone", "weaviate", "qdrant", "pgvector"
    ] = "pgvector"

    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 120
    RAG_MAX_CONTEXT_CHARS: int = 12000
    RAG_TOP_K_DEFAULT: int = 5
    RAG_TOP_K_MAX: int = 20
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    PINECONE_API_KEY: str | None = None
    PINECONE_INDEX_NAME: str = "document-factory"

    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: str | None = None

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None


    # -------------------------------------------------------------------------
    # File Storage
    # -------------------------------------------------------------------------
    STORAGE_BACKEND: Literal["local", "s3", "gcs", "azure_blob"] = "local"
    STORAGE_PATH: str = "./storage"
    """Root directory for local file storage (relative to the working directory)."""
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str = "us-east-1"

    # Upload constraints
    MAX_UPLOAD_SIZE_MB: int = 25
    """Maximum size of an uploaded file in megabytes."""
    ALLOWED_UPLOAD_TYPES: list[str] | str = [
        "pdf", "png", "jpg", "jpeg", "docx"
    ]
    """Lowercase file extensions accepted by the upload endpoint."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        """MAX_UPLOAD_SIZE_MB expressed in bytes for fast comparison."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="dev_secret_key_change_in_production_32chars",
        description="Application secret key is required",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # -------------------------------------------------------------------------
    # Document Processing
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: list[str] | str = Field(
        default=["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"]
    )

    @field_validator("ALLOWED_UPLOAD_TYPES", "ALLOWED_FILE_TYPES", mode="before")
    @classmethod
    def assemble_string_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return v
    PROCESSING_TIMEOUT_SECONDS: int = 300
    MAX_RETRY_ATTEMPTS: int = 3
    CONFIDENCE_THRESHOLD: float = 0.85
    AUTO_APPROVAL_THRESHOLD: float = 0.85
    REVIEW_THRESHOLD: float = 0.60
    ARITHMETIC_TOLERANCE: float = 0.05

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    ENABLE_TRACING: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    SENTRY_DSN: str | None = None

    @model_validator(mode="after")
    def validate_environment_consistency(self) -> "Settings":
        """Perform cross-field validation to catch misconfigurations early."""
        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG must be False in production environment")

        if 0.0 > self.CONFIDENCE_THRESHOLD or self.CONFIDENCE_THRESHOLD > 1.0:
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")

        if 0.0 > self.AUTO_APPROVAL_THRESHOLD or self.AUTO_APPROVAL_THRESHOLD > 1.0:
            raise ValueError("AUTO_APPROVAL_THRESHOLD must be between 0.0 and 1.0")

        if 0.0 > self.REVIEW_THRESHOLD or self.REVIEW_THRESHOLD > 1.0:
            raise ValueError("REVIEW_THRESHOLD must be between 0.0 and 1.0")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Using lru_cache ensures the Settings object is created once per process
    and environment variables are read only on first access.
    """
    return Settings()  # type: ignore[call-arg]


# Convenience alias for import
settings = get_settings()
