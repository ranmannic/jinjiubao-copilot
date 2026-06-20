from __future__ import annotations

"""多轮问询步骤：提示语与按钮一一对应。"""

from app.models.domain import CustomerNeeds, CustomerProfile, QuickReply
from app.core.quick_reply_utils import with_handoff

RETAIL_BANDS: dict[str, tuple[float, float, str]] = {
    "retail_under_30": (0, 30, "30元以内"),
    "retail_30_50": (30, 50, "30-50元"),
    "retail_50_100": (50, 100, "50-100元"),
    "retail_100_200": (100, 200, "100-200元"),
    "retail_200_300": (200, 300, "200-300元"),
    "retail_300_500": (300, 500, "300-500元"),
    "retail_500_1000": (500, 1000, "500-1000元"),
    "retail_1000_plus": (1000, 99999, "1000元以上"),
}


def current_need_step(profile: CustomerProfile, metadata: dict) -> str:
    needs = profile.needs
    if not needs.categories:
        return "category"
    if not needs.taste_preferences and metadata.get("need_step") != "taste_done":
        return "taste"
    if needs.retail_price_min is None and needs.retail_price_max is None and needs.margin_priority != "高":
        return "price"
    return "done"


def need_step_prompt_and_replies(
    profile: CustomerProfile,
    metadata: dict,
) -> tuple[str, list[QuickReply]]:
    step = current_need_step(profile, metadata)
    if step == "category":
        return "您这次主要想找哪类酒？（品类/类型）", with_handoff([
            QuickReply(id="c_white", label="白葡萄酒", value="need_cat:白葡萄酒"),
            QuickReply(id="c_red", label="红葡萄酒", value="need_cat:红葡萄酒"),
            QuickReply(id="c_baijiu", label="国产白酒", value="need_cat:国产白酒"),
            QuickReply(id="c_sparkling", label="起泡/香槟", value="need_cat:起泡/香槟"),
            QuickReply(id="c_beer", label="精酿啤酒", value="need_cat:精酿啤酒"),
            QuickReply(id="c_fruit", label="果酒", value="need_cat:果酒"),
        ])
    if step == "taste":
        return "口感或卖点偏好？（可多选或文字描述）", with_handoff([
            QuickReply(id="t_smooth", label="口感好/易入口", value="need_taste:口感好"),
            QuickReply(id="t_margin", label="利润型/高毛利", value="need_taste:零售定价高"),
            QuickReply(id="t_unique", label="当地差异化", value="need_taste:当地差异化"),
            QuickReply(id="t_brand", label="品牌/宴请", value="need_taste:品牌势能"),
            QuickReply(id="t_fast", label="走量/周转快", value="need_taste:周转快"),
            QuickReply(id="t_skip", label="暂不限", value="need_taste:skip"),
        ])
    if step == "price":
        return "期望零售价位段？（选择区间）", with_handoff([
            QuickReply(id="p_u30", label="30元以内", value="retail_under_30"),
            QuickReply(id="p_30_50", label="30-50元", value="retail_30_50"),
            QuickReply(id="p_50_100", label="50-100元", value="retail_50_100"),
            QuickReply(id="p_100_200", label="100-200元", value="retail_100_200"),
            QuickReply(id="p_200_300", label="200-300元", value="retail_200_300"),
            QuickReply(id="p_300_500", label="300-500元", value="retail_300_500"),
            QuickReply(id="p_500_1000", label="500-1000元", value="retail_500_1000"),
            QuickReply(id="p_1000p", label="1000元以上", value="retail_1000_plus"),
        ])
    return "还有别的需求要补充吗？可直接描述。", with_handoff([
        QuickReply(id="n_custom", label="补充需求", value="custom_need"),
    ])


def apply_retail_band(needs: CustomerNeeds, band_key: str) -> None:
    if band_key in RETAIL_BANDS:
        lo, hi, _ = RETAIL_BANDS[band_key]
        needs.retail_price_min = float(lo if lo > 0 else 1)
        needs.retail_price_max = float(hi if hi < 99999 else 2000)
