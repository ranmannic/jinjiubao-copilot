from app.core.llm_config import (
    normalize_model_name,
    probe_candidates,
    resolve_moonshot_endpoint,
)


def test_normalize_k2_aliases():
    assert normalize_model_name("kimi-k2-6") == "kimi-k2.6"
    assert normalize_model_name("kimi-latest") == "moonshot-v1-8k"


def test_k2_on_cn_does_not_force_ai_switch():
    base, notes = resolve_moonshot_endpoint("https://api.moonshot.cn/v1", "kimi-k2.6")
    assert base == "https://api.moonshot.cn/v1"
    assert notes


def test_probe_candidates_prefers_cn_for_v1():
    cands = probe_candidates("https://api.moonshot.ai/v1", "kimi-k2.6")
    assert cands[0] == ("https://api.moonshot.ai/v1", "kimi-k2.6")
    assert ("https://api.moonshot.cn/v1", "moonshot-v1-8k") in cands
