import logging
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment (see ``backend/.env.example``)."""

    openrouter_api_key: str
    bypass_cache: bool = False
    database_url: str = "sqlite:///./freightmind.db"
    cache_dir: str = "./cache"
    analytics_model: str = "meta-llama/llama-3.3-70b-instruct"
    # Fallback when primary text model fails after retries (Story 5.5, TECH_DECISIONS TD-2).
    analytics_model_fallback: str = "deepseek/deepseek-r1-0528:free"
    vision_model: str = "qwen/qwen2.5-vl-72b-instruct"
    # Fallback when primary vision model fails after retries (Story 5.5, TECH_DECISIONS TD-3).
    vision_model_fallback: str = "nvidia/nemotron-nano-2-vl:free"
    vision_timeout: float = 60.0
    # Passed to OpenRouter as max_tokens on every chat completion. High defaults (e.g. model
    # max) can trigger 402 on low-credit accounts; keep this within typical output needs.
    llm_max_tokens: int = 8192
    # Comma-separated origins, or "*" for all (local dev). Production: list explicit UI origins.
    cors_origins: str = "*"
    # Maximum upload size for POST /api/documents/extract (bytes).
    max_upload_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def warn_duplicate_fallback_models(self) -> Self:
        """Avoid redundant second model phase when primary and fallback ids match (deferred 5.5)."""
        if self.analytics_model.strip() == self.analytics_model_fallback.strip():
            logger.warning(
                "ANALYTICS_MODEL and ANALYTICS_MODEL_FALLBACK are identical; "
                "fallback will call the same model twice on failure."
            )
        if self.vision_model.strip() == self.vision_model_fallback.strip():
            logger.warning(
                "VISION_MODEL and VISION_MODEL_FALLBACK are identical; "
                "fallback will call the same model twice on failure."
            )
        return self


def cors_allow_origins_list(settings: Settings) -> list[str]:
    """Parse CORS_ORIGINS: ``*`` or comma-separated list."""
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
