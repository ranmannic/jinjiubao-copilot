from __future__ import annotations

import re

from app.models.domain import ConversationPhase, CustomerProfile, HandoffPayload, ProductRecommendation


HANDOFF_KEYWORDS = [
    "转人工",
    "人工",
    "销售",
    "打电话",
    "联系我",
    "电话",
    "经理",
    "最低多少",
    "能不能再便宜",
    "独家",
    "账期",
    "赊销",
    "大批量",
    "100箱",
    "整柜",
    "定制",
    "oem",
]

BULK_PATTERN = re.compile(r"(\d+)\s*箱")


def compute_intent_score(profile: CustomerProfile, user_text: str, phase: ConversationPhase) -> int:
    score = 0
    text = user_text.lower()

    if profile.needs.order_intent == "bulk":
        score += 35
    if profile.needs.order_intent == "trial":
        score += 15
    if any(k in text for k in ["下单", "进货", "要货", "成交"]):
        score += 25
    if any(k in text for k in HANDOFF_KEYWORDS):
        score += 30
    if BULK_PATTERN.search(text):
        score += 20
    if phase in {ConversationPhase.RECOMMENDATION, ConversationPhase.BUSINESS_PLAN}:
        score += 10
    if profile.customer_type.value in {"dealer", "importer"}:
        score += 5
    return min(100, score)


def should_handoff(
    profile: CustomerProfile,
    user_text: str,
    phase: ConversationPhase,
    threshold: int = 70,
    explicit: bool = False,
) -> HandoffPayload:
    text = user_text.lower()
    intent = compute_intent_score(profile, user_text, phase)
    reasons: list[str] = []

    if explicit or any(k in text for k in ["转人工", "handoff", "让销售"]):
        reasons.append("客户主动要求销售对接")
    if any(k in text for k in ["最低", "再便宜", "折扣", "返点"]):
        reasons.append("进入议价深水区")
        intent = max(intent, 75)
    if any(k in text for k in ["独家", "账期", "赊销", "定制"]):
        reasons.append("涉及独家/账期/定制条款")
        intent = max(intent, 80)
    if BULK_PATTERN.search(text):
        reasons.append("大批量采购意向")
        intent = max(intent, 78)
    if profile.needs.order_intent == "bulk":
        reasons.append("识别到大宗采购需求")

    required = explicit or intent >= threshold or bool(reasons)
    reason = "；".join(reasons) if reasons else ("意向达到转接阈值" if required else None)

    summary_parts = [
        f"业态：{profile.customer_type.value}",
        f"渠道：{','.join(c.value for c in profile.channels) or '待确认'}",
        f"品类：{','.join(profile.needs.categories) or '待确认'}",
        f"偏好：{','.join(profile.needs.taste_preferences) or '待确认'}",
    ]

    return HandoffPayload(
        required=required,
        reason=reason,
        intent_score=intent,
        conversation_summary="；".join(summary_parts),
    )


def _blocked_for_sales(blocked: list[ProductRecommendation]) -> list[dict]:
    items = []
    for r in blocked:
        items.append({
            "sku_id": r.sku_id,
            "name": r.name,
            "brand": r.brand,
            "match_score": r.match_score,
            "block_reason": r.block_reason,
            "do_not_quote": True,
            "sales_note": f"请勿对客户报价：{r.block_reason}",
        })
    return items


def build_crm_lead(
    profile: CustomerProfile,
    handoff: HandoffPayload,
    session_id: str,
    recommendations: list[ProductRecommendation] | None = None,
    blocked: list[ProductRecommendation] | None = None,
) -> dict:
    blocked_items = _blocked_for_sales(blocked or [])
    lead = {
        "session_id": session_id,
        "customer_id": profile.customer_id,
        "customer_name": profile.customer_name,
        "phone": profile.phone,
        "customer_type": profile.customer_type.value,
        "channels": [c.value for c in profile.channels],
        "needs": profile.needs.model_dump(),
        "intent_score": handoff.intent_score,
        "handoff_reason": handoff.reason,
        "summary": handoff.conversation_summary,
        "priority": "hot" if handoff.intent_score >= 80 else "warm" if handoff.intent_score >= 60 else "cold",
        "recommended_skus": [r.sku_id for r in (recommendations or []) if r.eligible],
        "blocked_skus_for_sales": blocked_items,
    }
    if blocked_items:
        lead["sales_alert"] = (
            "以下 SKU 匹配度较高但不可对客户报价，请销售知悉原因后再内部评估："
            + "；".join(f"{x['name']}（{x['block_reason']}）" for x in blocked_items)
        )
    return lead
