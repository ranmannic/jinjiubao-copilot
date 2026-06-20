from __future__ import annotations

"""带提示文案的快捷交互栏，始终保留转人工入口。"""

from app.core.cities import CITY_OPTIONS
from app.core.need_steps import need_step_prompt_and_replies
from app.models.domain import (
    ConversationPhase,
    ConversationSession,
    QuickReply,
)


from app.core.quick_reply_utils import with_handoff


def identity_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "请告诉我您的身份（也可文字补充）："
    replies = [
        QuickReply(id="t_premium", label="高端烟酒店", value="premium_wine_shop"),
        QuickReply(id="t_dealer", label="经销/批发商", value="dealer"),
        QuickReply(id="t_retail", label="烟酒便利店", value="retail_convenience"),
        QuickReply(id="t_corporate", label="企业团购", value="corporate_gift"),
        QuickReply(id="t_online", label="线上电商", value="online_ecommerce"),
        QuickReply(id="t_restaurant", label="餐厅酒吧", value="restaurant"),
        QuickReply(id="t_personal", label="自己用酒", value="personal_use"),
    ]
    return prompt, with_handoff(replies)


def inquiry_city_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "了解。请告诉我您的经营所在城市（点选或输入）："
    replies = [
        QuickReply(id=f"city_{i}", label=c, value=f"city:{c}", reply_type="city")
        for i, c in enumerate(CITY_OPTIONS[:12])
    ]
    replies.append(QuickReply(id="city_more", label="更多城市…", value="city:custom", reply_type="city"))
    return prompt, with_handoff(replies, max_items=9)


def returning_need_quick_replies() -> tuple[str, list[QuickReply]]:
    prompt = "欢迎回来！您这次想找什么产品？可直接描述品类、价位、口感等："
    return prompt, with_handoff([
        QuickReply(id="n_desc", label="我来说说需求", value="custom_need"),
        QuickReply(id="n_white", label="白葡萄酒", value="need_cat:白葡萄酒"),
        QuickReply(id="n_red", label="红葡萄酒", value="need_cat:红葡萄酒"),
        QuickReply(id="n_baijiu", label="国产白酒", value="need_cat:国产白酒"),
    ])


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
        if profile.is_returning:
            return returning_need_quick_replies()
        return identity_quick_replies()

    if phase == ConversationPhase.INQUIRY:
        if not needs.region_city:
            return inquiry_city_quick_replies()
        return need_step_prompt_and_replies(profile, session.metadata)

    if phase == ConversationPhase.NEED_DISCOVERY:
        return need_step_prompt_and_replies(profile, session.metadata)

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
            QuickReply(id="continue", label="继续选品", value="continue_category"),
        ])

    return None, with_handoff([])
