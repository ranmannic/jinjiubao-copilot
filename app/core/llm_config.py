from __future__ import annotations

"""LLM 配置：Moonshot/Kimi 与 DeepSeek 端点解析。"""

MOONSHOT_AI_BASE = "https://api.moonshot.ai/v1"
MOONSHOT_CN_BASE = "https://api.moonshot.cn/v1"
DEEPSEEK_BASE = "https://api.deepseek.com/v1"

MODEL_ALIASES: dict[str, str] = {
    "kimi-k2-6": "kimi-k2.6",
    "kimi-k2-5": "kimi-k2.5",
    "kimi-k2-7": "kimi-k2.7-code",
    "kimi-k2-7-code-highspeed": "kimi-k2.7-code-highspeed",
    "kimi-latest": "moonshot-v1-8k",
    "kimi-k2-turbo-preview": "kimi-k2.5",
    "kimi-k2-thinking": "kimi-k2.5",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
}

K2_MODEL_IDS = frozenset(
    {
        "kimi-k2.6",
        "kimi-k2.5",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
    }
)

DEEPSEEK_MODEL_IDS = frozenset(
    {
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-chat",
        "deepseek-reasoner",
    }
)

SUPPORTED_MODEL_HINT = (
    "DeepSeek：deepseek-v4-flash @ https://api.deepseek.com/v1；"
    "Moonshot 国内：moonshot-v1-8k @ api.moonshot.cn；"
    "Moonshot 国际：kimi-k2.6 @ api.moonshot.ai"
)


def _canonical_key(model: str) -> str:
    return model.strip().lower().replace("_", "-")


def normalize_model_name(model: str) -> str:
    key = _canonical_key(model)
    return MODEL_ALIASES.get(key, model.strip())


def is_k2_model(model: str) -> bool:
    m = normalize_model_name(model)
    return m in K2_MODEL_IDS or m.startswith("kimi-k2.")


def is_deepseek_model(model: str) -> bool:
    m = normalize_model_name(model)
    return m in DEEPSEEK_MODEL_IDS or m.startswith("deepseek-")


def is_deepseek_provider(base_url: str, model: str) -> bool:
    base = (base_url or "").lower()
    return "deepseek.com" in base or is_deepseek_model(model)


def resolve_deepseek_endpoint(base_url: str, model: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    base = (base_url or DEEPSEEK_BASE).rstrip("/")
    model = normalize_model_name(model)

    if "/anthropic" in base:
        base = DEEPSEEK_BASE
        notes.append(
            "DeepSeek 的 /anthropic 端点供 Claude SDK 使用；"
            "本项目使用 OpenAI SDK，已自动改为 https://api.deepseek.com/v1"
        )
    elif base.endswith("api.deepseek.com"):
        base = DEEPSEEK_BASE
        if not notes:
            notes.append("DeepSeek OpenAI 兼容端点：https://api.deepseek.com/v1")

    return base, notes


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


def resolve_llm_endpoint(base_url: str, model: str) -> tuple[str, list[str]]:
    if is_deepseek_provider(base_url, model):
        return resolve_deepseek_endpoint(base_url, model)
    return resolve_moonshot_endpoint(base_url, model)


def probe_candidates(base_url: str, model: str) -> list[tuple[str, str]]:
    """按优先级尝试 base+model 组合。"""
    model = normalize_model_name(model)
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []

    def add(b: str, m: str) -> None:
        b = b.rstrip("/")
        m = normalize_model_name(m)
        key = (b, m)
        if key not in seen:
            seen.add(key)
            out.append(key)

    if is_deepseek_provider(base_url, model):
        base, _ = resolve_deepseek_endpoint(base_url, model)
        for m in (model, "deepseek-v4-flash", "deepseek-chat", "deepseek-v4-pro"):
            add(base, m)
        return out

    base = (base_url or MOONSHOT_CN_BASE).rstrip("/")
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
    if is_deepseek_provider(base_url, model):
        return "。DeepSeek 请使用 LLM_BASE_URL=https://api.deepseek.com/v1、LLM_MODEL=deepseek-v4-flash"
    if "moonshot.ai" in base_url:
        return "。国内 Key 请改用 api.moonshot.cn + moonshot-v1-8k"
    if is_k2_model(model) and "moonshot.cn" in base_url:
        return f"。{model} 需 api.moonshot.ai 国际版 Key"
    return f"。可用：{SUPPORTED_MODEL_HINT}"
