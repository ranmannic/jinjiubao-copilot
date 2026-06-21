from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.llm_config import DEEPSEEK_BASE, MOONSHOT_CN_BASE, resolve_llm_endpoint


@dataclass
class ProviderConfig:
    id: str
    label: str
    base_url: str
    model: str
    api_key: str
    description: str


PROVIDER_DEFS: dict[str, dict[str, str]] = {
    "kimi": {
        "label": "Kimi (Moonshot)",
        "base_url_key": "llm_kimi_base_url",
        "model_key": "llm_kimi_model",
        "default_base_url": MOONSHOT_CN_BASE,
        "default_model": "moonshot-v1-8k",
        "description": "国内 Key · platform.moonshot.cn",
    },
    "deepseek": {
        "label": "DeepSeek V4 Flash",
        "base_url_key": "llm_deepseek_base_url",
        "model_key": "llm_deepseek_model",
        "default_base_url": DEEPSEEK_BASE,
        "default_model": "deepseek-v4-flash",
        "description": "高性价比 · platform.deepseek.com",
    },
}


class LLMProviderStore:
    def __init__(self, path: str = "./data/llm_provider.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> str | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data.get("active")
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, provider_id: str) -> None:
        self.path.write_text(
            json.dumps({"active": provider_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _key_for_provider(settings: Settings, provider_id: str) -> str:
    if provider_id == "kimi":
        return (settings.llm_kimi_api_key or "").strip()
    if provider_id == "deepseek":
        return (settings.llm_deepseek_api_key or "").strip()
    return ""


def build_provider_config(settings: Settings, provider_id: str) -> ProviderConfig:
    meta = PROVIDER_DEFS.get(provider_id, PROVIDER_DEFS["deepseek"])
    api_key = _key_for_provider(settings, provider_id)
    if not api_key and settings.llm_provider == provider_id:
        api_key = (settings.llm_api_key or "").strip()
    base_url = getattr(settings, meta["base_url_key"], meta["default_base_url"])
    model = getattr(settings, meta["model_key"], meta["default_model"])
    base, _ = resolve_llm_endpoint(base_url, model)
    return ProviderConfig(
        id=provider_id,
        label=meta["label"],
        base_url=base,
        model=model,
        api_key=api_key,
        description=meta["description"],
    )


def list_providers(settings: Settings) -> list[ProviderConfig]:
    return [build_provider_config(settings, pid) for pid in PROVIDER_DEFS]


def apply_provider_to_settings(settings: Settings, provider_id: str) -> ProviderConfig:
    if provider_id not in PROVIDER_DEFS:
        provider_id = settings.llm_provider or "deepseek"
    cfg = build_provider_config(settings, provider_id)
    if not cfg.api_key:
        raise ValueError(f"{cfg.label} 未配置 API Key（请在 .env 设置 LLM_{provider_id.upper()}_API_KEY）")
    settings.llm_provider = provider_id
    settings.llm_api_key = cfg.api_key
    settings.llm_base_url = cfg.base_url
    settings.llm_model = cfg.model
    return cfg


def provider_status_dict(cfg: ProviderConfig, active: bool, connected: bool, error: str | None) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "label": cfg.label,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "description": cfg.description,
        "configured": bool(cfg.api_key),
        "active": active,
        "connected": connected,
        "error": error,
    }
