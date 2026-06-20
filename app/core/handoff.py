from __future__ import annotations

import re

from app.models.domain import ConversationPhase, CustomerProfile, HandoffPayload


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


def build_crm_lead(profile: CustomerProfile, handoff: HandoffPayload, session_id: str) -> dict:
    return {
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
    }
