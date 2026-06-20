from __future__ import annotations

"""带提示文案的快捷交互栏，始终保留转人工入口。"""

from app.core.cities import CITY_OPTIONS
from app.models.domain import (
    ChannelScene,
    ConversationPhase,
    ConversationSession,
    CustomerType,
    QuickReply,
    StoreType,
)


def handoff_reply() -> QuickReply:
    return QuickReply(
        id="handoff_always",
        label="转人工",
        value="handoff",
        reply_type="handoff",
        style="primary-outline",
    )


def with_handoff(replies: list[QuickReply], max_items: int = 7) -> list[QuickReply]:
    out = [r for r in replies if r.value != "handoff"][:max_items]
    if not any(r.value == "handoff" for r in out):
        out.append(handoff_reply())
    return out


def identity_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "请告诉我您的身份（也可文字补充说明）："
    replies = [
        QuickReply(id="t_premium", label="高端烟酒店", value="premium_wine_shop"),
        QuickReply(id="t_dealer", label="经销/批发商", value="dealer"),
        QuickReply(id="t_retail", label="烟酒便利店", value="retail_convenience"),
        QuickReply(id="t_corporate", label="企业团购", value="corporate_gift"),
        QuickReply(id="t_online", label="线上电商", value="dealer", reply_type="chip"),
        QuickReply(id="t_restaurant", label="餐厅酒吧", value="restaurant"),
        QuickReply(id="t_other", label="其他", value="custom_need"),
    ]
    return prompt, with_handoff(replies)


def channel_mode_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "您的主要经营模式是？（可多选或文字描述，便于区分批发/团购/零售/特殊模式）"
    replies = [
        QuickReply(id="m_wholesale", label="以批发为主", value="channel_wholesale"),
        QuickReply(id="m_group", label="以团购/关系为主", value="group_purchase"),
        QuickReply(id="m_retail", label="以门店零售为主", value="retail"),
        QuickReply(id="m_mixed", label="多种兼而有之", value="mixed"),
        QuickReply(id="m_online", label="线上/私域", value="online_distribution"),
        QuickReply(id="m_banquet", label="宴席/婚宴", value="banquet"),
    ]
    return prompt, with_handoff(replies)


def inquiry_city_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "问询：请告诉我您的经营所在地（选择城市或输入）："
    replies = [
        QuickReply(id=f"city_{i}", label=c, value=f"city:{c}", reply_type="city")
        for i, c in enumerate(CITY_OPTIONS[:12])
    ]
    replies.append(QuickReply(id="city_more", label="更多城市…", value="city:custom", reply_type="city"))
    return prompt, with_handoff(replies, max_items=8)


def inquiry_store_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "问询：您是否有实体门店？如有，请选择门店类型："
    replies = [
        QuickReply(id="store_no", label="无门店（纯批发/团购）", value="store:none"),
        QuickReply(id="store_premium", label="名烟名酒", value="store:premium_wine_shop"),
        QuickReply(id="store_conv", label="烟酒便利零售店", value="store:retail_convenience"),
        QuickReply(id="store_club", label="会所", value="store:club"),
        QuickReply(id="store_rest", label="餐厅/酒吧/酒馆", value="store:restaurant_bar"),
        QuickReply(id="store_super", label="超市/连锁商超", value="store:supermarket"),
        QuickReply(id="store_other", label="其他", value="store:other"),
    ]
    return prompt, with_handoff(replies)


def need_category_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "您这次主要想找哪类酒？"
    replies = [
        QuickReply(id="n_white", label="白葡萄酒", value="白葡萄酒 口感好"),
        QuickReply(id="n_red", label="红葡萄酒", value="红葡萄酒 宴请"),
        QuickReply(id="n_baijiu", label="国产白酒", value="国产白酒 走量"),
        QuickReply(id="n_beer", label="精酿啤酒", value="精酿啤酒"),
        QuickReply(id="n_custom", label="我来说说", value="custom_need"),
    ]
    return prompt, with_handoff(replies)


def post_recommendation_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "需要报价详情、业务方案，或有异议？"
    replies = [
        QuickReply(id="quote", label="看价格及政策", value="show_price_policy"),
        QuickReply(id="plan", label="看业务方案", value="show_plan"),
        QuickReply(id="objection", label="我有顾虑", value="raise_objection"),
        QuickReply(id="sample", label="申请样品", value="request_sample"),
        QuickReply(id="cart", label="加入进货单", value="add_cart"),
    ]
    return prompt, with_handoff(replies)


def get_quick_replies_for_session(session: ConversationSession) -> tuple[str | None, list[QuickReply]]:
    phase = session.phase
    profile = session.profile
    needs = profile.needs

    if phase == ConversationPhase.HANDOFF:
        return None, []

    if phase == ConversationPhase.TYPE_IDENTIFICATION:
        return identity_quick_replies()

    if phase == ConversationPhase.INQUIRY:
        if not needs.region_city and not profile.is_returning:
            return inquiry_city_quick_replies()
        if profile.has_store is None:
            return inquiry_store_quick_replies()
        return channel_mode_quick_replies()

    if phase == ConversationPhase.CHANNEL_DISCOVERY:
        return channel_mode_quick_replies()

    if phase == ConversationPhase.NEED_DISCOVERY:
        if not needs.categories:
            return need_category_quick_replies()
        from app.core.dialogue import need_discovery_message

        _, replies = need_discovery_message(profile)
        return "请补充期望零售价位或毛利偏好：", with_handoff(replies)

    if phase == ConversationPhase.RECOMMENDATION:
        return post_recommendation_quick_replies()

    if phase == ConversationPhase.PRICE_POLICY:
        return "对价格/政策还有疑问？", with_handoff([
            QuickReply(id="obj_price", label="价格太高", value="objection:price_high"),
            QuickReply(id="obj_comp", label="和别家比价", value="objection:competition"),
            QuickReply(id="obj_policy", label="问代理/大批量", value="objection:policy"),
            QuickReply(id="plan", label="看业务方案", value="show_plan"),
        ])

    if phase == ConversationPhase.BUSINESS_PLAN:
        return "方案是否合适？", with_handoff([
            QuickReply(id="plan_more", label="换一套方案", value="show_plan_alt"),
            QuickReply(id="sample", label="申请样品", value="request_sample"),
        ])

    if phase == ConversationPhase.OBJECTION:
        return "还有其他顾虑吗？", with_handoff([
            QuickReply(id="handoff", label="转销售详聊", value="handoff"),
            QuickReply(id="continue", label="继续选品", value="continue_category"),
        ])

    return None, with_handoff([])
