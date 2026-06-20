from __future__ import annotations

from app.models.domain import (
    CHANNEL_SCENE_LABELS,
    CUSTOMER_TYPE_LABELS,
    ChannelScene,
    ConversationPhase,
    CustomerType,
)


TYPE_KEYWORDS: dict[CustomerType, list[str]] = {
    CustomerType.DEALER: ["经销商", "批发", "分销商", "代理"],
    CustomerType.IMPORTER: ["进口商", "贸易", "进口贸易"],
    CustomerType.PREMIUM_WINE_SHOP: ["高端烟酒店", "烟酒店", "名烟名酒"],
    CustomerType.RETAIL_CONVENIENCE: ["便利店", "杂货", "超市", "小卖部"],
    CustomerType.RESTAURANT: ["餐厅", "饭店", "酒店", "餐饮"],
    CustomerType.CLUB_BAR: ["会所", "ktv", "酒吧", "夜场", "club"],
    CustomerType.CORPORATE_GIFT: ["企业", "礼品", "团购公司", "福利"],
}

CHANNEL_KEYWORDS: dict[ChannelScene, list[str]] = {
    ChannelScene.GROUP_PURCHASE: ["团购", "关系", "宴请", "送礼", "政企"],
    ChannelScene.RETAIL: ["门店零售", "散客", "便利店卖"],
    ChannelScene.BANQUET: ["宴席", "婚宴", "寿宴", "酒席"],
    ChannelScene.RESTAURANT_PAIRING: ["配餐", "餐饮", "后厨", "包间"],
    ChannelScene.CORPORATE_GIFT: ["礼品", "福利", "企业采购"],
    ChannelScene.ONLINE_DISTRIBUTION: ["私域", "线上", "直播", "社群"],
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "白葡萄酒": ["白葡萄酒", "白酒（葡萄）", "干白", "半甜白", "雷司令", "霞多丽"],
    "红葡萄酒": ["红葡萄酒", "红酒", "干红", "赤霞珠", "梅洛"],
    "起泡/香槟": ["起泡", "香槟", "sparkling"],
    "国产白酒": ["国产白酒", "酱香", "浓香", "毛府"],
    "精酿啤酒": ["精酿", "啤酒", "翁布里亚"],
    "果酒": ["果酒", "洛齐", "半甜"],
}

NEED_KEYWORDS: dict[str, list[str]] = {
    "口感好": ["口感好", "好喝", "顺", "易入口", "好推"],
    "供货便宜": ["便宜", "低价", "供货价", "成本", "利润空间"],
    "零售定价高": ["零售定价高", "零售高", "定价高", "卖贵", "高毛利"],
    "当地差异化": ["独家", "少见", "不透明", "没人做", "差异化", "不撞款"],
    "周转快": ["走量", "动销", "快销", "复购"],
    "品牌势能": ["品牌", "有面子", "宴请", "送礼", "标杆"],
}

PHASE_ORDER = [
    ConversationPhase.WELCOME,
    ConversationPhase.TYPE_IDENTIFICATION,
    ConversationPhase.CHANNEL_DISCOVERY,
    ConversationPhase.NEED_DISCOVERY,
    ConversationPhase.RECOMMENDATION,
    ConversationPhase.BUSINESS_PLAN,
    ConversationPhase.HANDOFF,
]


def classify_customer_type(text: str) -> tuple[CustomerType, float]:
    lowered = text.lower()
    scores: dict[CustomerType, int] = {t: 0 for t in CustomerType if t != CustomerType.UNKNOWN}
    for ctype, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                scores[ctype] += 1
    best = max(scores, key=scores.get)
    score = scores[best]
    if score == 0:
        return CustomerType.UNKNOWN, 0.0
    return best, min(0.95, 0.5 + score * 0.15)


def classify_channels(text: str, *, from_quick_reply: bool = False) -> list[ChannelScene]:
    """从自然语言推断渠道。快捷选项 value 已是明确渠道码时不应再跑关键词匹配。"""
    if from_quick_reply:
        return []
    lowered = text.lower()
    found: list[ChannelScene] = []
    for scene, keywords in CHANNEL_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(scene)
    return found or []


def extract_categories(text: str) -> list[str]:
    """按关键词长度优先匹配，避免「白葡萄酒」被「白酒」误命中。"""
    lowered = text.lower()
    matched: list[str] = []
    pairs: list[tuple[str, str]] = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            pairs.append((cat, kw))
    pairs.sort(key=lambda x: len(x[1]), reverse=True)
    used_spans: list[tuple[int, int]] = []
    for cat, kw in pairs:
        start = lowered.find(kw)
        if start == -1:
            continue
        end = start + len(kw)
        if any(not (end <= s or start >= e) for s, e in used_spans):
            continue
        if cat not in matched:
            matched.append(cat)
        used_spans.append((start, end))
    return matched


def extract_needs_from_text(text: str) -> dict[str, object]:
    lowered = text.lower()
    result: dict[str, object] = {
        "categories": [],
        "taste_preferences": [],
        "differentiation": [],
    }
    for cat in extract_categories(text):
        if cat not in result["categories"]:
            result["categories"].append(cat)
    for need, keywords in NEED_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            if need in {"口感好", "供货便宜", "零售定价高", "周转快", "品牌势能"}:
                result["taste_preferences"].append(need)
            elif need == "当地差异化":
                result["differentiation"].append(need)
    if "利润" in lowered or "毛利" in lowered:
        result["margin_priority"] = "高"
    if "试" in lowered or "样品" in lowered:
        result["order_intent"] = "trial"
    if "大批量" in lowered or "整柜" in lowered or "100箱" in lowered:
        result["order_intent"] = "bulk"
    return result


def map_quick_reply_to_type(value: str) -> CustomerType | None:
    mapping = {
        "dealer": CustomerType.DEALER,
        "importer": CustomerType.IMPORTER,
        "premium_wine_shop": CustomerType.PREMIUM_WINE_SHOP,
        "retail_convenience": CustomerType.RETAIL_CONVENIENCE,
        "restaurant": CustomerType.RESTAURANT,
        "club_bar": CustomerType.CLUB_BAR,
        "corporate_gift": CustomerType.CORPORATE_GIFT,
    }
    return mapping.get(value)


def map_quick_reply_to_channel(value: str) -> ChannelScene | None:
    mapping = {
        "group_purchase": ChannelScene.GROUP_PURCHASE,
        "retail": ChannelScene.RETAIL,
        "banquet": ChannelScene.BANQUET,
        "restaurant_pairing": ChannelScene.RESTAURANT_PAIRING,
        "corporate_gift": ChannelScene.CORPORATE_GIFT,
        "online_distribution": ChannelScene.ONLINE_DISTRIBUTION,
        "mixed": ChannelScene.MIXED,
    }
    return mapping.get(value)


def next_phase(current: ConversationPhase) -> ConversationPhase | None:
    try:
        idx = PHASE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PHASE_ORDER):
        return None
    return PHASE_ORDER[idx + 1]


def type_label(customer_type: CustomerType) -> str:
    return CUSTOMER_TYPE_LABELS.get(customer_type, "未明确")


def channel_label(scene: ChannelScene) -> str:
    return CHANNEL_SCENE_LABELS.get(scene, scene.value)
