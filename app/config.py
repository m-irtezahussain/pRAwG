from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "pRAwG"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection: str = "personal_documents"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    chat_provider: Literal["gemini", "ollama"] = "gemini"
    google_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    ollama_embedding_model: str = "nomic-embed-text-v2-moe:latest"

    object_storage_endpoint: AnyHttpUrl = "http://localhost:9000"
    object_storage_access_key: SecretStr = SecretStr("prawg")
    object_storage_secret_key: SecretStr = SecretStr("prawg-local-dev")
    object_storage_bucket: str = Field(
        default="prawg-documents",
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$",
    )
    object_storage_region: str = "us-east-1"

    max_upload_mb: int = Field(default=25, ge=1, le=250)
    chunk_size: int = Field(default=1200, ge=200, le=10_000)
    chunk_overlap: int = Field(default=200, ge=0, le=2_000)

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
