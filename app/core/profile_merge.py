from __future__ import annotations

from typing import Any, Optional

from app.core.need_steps import current_need_step
from app.core.nlp_utils import map_quick_reply_to_channel, map_quick_reply_to_type
from app.core.quick_replies import get_quick_replies_for_session
from app.models.domain import (
    ChannelScene,
    ConversationPhase,
    ConversationSession,
    CustomerNeeds,
    CustomerProfile,
    CustomerType,
    QuickReply,
)


TYPE_FROM_LLM: dict[str, CustomerType] = {
    "dealer": CustomerType.DEALER,
    "importer": CustomerType.IMPORTER,
    "premium_wine_shop": CustomerType.PREMIUM_WINE_SHOP,
    "retail_convenience": CustomerType.RETAIL_CONVENIENCE,
    "restaurant": CustomerType.RESTAURANT,
    "club_bar": CustomerType.CLUB_BAR,
    "corporate_gift": CustomerType.CORPORATE_GIFT,
    "personal_use": CustomerType.PERSONAL_USE,
    "online_ecommerce": CustomerType.ONLINE_ECOMMERCE,
}

CHANNEL_FROM_LLM: dict[str, ChannelScene] = {
    "group_purchase": ChannelScene.GROUP_PURCHASE,
    "retail": ChannelScene.RETAIL,
    "banquet": ChannelScene.BANQUET,
    "restaurant_pairing": ChannelScene.RESTAURANT_PAIRING,
    "corporate_gift": ChannelScene.CORPORATE_GIFT,
    "online_distribution": ChannelScene.ONLINE_DISTRIBUTION,
    "mixed": ChannelScene.MIXED,
}


def infer_phase(session: ConversationSession) -> ConversationPhase:
    if session.handoff.required:
        return ConversationPhase.HANDOFF
    if session.phase in {
        ConversationPhase.PRICE_POLICY,
        ConversationPhase.OBJECTION,
        ConversationPhase.BUSINESS_PLAN,
    } and session.recommendations:
        return session.phase

    profile = session.profile
    needs = profile.needs

    if profile.is_returning:
        step = current_need_step(profile, session.metadata)
        if step != "done" and not session.recommendations:
            return ConversationPhase.NEED_DISCOVERY
        if session.recommendations:
            return ConversationPhase.RECOMMENDATION
        return ConversationPhase.NEED_DISCOVERY

    if profile.customer_type == CustomerType.UNKNOWN:
        return ConversationPhase.TYPE_IDENTIFICATION

    if not needs.region_city:
        return ConversationPhase.INQUIRY

    step = current_need_step(profile, session.metadata)
    if step != "done" and not session.recommendations:
        return ConversationPhase.NEED_DISCOVERY

    if session.recommendations:
        return ConversationPhase.RECOMMENDATION

    return ConversationPhase.NEED_DISCOVERY


def default_quick_replies(session: ConversationSession) -> list[QuickReply]:
    _, replies = get_quick_replies_for_session(session)
    return replies


def default_quick_reply_prompt(session: ConversationSession) -> Optional[str]:
    prompt, _ = get_quick_replies_for_session(session)
    return prompt


def apply_llm_profile_updates(profile: CustomerProfile, updates: dict[str, Any]) -> None:
    if not updates:
        return
    needs = profile.needs

    raw_type = updates.get("customer_type")
    if raw_type and raw_type != "null":
        if raw_type in TYPE_FROM_LLM:
            profile.customer_type = TYPE_FROM_LLM[raw_type]
            profile.customer_type_confidence = 0.9
        else:
            mapped = map_quick_reply_to_type(str(raw_type))
            if mapped:
                profile.customer_type = mapped

    for ch in updates.get("channels") or []:
        if ch in CHANNEL_FROM_LLM:
            scene = CHANNEL_FROM_LLM[ch]
        else:
            scene = map_quick_reply_to_channel(str(ch))
        if scene and scene not in profile.channels:
            profile.channels.append(scene)

    for cat in updates.get("categories") or []:
        if cat and cat not in needs.categories:
            needs.categories.append(str(cat))
    for t in updates.get("taste_preferences") or []:
        if t and t not in needs.taste_preferences:
            needs.taste_preferences.append(str(t))
    for d in updates.get("differentiation") or []:
        if d and d not in needs.differentiation:
            needs.differentiation.append(str(d))

    if updates.get("margin_priority") and updates.get("margin_priority") != "null":
        needs.margin_priority = str(updates["margin_priority"])
    if updates.get("order_intent") and updates.get("order_intent") != "null":
        needs.order_intent = str(updates["order_intent"])
    if updates.get("region_city"):
        needs.region_city = str(updates["region_city"])
    if updates.get("notes"):
        needs.notes = str(updates["notes"])

    rmin = updates.get("retail_price_min")
    rmax = updates.get("retail_price_max")
    if rmin is not None:
        needs.retail_price_min = float(rmin)
    if rmax is not None:
        needs.retail_price_max = float(rmax)
    if needs.retail_price_min and not needs.retail_price_max:
        needs.retail_price_max = needs.retail_price_min * 1.5
