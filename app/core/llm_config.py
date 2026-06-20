from __future__ import annotations

"""Moonshot/Kimi LLM 配置解析：模型别名、端点探测候选。"""

MOONSHOT_AI_BASE = "https://api.moonshot.ai/v1"
MOONSHOT_CN_BASE = "https://api.moonshot.cn/v1"

MODEL_ALIASES: dict[str, str] = {
    "kimi-k2-6": "kimi-k2.6",
    "kimi-k2-5": "kimi-k2.5",
    "kimi-k2-7": "kimi-k2.7-code",
    "kimi-k2-7-code-highspeed": "kimi-k2.7-code-highspeed",
    "kimi-latest": "moonshot-v1-8k",
    "kimi-k2-turbo-preview": "kimi-k2.5",
    "kimi-k2-thinking": "kimi-k2.5",
}

K2_MODEL_IDS = frozenset(
    {
        "kimi-k2.6",
        "kimi-k2.5",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
    }
)

CN_LEGACY_MODELS = frozenset(
    {
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
        "moonshot-v1-8k-vision-preview",
        "moonshot-v1-32k-vision-preview",
        "moonshot-v1-128k-vision-preview",
    }
)

SUPPORTED_MODEL_HINT = (
    "国内 Key：moonshot-v1-8k @ api.moonshot.cn；"
    "国际 Key：kimi-k2.6 @ api.moonshot.ai"
)


def _canonical_key(model: str) -> str:
    return model.strip().lower().replace("_", "-")


def normalize_model_name(model: str) -> str:
    key = _canonical_key(model)
    return MODEL_ALIASES.get(key, model.strip())


def is_k2_model(model: str) -> bool:
    m = normalize_model_name(model)
    return m in K2_MODEL_IDS or m.startswith("kimi-k2.")


def resolve_moonshot_endpoint(base_url: str, model: str) -> tuple[str, list[str]]:
    """保留用户配置的端点，不再强制把 K2 切到 .ai（国内 Key 会 401）。"""
    notes: list[str] = []
    base = (base_url or MOONSHOT_CN_BASE).rstrip("/")
    model = normalize_model_name(model)

    if not base_url:
        notes.append(f"未配置 LLM_BASE_URL，默认 {MOONSHOT_CN_BASE}")

    if is_k2_model(model) and "moonshot.cn" in base:
        notes.append(
            f"提示：{model} 需国际版 Key（api.moonshot.ai）；"
            f"国内 Key 请改用 moonshot-v1-8k + api.moonshot.cn"
        )

    return base, notes


def probe_candidates(base_url: str, model: str) -> list[tuple[str, str]]:
    """按优先级尝试 base+model 组合，自动匹配国内/国际 Key。"""
    model = normalize_model_name(model)
    base = (base_url or MOONSHOT_CN_BASE).rstrip("/")
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []

    def add(b: str, m: str) -> None:
        b = b.rstrip("/")
        m = normalize_model_name(m)
        key = (b, m)
        if key not in seen:
            seen.add(key)
            out.append(key)

    add(base, model)
    add(MOONSHOT_CN_BASE, model)
    add(MOONSHOT_CN_BASE, "moonshot-v1-8k")
    add(MOONSHOT_CN_BASE, "moonshot-v1-32k")
    add(MOONSHOT_AI_BASE, model)
    if is_k2_model(model):
        add(MOONSHOT_AI_BASE, "kimi-k2.6")
        add(MOONSHOT_AI_BASE, "kimi-k2.5")
    else:
        add(MOONSHOT_AI_BASE, "kimi-k2.6")

    return out


def model_error_hint(model: str, base_url: str) -> str:
    model = normalize_model_name(model)
    if "moonshot.ai" in base_url:
        return "。国内 Key 请改用 api.moonshot.cn + moonshot-v1-8k"
    if is_k2_model(model) and "moonshot.cn" in base_url:
        return f"。{model} 需 api.moonshot.ai 国际版 Key"
    return f"。可用：{SUPPORTED_MODEL_HINT}"
