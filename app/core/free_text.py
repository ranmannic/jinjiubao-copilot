from __future__ import annotations

import re

from app.models.domain import CustomerNeeds, CustomerProfile


META_PATTERNS = [
    "哪家ai",
    "哪家 ai",
    "什么ai",
    "什么 ai",
    "什么模型",
    "你是谁",
    "你是哪个",
    "谁开发的",
]


def is_meta_question(text: str) -> bool:
    lowered = text.lower().replace("？", "?").strip()
    return any(p in lowered for p in META_PATTERNS)


def meta_answer() -> str:
    return (
        "我是进酒宝 AI 选品顾问「小进」，由 Kimi（Moonshot 月之暗面）大模型驱动，"
        "专门帮酒商客户选品、谈方案。您有具体选酒需求可以直接说，我来帮您匹配。"
    )


def enrich_needs_from_free_text(text: str, needs: CustomerNeeds) -> None:
    """从自然语言补充规则引擎未识别的需求字段。"""
    lowered = text.lower()

    if not needs.notes and len(text.strip()) > 12:
        needs.notes = text.strip()[:500]

    if any(k in lowered for k in ["法国", "aop", "勃艮第", "波尔多", "进口"]):
        if "葡萄酒" not in needs.categories and "白葡萄酒" not in needs.categories:
            if any(k in lowered for k in ["白", "干白", "霞多丽", "勃艮第"]):
                needs.categories.append("白葡萄酒")
            elif any(k in lowered for k in ["红", "干红", "赤霞珠"]):
                needs.categories.append("红葡萄酒")
            else:
                needs.categories.append("葡萄酒")

    if any(k in lowered for k in ["口感好", "好喝", "顺", "易入口"]):
        if "口感好" not in needs.taste_preferences:
            needs.taste_preferences.append("口感好")
    if any(k in lowered for k in ["差异化", "不透明", "网上没有", "少人做", "价格高一点"]):
        if "当地差异化" not in needs.differentiation:
            needs.differentiation.append("当地差异化")
    if any(k in lowered for k in ["利润", "毛利", "赚钱"]):
        needs.margin_priority = "高"

    # 20以内 / 20块以内 / 不超过20
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*以内", text)
    if m:
        needs.retail_price_max = float(m.group(1))
        if not needs.retail_price_min:
            needs.retail_price_min = max(1.0, needs.retail_price_max * 0.5)

    m = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*(?:元|块)?", text)
    if m:
        needs.retail_price_min = float(m.group(1))
        needs.retail_price_max = float(m.group(2))

    m = re.search(r"零售\s*(\d+)\s*[-~到]\s*(\d+)", text)
    if m:
        needs.retail_price_min = float(m.group(1))
        needs.retail_price_max = float(m.group(2))


def needs_complete(needs: CustomerNeeds) -> bool:
    """判断是否有足够信息推品——支持自然语言详述，不要求填完所有字段。"""
    has_category = bool(needs.categories)
    has_price = needs.retail_price_min is not None or needs.retail_price_max is not None
    has_margin = needs.margin_priority == "高"
    has_rich_notes = bool(needs.notes and len(needs.notes) >= 15)
    has_prefs = bool(needs.taste_preferences or needs.differentiation)

    if has_category and (has_price or has_margin):
        return True
    # 详述型需求：品类+偏好+价位 或 长描述含价位
    if has_category and has_prefs and has_price:
        return True
    if has_rich_notes and (has_price or has_prefs):
        return True
    return False


def missing_field_prompt(profile: CustomerProfile) -> str | None:
    """只追问一个缺失项，避免连环问卷。"""
    needs = profile.needs
    if profile.customer_type.value == "unknown":
        return "方便先说一下您主要是做哪块生意？经销商、烟酒店还是餐饮渠道？"
    if not profile.channels:
        return "了解。您卖酒主要靠团购/关系客户，还是门店零售？"
    if not needs.categories and not needs.notes:
        return "您这次主要想找哪类酒？比如白葡萄酒、红葡萄酒、白酒等。"
    if needs.retail_price_min is None and needs.retail_price_max is None and needs.margin_priority != "高":
        return "期望零售大概在什么价位？可以说个范围，比如 15-20 元或 80-120 元。"
    return None
