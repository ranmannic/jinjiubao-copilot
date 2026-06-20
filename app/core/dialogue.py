from __future__ import annotations

from app.core.eligibility import regular_wholesale_policy_note
from app.core.product_match import product_detail_line
from app.core.quick_replies import with_handoff, returning_need_quick_replies, identity_quick_replies
from app.models.domain import (
    BusinessPlan,
    CustomerProfile,
    ProductRecommendation,
    QuickReply,
)
from app.core.nlp_utils import channel_label, type_label


def welcome_message(profile: CustomerProfile, *, is_new: bool = True) -> tuple[str, list[QuickReply]]:
    name = profile.customer_name or "老板"
    if profile.is_returning and not is_new:
        prompt, replies = returning_need_quick_replies()
        msg = (
            f"{name}您好，欢迎回到进酒宝！我是 AI 选品顾问。\n\n"
            f"{prompt}"
        )
        return msg, replies

    prompt, replies = identity_quick_replies()
    msg = (
        f"{name}您好，初次见面，欢迎进酒宝！我是 AI 选品顾问，"
        f"先了解您的身份和经营城市，再帮您精准推品。\n\n{prompt}"
    )
    return msg, replies


def inquiry_city_message() -> str:
    return "了解。请告诉我您的经营所在城市（选择下方城市或输入）："


def channel_plans_message(plans: list[BusinessPlan]) -> str:
    if not plans:
        return ""
    lines = ["根据您的渠道，为您准备以下业务方案（可先浏览再选品）：", ""]
    for idx, p in enumerate(plans[:3], 1):
        lines.append(f"**方案{idx}：{p.title}**（适合：{p.channel_fit or '综合'}）")
        lines.append(p.detailed_explanation or p.pricing_strategy)
        lines.append("")
    lines.append("确认方向后，我再帮您匹配具体 SKU。也可直接说您的选品需求。")
    return "\n".join(lines)


def _attrs_line(rec: ProductRecommendation) -> str:
    line = product_detail_line(rec)
    return f"   产品信息：{line}" if line else ""


def recommendation_message(
    profile: CustomerProfile,
    recommendations: list[ProductRecommendation],
) -> tuple[str, list[QuickReply]]:
    from app.core.quick_replies import post_recommendation_quick_replies

    eligible = [r for r in recommendations if r.eligible]

    if not eligible:
        msg = "暂未匹配到可对外推荐的 SKU，建议转专属销售进一步对接（区域/库存限制等）。"
        return msg, with_handoff([QuickReply(id="handoff", label="转人工", value="handoff")])

    lines = [
        f"根据您「{type_label(profile.customer_type)}」+ "
        f"{'、'.join(channel_label(c) for c in profile.channels) or profile.channel_mode or '渠道待确认'}」的需求，"
        f"为您精选以下产品：",
        "",
        regular_wholesale_policy_note(),
        "",
    ]

    for idx, rec in enumerate(eligible[:3], start=1):
        reasons = "；".join(rec.match_reasons[:2]) or "综合匹配"
        lines.append(f"{idx}. **{rec.name}**（{rec.brand}）")
        lines.append(f"   推荐分 **{rec.match_score:.0f}**｜{reasons}")
        if rec.score_breakdown:
            detail = " + ".join(
                f"{b['label']}{b['points']:+.0f}" for b in rec.score_breakdown[:5]
            )
            lines.append(f"   计分明细：{detail}")
        attrs = _attrs_line(rec)
        if attrs:
            lines.append(attrs)
        lines.append(
            f"   常规批发约 ¥{rec.supply_price:.0f}，建议零售 "
            f"¥{rec.suggested_retail_min:.0f}-¥{rec.suggested_retail_max:.0f}，毛利约 {rec.margin_rate:.0f}%"
        )
        if rec.mismatch_notes:
            for note in rec.mismatch_notes[:2]:
                lines.append(f"   ※ 说明：{note}")
        if rec.differentiation_note:
            lines.append(f"   区域：{rec.differentiation_note}")
        lines.append("")

    lines.append("下一步：查看**价格及政策**、**业务方案**，或有异议可直接说。")
    prompt, replies = post_recommendation_quick_replies()
    return "\n".join(lines), replies


def business_plans_message(plans: list[BusinessPlan]) -> str:
    if not plans:
        return "暂无匹配方案。"
    parts = ["**为您匹配的业务方案（共 {} 套）：**".format(len(plans)), ""]
    for idx, plan in enumerate(plans[:3], 1):
        tracks = "\n".join(f"  · {t}" for t in plan.talk_tracks[:2])
        parts.append(f"### 方案{idx}：{plan.title}")
        if plan.channel_fit:
            parts.append(f"**适合渠道：** {plan.channel_fit}")
        parts.append(plan.detailed_explanation or plan.pricing_strategy)
        parts.append(f"**定价策略：** {plan.pricing_strategy}")
        if tracks:
            parts.append(f"**话术要点：**\n{tracks}")
        if plan.trial_plan:
            parts.append(f"**试销建议：** {plan.trial_plan}")
        parts.append("")
    parts.append("如需代理、混批、大批量（≥100件）等特殊政策，请转人工。")
    return "\n".join(parts)


def business_plan_message(plan: BusinessPlan) -> tuple[str, list[QuickReply]]:
    tracks = "\n".join(f"· {t}" for t in plan.talk_tracks[:3])
    bundles = "\n".join(f"· {b}" for b in plan.bundle_suggestions[:2])
    risks = "\n".join(f"· {r}" for r in plan.risk_notes[:2])
    msg = (
        f"**{plan.title}**\n\n"
        f"{plan.detailed_explanation}\n\n"
        f"**定价策略**\n{plan.pricing_strategy}\n\n"
        f"**推荐话术**\n{tracks}\n\n"
        f"**组合建议**\n{bundles}\n\n"
        f"**试销建议**\n{plan.trial_plan or '可先 1-2 箱试销验证动销'}\n\n"
        f"**风险提示**\n{risks}"
    )
    replies = with_handoff([
        QuickReply(id="quote", label="看价格政策", value="show_price_policy"),
        QuickReply(id="sample", label="申请样品", value="request_sample"),
        QuickReply(id="continue", label="继续选品", value="continue_category"),
    ])
    return msg, replies


def handoff_message(profile: CustomerProfile, reason: str, sales_name: str | None) -> str:
    sales = sales_name or "专属客户经理"
    return (
        f"好的，已为您安排{sales}跟进，并已通过进酒宝通知销售同事。\n"
        f"转接原因：{reason}\n"
        f"我们会在 30 分钟内电话与您对接。\n\n"
        f"已同步需求画像、推荐记录与计分明细。"
        f"{'（' + profile.customer_name + '）' if profile.customer_name else ''}"
    )
