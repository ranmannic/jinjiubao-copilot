from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.llm_config import normalize_model_name, resolve_moonshot_endpoint


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_env: str = "development"
    log_level: str = "INFO"

    llm_enabled: bool = True
    llm_api_key: str = ""
    llm_base_url: str = "https://api.moonshot.cn/v1"
    llm_model: str = "moonshot-v1-8k"
    llm_config_notes: List[str] = []

    jinjiubao_api_base_url: str = "https://api.jinjiubao.example.com"
    jinjiubao_api_key: str = ""
    jinjiubao_api_timeout: float = 15.0

    session_backend: str = "sqlite"
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "./data/sessions.db"

    handoff_intent_threshold: int = 70
    sales_callback_sla_minutes: int = 30

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def strip_llm_api_key(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("llm_model", mode="before")
    @classmethod
    def normalize_llm_model(cls, v: object) -> str:
        if v is None:
            return "kimi-k2.6"
        return normalize_model_name(str(v))

    @model_validator(mode="after")
    def resolve_llm_endpoint(self) -> "Settings":
        base, notes = resolve_moonshot_endpoint(self.llm_base_url, self.llm_model)
        self.llm_base_url = base
        self.llm_config_notes = notes
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
