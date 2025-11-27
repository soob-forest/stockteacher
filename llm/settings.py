"""Settings for the analysis (OpenAI LLM) pipeline."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisSettings(BaseSettings):
    """Environment-driven configuration for analysis stage."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY", description="OpenAI API key")
    analysis_model: str = Field("gpt-4o-mini", alias="ANALYSIS_MODEL", description="OpenAI model name")
    analysis_max_tokens: PositiveInt = Field(512, alias="ANALYSIS_MAX_TOKENS", description="Max completion tokens")
    analysis_temperature: PositiveFloat = Field(0.2, alias="ANALYSIS_TEMPERATURE", description="Sampling temperature")
    analysis_cost_limit_usd: PositiveFloat = Field(0.02, alias="ANALYSIS_COST_LIMIT_USD", description="Per-request cost cap (USD)")
    analysis_request_timeout_seconds: PositiveInt = Field(
        15,
        alias="ANALYSIS_REQUEST_TIMEOUT_SECONDS",
        description="HTTP request timeout in seconds",
    )
    analysis_retry_max_attempts: PositiveInt = Field(2, alias="ANALYSIS_RETRY_MAX_ATTEMPTS", description="Max retry attempts")
    default_locale: str = Field("ko_KR", alias="DEFAULT_LOCALE", description="Default locale for prompts")

    @field_validator("openai_api_key")
    @classmethod
    def _non_empty_api_key(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("OPENAI_API_KEY는 공백일 수 없습니다.")
        return s


@lru_cache()
def get_analysis_settings() -> AnalysisSettings:
    try:
        return AnalysisSettings()
    except ValidationError as exc:
        raise RuntimeError(f"분석 설정 검증 실패: {exc}") from exc


def reset_analysis_settings_cache() -> None:
    get_analysis_settings.cache_clear()  # type: ignore[attr-defined]
