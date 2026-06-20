from __future__ import annotations

from app.core.eligibility import check_product_eligibility, regular_wholesale_policy_note
from app.models.domain import (
    BusinessPlan,
    ChannelScene,
    CustomerNeeds,
    CustomerProfile,
    CustomerType,
    ProductRecommendation,
)


def _margin_rate(supply: float, retail_mid: float) -> float:
    if retail_mid <= 0:
        return 0.0
    return max(0.0, (retail_mid - supply) / retail_mid * 100)


def _score_product(
    product: dict,
    profile: CustomerProfile,
    region_competition: dict[str, int] | None = None,
) -> tuple[float, list[str], list[dict], str | None]:
    needs = profile.needs
    reasons: list[str] = []
    breakdown: list[dict] = []
    score = 0.0
    region_competition = region_competition or {}

    def add(points: float, label: str, detail: str) -> None:
        nonlocal score
        score += points
        breakdown.append({"label": label, "points": points, "detail": detail})
        if points > 0:
            reasons.append(detail)

    category = product.get("category", "")
    if needs.categories and any(c in category for c in needs.categories):
        add(35, "品类匹配", f"匹配品类：{category}")

    supply = float(product.get("supply_price", 0))
    retail_min = float(product.get("retail_min", 0))
    retail_max = float(product.get("retail_max", 0))
    retail_mid = (retail_min + retail_max) / 2

    if needs.supply_price_max and supply <= needs.supply_price_max:
        add(15, "供货预算", "供货价在预算内")
    if needs.retail_price_min and needs.retail_price_max:
        if retail_max < needs.retail_price_min or retail_min > needs.retail_price_max:
            add(-40, "价位偏差", "价位与目标区间部分重叠")
        elif retail_min >= needs.retail_price_min and retail_max <= needs.retail_price_max:
            add(15, "零售价位", "零售价落在目标区间")
        elif retail_mid >= needs.retail_price_min and retail_mid <= needs.retail_price_max:
            add(10, "零售价位", "主力成交价符合目标价位")

    margin = _margin_rate(supply, retail_mid)
    if needs.margin_priority == "高" and margin >= 35:
        add(20, "毛利空间", f"毛利空间约{margin:.0f}%")

    tags = product.get("tags", [])
    if "口感好" in needs.taste_preferences and "易推销" in tags:
        add(8, "口感标签", "口感友好、易推销")

    diff_note = None
    if "当地差异化" in needs.differentiation:
        city = profile.needs.region_city or profile.region or "当地"
        competitors = region_competition.get(product.get("sku_id", ""), 0)
        if competitors <= 2:
            add(12, "区域差异化", f"{city}同价位较少客户在做")
        diff_note = f"{city}目前约 {competitors} 家客户在卖，差异化{'较好' if competitors <= 2 else '一般'}"

    if profile.customer_type == CustomerType.PREMIUM_WINE_SHOP and "礼盒" in tags:
        add(5, "业态匹配", "适合团购礼盒场景")
    if profile.customer_type == CustomerType.RETAIL_CONVENIENCE and "高周转" in tags:
        add(8, "业态匹配", "动销快、适合零售")

    strategic = float(product.get("strategic_weight", 0))
    if strategic:
        add(strategic, "战略权重", f"平台战略加权 +{strategic:.0f}")

    return score, reasons, breakdown, diff_note


def _wholesale_policy_text(product: dict) -> str:
    moq = product.get("moq", 6)
    return (
        f"常规批发价 ¥{product.get('supply_price', 0):.0f}/瓶；"
        f"标准 MOQ {moq} 瓶/箱起；"
        f"常规物流与售后按进酒宝标准政策执行。"
    )


def recommend_products(
    products: list[dict],
    profile: CustomerProfile,
    region_competition: dict[str, int] | None = None,
    limit: int = 3,
    include_ineligible: bool = False,
) -> list[ProductRecommendation]:
    scored: list[ProductRecommendation] = []
    blocked: list[ProductRecommendation] = []

    for p in products:
        eligible, block_reason = check_product_eligibility(p, profile, region_competition)
        s, reasons, breakdown, diff = _score_product(p, profile, region_competition)
        supply = float(p["supply_price"])
        rmin = float(p["retail_min"])
        rmax = float(p["retail_max"])
        rec = ProductRecommendation(
            sku_id=p["sku_id"],
            name=p["name"],
            brand=p["brand"],
            category=p["category"],
            supply_price=supply,
            suggested_retail_min=rmin,
            suggested_retail_max=rmax,
            margin_rate=_margin_rate(supply, (rmin + rmax) / 2),
            match_score=round(s, 1),
            match_reasons=reasons,
            score_breakdown=breakdown,
            eligible=eligible,
            block_reason=block_reason,
            differentiation_note=diff,
            wholesale_policy=_wholesale_policy_text(p) if eligible else None,
            tags=p.get("tags", []),
        )
        if not eligible:
            blocked.append(rec)
            if include_ineligible:
                scored.append(rec)
            continue
        if s <= 0:
            continue
        scored.append(rec)

    scored.sort(key=lambda x: x.match_score, reverse=True)
    result = scored[:limit]
    if not result and blocked and include_ineligible:
        return blocked[:limit]
    return result


def build_business_plan(profile: CustomerProfile, top: ProductRecommendation | None) -> BusinessPlan:
    plans = build_channel_plans(profile, top)
    return plans[0] if plans else _generic_plan(profile, top)


def build_channel_plans(
    profile: CustomerProfile,
    top: ProductRecommendation | None,
    limit: int = 3,
) -> list[BusinessPlan]:
    ctype = profile.customer_type
    channels = profile.channels
    product_name = top.name if top else "主推 SKU"
    plans: list[BusinessPlan] = []

    if ChannelScene.GROUP_PURCHASE in channels or profile.channel_mode == "group":
        plans.append(
            BusinessPlan(
                plan_id="P_group",
                title="团购/关系客户 · 高毛利方案",
                channel_fit="团购/政企/宴请关系",
                pricing_strategy=(
                    f"建议零售价标 {top.suggested_retail_max:.0f} 元，团购成交价留 10-15% 关系空间"
                    if top
                    else "零售价留足关系折扣空间"
                ),
                detailed_explanation=(
                    "【方案说明】团购客户决策链长、重面子与稳定供应。本方案以「口感普适 + 控价」为核心："
                    "对外强调非电商比价款，对内留足关系折扣。首单建议 2 箱试销，覆盖 2-3 个核心关系客户，"
                    "验证复购后再谈阶梯价。适合烟酒店、礼品公司做政企/家宴场景。"
                ),
                talk_tracks=[
                    "这款半甜白入口顺、男女都能接受，家宴宴请不踩雷。",
                    "同价位本地做的人少，您更好控价、更好赚。",
                ],
                bundle_suggestions=[f"{product_name} + 干红礼盒做双支宴请套装"],
                trial_plan="2 箱试销，2 周回访复购",
                risk_notes=["勿过度承诺区域独家，可强调「目前较少渠道在做」"],
            )
        )

    if ChannelScene.RETAIL in channels or profile.channel_mode == "retail":
        plans.append(
            BusinessPlan(
                plan_id="P_retail",
                title="门店零售 · 动销走量方案",
                channel_fit="便利店/名烟名酒门店零售",
                pricing_strategy="明码标价 + 收银台视线位 + 第二件凑单",
                detailed_explanation=(
                    "【方案说明】零售场景重动销与陈列效率。本方案把 SKU 放在收银台或酒类专区视线位，"
                    "用半甜/易入口降低尝试门槛。定价留 35-45% 毛利，控制 SKU 深度，先进先出。"
                    "2 周看动销，好卖再加深度。"
                ),
                talk_tracks=["放收银台视线位", "口感顺、复购率高"],
                bundle_suggestions=["与果酒组成小酒专区"],
                trial_plan="1 箱陈列测试 2 周",
                risk_notes=["注意效期轮换"],
            )
        )

    if ctype == CustomerType.DEALER or profile.channel_mode == "wholesale":
        plans.append(
            BusinessPlan(
                plan_id="P_dealer",
                title="经销批发 · 铺货分销方案",
                channel_fit="经销商/批发商",
                pricing_strategy="按周转档位设阶梯价，鼓励整箱补货",
                detailed_explanation=(
                    "【方案说明】经销商关注周转、下游利润与物流成本。本方案提供下游话术包与组合进货建议，"
                    "降低铺货阻力。先选 1-2 个主力 SKU 铺终端，根据回款节奏再扩 SKU。"
                ),
                talk_tracks=["提供零售话术包", "强调进酒宝物流稳定"],
                bundle_suggestions=["葡萄酒+白酒组合降低物流成本"],
                trial_plan="先 2 个 SKU 铺终端",
                risk_notes=["大批量及账期请转销售"],
            )
        )

    if ChannelScene.ONLINE_DISTRIBUTION in channels or profile.channel_mode == "online":
        plans.append(
            BusinessPlan(
                plan_id="P_online",
                title="线上私域 · 控价分销方案",
                channel_fit="电商/私域/社群",
                pricing_strategy="统一控价 + 素材包，避免乱价",
                detailed_explanation=(
                    "【方案说明】线上渠道需控价与内容素材。提供产品图、卖点话术，"
                    "规定最低零售价，私域拼团留 5-8% 活动空间。"
                ),
                talk_tracks=["强调线下专供、非电商比价款"],
                bundle_suggestions=["双支礼盒装提升客单"],
                trial_plan="小批量测转化后再加码",
                risk_notes=["严禁低于指导价销售"],
            )
        )

    if not plans:
        plans.append(_generic_plan(profile, top))

    return plans[:limit]


def _generic_plan(profile: CustomerProfile, top: ProductRecommendation | None) -> BusinessPlan:
    return BusinessPlan(
        plan_id="generic",
        title="通用卖货方案",
        channel_fit="综合渠道",
        pricing_strategy="按渠道留 30-45% 毛利空间",
        detailed_explanation=(
            "【方案说明】根据您的业态与渠道，建议先小批量试销验证动销，"
            "再与销售谈规模政策。常规批发价见产品报价，特殊政策请转人工。"
        ),
        talk_tracks=["先讲口感场景，再讲价格"],
        bundle_suggestions=["红白搭配提升客单"],
        trial_plan="建议小批量试销 1-2 周",
        risk_notes=["大批量及账期请转销售"],
    )


def price_policy_message(recs: list[ProductRecommendation]) -> str:
    lines = [regular_wholesale_policy_note(), ""]
    eligible = [r for r in recs if r.eligible]
    if not eligible:
        lines.append("当前推荐 SKU 均因区域/身份/库存限制暂无法报价，请转销售沟通。")
        return "\n".join(lines)

    lines.append("**常规批发价及政策：**")
    for idx, r in enumerate(eligible[:3], 1):
        lines.append(f"\n{idx}. **{r.name}**")
        lines.append(f"   {r.wholesale_policy or '见标准批发政策'}")
        lines.append(
            f"   建议零售 ¥{r.suggested_retail_min:.0f}-¥{r.suggested_retail_max:.0f}，"
            f"毛利约 {r.margin_rate:.0f}%"
        )
    lines.append(
        "\n如需区域代理、混合批发、大批量（≥100件）或账期等特殊政策，请点击「转人工」。"
    )
    return "\n".join(lines)


def apply_price_band(needs: CustomerNeeds, value: str) -> CustomerNeeds:
    bands = {
        "retail_50_80": (50, 80),
        "retail_80_120": (80, 120),
        "retail_120_200": (120, 200),
        "retail_200_plus": (200, 9999),
    }
    if value in bands:
        lo, hi = bands[value]
        needs.retail_price_min = float(lo)
        needs.retail_price_max = float(hi if hi < 9999 else 500)
        if hi < 9999:
            needs.supply_price_max = hi * 0.55
    if value == "margin_high":
        needs.margin_priority = "高"
    if value == "local_unique":
        needs.differentiation.append("当地差异化")
    return needs
