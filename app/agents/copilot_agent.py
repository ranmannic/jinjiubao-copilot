from __future__ import annotations

import re

from app.config import Settings
from app.core.dialogue import (
    business_plan_message,
    business_plans_message,
    channel_plans_message,
    handoff_message,
    inquiry_city_message,
    inquiry_store_message,
    recommendation_message,
    welcome_message,
)
from app.core.objections import detect_objection, objection_reply
from app.core.free_text import (
    enrich_needs_from_free_text,
    is_meta_question,
    meta_answer,
    missing_field_prompt,
    needs_complete,
)
from app.core.handoff import build_crm_lead, should_handoff
from app.core.nlp_utils import (
    classify_channels,
    classify_customer_type,
    extract_needs_from_text,
    map_quick_reply_to_channel,
    map_quick_reply_to_type,
)
from app.core.profile_merge import (
    apply_llm_profile_updates,
    default_quick_replies,
    default_quick_reply_prompt,
    infer_phase,
)
from app.core.recommender import (
    apply_price_band,
    build_business_plan,
    build_channel_plans,
    price_policy_message,
    recommend_products,
)
from app.services.rag_store import RagStore
from app.integrations.jinjiubao_client import JinjiubaoClient
from app.models.domain import (
    ChannelScene,
    ChatMessage,
    ConversationPhase,
    ConversationSession,
    CopilotResponse,
    CustomerNeeds,
    CustomerProfile,
    CustomerType,
    HandoffPayload,
    QuickReply,
    StoreType,
)
from app.services.llm_service import LLMService


class CopilotAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jjb = JinjiubaoClient(settings)
        self.llm = LLMService(settings)
        self.rag = RagStore()

    async def start_session(
        self,
        customer_id: str,
        token: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        customer = await self.jjb.get_customer(customer_id, token)
        profile = CustomerProfile(
            customer_id=customer_id,
            customer_name=customer.get("name"),
            phone=customer.get("phone"),
            is_returning=bool(customer.get("is_returning")),
            tier=customer.get("tier"),
            region=customer.get("region"),
        )
        if customer.get("region"):
            parts = str(customer["region"]).split("-")
            if len(parts) >= 2:
                profile.needs.region_province = parts[0]
                profile.needs.region_city = parts[1]

        from app.services.session_service import new_session_id

        session = ConversationSession(
            session_id=new_session_id(),
            customer_id=customer_id,
            token=token,
            phase=ConversationPhase.TYPE_IDENTIFICATION,
            profile=profile,
        )

        llm_turn, llm_err = await self.llm.generate_welcome(session)
        if llm_turn and llm_turn.reply:
            msg = llm_turn.reply
            replies = llm_turn.quick_replies or default_quick_replies(session)
        else:
            msg, replies = welcome_message(profile)
            if llm_err:
                msg = f"（AI 对话暂不可用：{llm_err}）\n\n{msg}"

        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies), session

    async def handle_message(
        self,
        session: ConversationSession,
        user_text: str,
        quick_reply_value: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        text = (quick_reply_value or user_text or "").strip()
        display_text = user_text.strip() or text
        session.messages.append(ChatMessage(role="user", content=display_text))

        if session.phase == ConversationPhase.HANDOFF:
            msg = "您已转接销售同事，请保持电话畅通。如需新的选品咨询，请刷新页面重新开始。"
            session.messages.append(ChatMessage(role="assistant", content=msg))
            return self._response(session, msg, []), session

        explicit_handoff = text in {"handoff", "转人工", "让销售联系我", "转销售"} or "让销售" in text

        if text == "show_plan" and session.recommendations:
            return await self._show_plan(session)

        if text == "show_plan_alt" and session.business_plans:
            idx = int(session.metadata.get("plan_index", 0)) + 1
            session.metadata["plan_index"] = idx % len(session.business_plans)
            return await self._show_plan(session, plan_index=session.metadata["plan_index"])

        if text == "show_price_policy" and session.recommendations:
            return await self._show_price_policy(session)

        if text == "raise_objection" or text.startswith("objection:"):
            kind = text.split(":", 1)[1] if ":" in text else detect_objection(display_text) or "price_high"
            return await self._handle_objection(session, kind)

        if text == "request_sample":
            handoff = HandoffPayload(required=True, reason="客户申请样品", intent_score=72)
            return await self._do_handoff(session, handoff)

        if text == "add_cart" and session.recommendations:
            sku = session.recommendations[0].sku_id
            await self.jjb.add_to_cart(session.customer_id, sku)
            msg = f"已将「{session.recommendations[0].name}」加入进货单。如需谈价格或发货，可让销售联系您。"
            replies = default_quick_replies(session)
            session.messages.append(ChatMessage(role="assistant", content=msg))
            return self._response(session, msg, replies), session

        if text == "continue_category":
            session.phase = ConversationPhase.NEED_DISCOVERY
            session.recommendations = []
            session.business_plan = None

        await self._update_profile_from_input(session, text, quick_reply_value)
        enrich_needs_from_free_text(display_text, session.profile.needs)

        obj = detect_objection(display_text)
        if obj and session.recommendations and session.phase in {
            ConversationPhase.RECOMMENDATION,
            ConversationPhase.PRICE_POLICY,
        }:
            return await self._handle_objection(session, obj)

        handoff_check = should_handoff(
            session.profile,
            text,
            session.phase,
            threshold=self.settings.handoff_intent_threshold,
            explicit=explicit_handoff,
        )
        if handoff_check.required:
            return await self._do_handoff(session, handoff_check)

        # --- LLM 主路径：自由对话 + 引回主线 ---
        llm_turn, llm_err = await self.llm.generate_turn(session, display_text, quick_reply_value)
        if llm_turn:
            apply_llm_profile_updates(session.profile, llm_turn.profile_updates)
            enrich_needs_from_free_text(display_text, session.profile.needs)
            session.phase = infer_phase(session)

            if "handoff" in llm_turn.actions or llm_turn.handoff_reason:
                handoff = HandoffPayload(
                    required=True,
                    reason=llm_turn.handoff_reason or "AI 判断需销售跟进",
                    intent_score=80,
                )
                return await self._do_handoff(session, handoff, intro=llm_turn.reply)

            if "show_plan" in llm_turn.actions and session.recommendations:
                return await self._show_plan(session, intro=llm_turn.reply)

            if "recommend" in llm_turn.actions and needs_complete(session.profile.needs):
                return await self._recommend(session, intro=llm_turn.reply)

            if needs_complete(session.profile.needs) and not session.recommendations:
                return await self._recommend(session, intro=llm_turn.reply)

            replies = llm_turn.quick_replies or default_quick_replies(session)
            session.messages.append(ChatMessage(role="assistant", content=llm_turn.reply))
            return self._response(session, llm_turn.reply, replies), session

        fallback = await self._smart_fallback(session, display_text, llm_err)
        if fallback:
            return fallback

        return await self._handle_rule_based(session, text, quick_reply_value, llm_error=llm_err)

    async def _smart_fallback(
        self,
        session: ConversationSession,
        display_text: str,
        llm_error: str | None,
    ) -> tuple[CopilotResponse, ConversationSession] | None:
        """LLM 不可用时的智能兜底：回答元问题、解析自然语言、单次追问。"""
        prefix = f"（AI 对话暂不可用：{llm_error}）\n\n" if llm_error else ""

        if is_meta_question(display_text):
            msg = prefix + meta_answer()
            if needs_complete(session.profile.needs) and not session.recommendations:
                return await self._recommend(session, intro=msg)
            follow = missing_field_prompt(session.profile)
            if follow:
                msg = f"{msg}\n\n{follow}"
            replies = default_quick_replies(session)
            session.messages.append(ChatMessage(role="assistant", content=msg))
            return self._response(session, msg, replies, llm_error=llm_error), session

        if needs_complete(session.profile.needs):
            intro = prefix + "根据您描述的需求，我先帮您筛几款候选："
            return await self._recommend(session, intro=intro.strip())

        if len(display_text.strip()) >= 8:
            needs = session.profile.needs
            ack_bits: list[str] = []
            if needs.categories:
                ack_bits.append("、".join(needs.categories))
            if needs.retail_price_max is not None:
                ack_bits.append(f"零售约 {needs.retail_price_max:.0f} 元以内")
            elif needs.retail_price_min is not None:
                ack_bits.append(f"零售约 {needs.retail_price_min:.0f} 元起")
            if needs.differentiation:
                ack_bits.append("要当地差异化")
            ack = f"收到，您想找{'，'.join(ack_bits)}。" if ack_bits else "收到您的需求。"
            follow = missing_field_prompt(session.profile)
            if follow:
                msg = prefix + ack + follow
                replies = default_quick_replies(session)
                session.phase = infer_phase(session)
                session.messages.append(ChatMessage(role="assistant", content=msg))
                return self._response(session, msg, replies, llm_error=llm_error), session

        return None

    async def _handle_rule_based(
        self,
        session: ConversationSession,
        text: str,
        quick_reply_value: str | None,
        llm_error: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        if text == "custom_need":
            msg = "请直接输入您的需求：品类、渠道、期望零售价位等。"
            session.messages.append(ChatMessage(role="assistant", content=msg))
            return self._response(session, msg, []), session

        price_updated = bool(
            quick_reply_value
            and (quick_reply_value.startswith("retail_") or quick_reply_value in {"margin_high", "local_unique"})
        )
        phase = session.phase

        if phase == ConversationPhase.RECOMMENDATION and price_updated:
            return await self._recommend(session, refreshed=True)

        if phase == ConversationPhase.TYPE_IDENTIFICATION:
            if session.profile.customer_type != CustomerType.UNKNOWN:
                session.phase = (
                    ConversationPhase.INQUIRY
                    if not session.profile.is_returning
                    else ConversationPhase.CHANNEL_DISCOVERY
                )
                if session.phase == ConversationPhase.INQUIRY:
                    msg = inquiry_city_message()
                    replies = default_quick_replies(session)
                else:
                    return await self._after_channel_set(session, llm_error)
            else:
                msg, replies = welcome_message(session.profile)
        elif phase == ConversationPhase.INQUIRY:
            if not session.profile.needs.region_city:
                msg = inquiry_city_message()
                replies = default_quick_replies(session)
            elif session.profile.has_store is None:
                msg = inquiry_store_message()
                replies = default_quick_replies(session)
            else:
                session.phase = ConversationPhase.CHANNEL_DISCOVERY
                return await self._after_channel_set(session, llm_error)
        elif phase == ConversationPhase.CHANNEL_DISCOVERY:
            if session.profile.channels or session.profile.channel_mode:
                return await self._after_channel_set(session, llm_error)
            from app.core.quick_replies import channel_mode_quick_replies

            prompt, replies = channel_mode_quick_replies()
            msg = prompt
        elif phase == ConversationPhase.NEED_DISCOVERY:
            if needs_complete(session.profile.needs):
                return await self._recommend(session)
            from app.core.dialogue import need_discovery_message

            msg, replies = need_discovery_message(session.profile)
        elif phase == ConversationPhase.RECOMMENDATION:
            return await self._recommend(session, refreshed=price_updated)
        elif phase == ConversationPhase.PRICE_POLICY and session.recommendations:
            return await self._show_price_policy(session)
        elif phase == ConversationPhase.BUSINESS_PLAN and session.business_plan:
            msg, replies = business_plan_message(session.business_plan)
        else:
            msg, replies = welcome_message(session.profile)
            session.phase = ConversationPhase.TYPE_IDENTIFICATION

        if llm_error:
            msg = f"（AI 对话暂不可用：{llm_error}）\n\n{msg}"

        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies, llm_error=llm_error), session

    async def _update_profile_from_input(
        self,
        session: ConversationSession,
        text: str,
        quick_reply_value: str | None,
    ) -> None:
        profile = session.profile
        qr = quick_reply_value or text

        if qr.startswith("city:"):
            city = qr.split(":", 1)[1]
            if city != "custom":
                profile.needs.region_city = city
                if "-" in (profile.region or ""):
                    profile.needs.region_province = profile.region.split("-")[0]
            return

        if qr.startswith("store:"):
            st = qr.split(":", 1)[1]
            if st == "none":
                profile.has_store = False
                profile.store_type = StoreType.NONE
            else:
                profile.has_store = True
                mapping = {
                    "premium_wine_shop": StoreType.PREMIUM_WINE_SHOP,
                    "retail_convenience": StoreType.RETAIL_CONVENIENCE,
                    "club": StoreType.CLUB,
                    "restaurant_bar": StoreType.RESTAURANT_BAR,
                    "supermarket": StoreType.SUPERMARKET,
                    "other": StoreType.OTHER,
                }
                profile.store_type = mapping.get(st, StoreType.OTHER)
            return

        if qr == "channel_wholesale":
            profile.channel_mode = "wholesale"
            return

        if qr.startswith("channel_") or qr in {"group_purchase", "retail", "banquet", "mixed", "online_distribution"}:
            ch_map = {
                "channel_wholesale": "wholesale",
                "group_purchase": "group",
                "retail": "retail",
                "banquet": "banquet",
                "online_distribution": "online",
                "mixed": "mixed",
            }
            if qr in ch_map:
                profile.channel_mode = ch_map[qr]
            mapped_channel = map_quick_reply_to_channel(qr.replace("channel_", "") if qr.startswith("channel_") else qr)
            if mapped_channel and mapped_channel not in profile.channels:
                profile.channels.append(mapped_channel)
            return

        mapped_type = map_quick_reply_to_type(qr)
        if mapped_type:
            profile.customer_type = mapped_type
            profile.customer_type_confidence = 0.95

        mapped_channel = map_quick_reply_to_channel(qr)
        if mapped_channel and mapped_channel not in profile.channels:
            profile.channels.append(mapped_channel)

        if not mapped_type:
            ctype, conf = classify_customer_type(text)
            if ctype != CustomerType.UNKNOWN and conf > profile.customer_type_confidence:
                profile.customer_type = ctype
                profile.customer_type_confidence = conf

        skip_channel_nlp = bool(quick_reply_value and map_quick_reply_to_channel(quick_reply_value))
        for ch in classify_channels(text, from_quick_reply=skip_channel_nlp):
            if ch not in profile.channels:
                profile.channels.append(ch)

        extracted = extract_needs_from_text(text)
        needs = profile.needs
        for cat in extracted.get("categories", []):
            if cat not in needs.categories:
                needs.categories.append(cat)
        for t in extracted.get("taste_preferences", []):
            if t not in needs.taste_preferences:
                needs.taste_preferences.append(t)
        for d in extracted.get("differentiation", []):
            if d not in needs.differentiation:
                needs.differentiation.append(d)
        if extracted.get("margin_priority"):
            needs.margin_priority = str(extracted["margin_priority"])
        if extracted.get("order_intent"):
            needs.order_intent = str(extracted["order_intent"])

        if qr.startswith("retail_") or qr in {"margin_high", "local_unique"}:
            profile.needs = apply_price_band(needs, qr)

        self._parse_price_text(text, needs)

    def _parse_price_text(self, text: str, needs: CustomerNeeds) -> None:
        retail = re.findall(r"零售\s*(\d+)\s*[-~到]\s*(\d+)", text)
        if retail:
            needs.retail_price_min = float(retail[0][0])
            needs.retail_price_max = float(retail[0][1])
        band = re.findall(r"(\d+)\s*[-~到]\s*(\d+)\s*元", text)
        if band and not needs.retail_price_min:
            needs.retail_price_min = float(band[0][0])
            needs.retail_price_max = float(band[0][1])
        supply = re.findall(r"供货\s*(\d+)", text)
        if supply:
            needs.supply_price_max = float(supply[0])

    async def _recommend(
        self,
        session: ConversationSession,
        intro: str | None = None,
        refreshed: bool = False,
    ) -> tuple[CopilotResponse, ConversationSession]:
        profile = session.profile
        category = profile.needs.categories[0] if profile.needs.categories else None
        products = await self.jjb.list_products(profile.customer_id, category=category, region=profile.region)
        sku_ids = [p["sku_id"] for p in products]
        city = profile.needs.region_city or (profile.region.split("-")[-1] if profile.region else None)
        competition = await self.jjb.get_region_competition(sku_ids, city)
        recs = recommend_products(products, profile, competition, limit=3, include_ineligible=True)
        session.recommendations = recs
        top = next((r for r in recs if r.eligible), recs[0] if recs else None)
        session.business_plans = build_channel_plans(profile, top)
        session.business_plan = session.business_plans[0] if session.business_plans else None
        session.phase = ConversationPhase.RECOMMENDATION

        if intro:
            rec_part, replies = recommendation_message(profile, recs)
            msg = f"{intro}\n\n{rec_part}"
        else:
            msg, replies = recommendation_message(profile, recs)
            if refreshed and profile.needs.retail_price_min:
                msg = (
                    f"已按零售价位 ¥{profile.needs.retail_price_min:.0f}-"
                    f"¥{profile.needs.retail_price_max:.0f} 重新筛选：\n\n{msg}"
                )

        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies, recommendations=recs), session

    async def _after_channel_set(
        self,
        session: ConversationSession,
        llm_error: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        top = session.recommendations[0] if session.recommendations else None
        session.business_plans = build_channel_plans(session.profile, top)
        session.business_plan = session.business_plans[0] if session.business_plans else None
        plans_msg = channel_plans_message(session.business_plans)
        session.phase = ConversationPhase.NEED_DISCOVERY
        msg = plans_msg
        if llm_error:
            msg = f"（AI 对话暂不可用：{llm_error}）\n\n{msg}"
        replies = default_quick_replies(session)
        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies, llm_error=llm_error), session

    async def _show_price_policy(
        self,
        session: ConversationSession,
        intro: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        msg = price_policy_message(session.recommendations)
        if intro:
            msg = f"{intro}\n\n{msg}"
        session.phase = ConversationPhase.PRICE_POLICY
        replies = default_quick_replies(session)
        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies), session

    async def _handle_objection(
        self,
        session: ConversationSession,
        kind: str,
    ) -> tuple[CopilotResponse, ConversationSession]:
        top = session.recommendations[0] if session.recommendations else None
        msg = objection_reply(kind, top.name if top else None)
        if kind == "policy":
            handoff = HandoffPayload(required=True, reason="客户咨询代理/大批量政策", intent_score=85)
            return await self._do_handoff(session, handoff, intro=msg)
        session.phase = ConversationPhase.OBJECTION
        replies = default_quick_replies(session)
        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies), session

    async def _show_plan(
        self,
        session: ConversationSession,
        intro: str | None = None,
        plan_index: int = 0,
    ) -> tuple[CopilotResponse, ConversationSession]:
        if session.business_plans:
            idx = plan_index % len(session.business_plans)
            session.business_plan = session.business_plans[idx]
        else:
            top = session.recommendations[0] if session.recommendations else None
            session.business_plan = build_business_plan(session.profile, top)
        session.phase = ConversationPhase.BUSINESS_PLAN
        if intro and len(session.business_plans) > 1:
            msg = f"{intro}\n\n{business_plans_message(session.business_plans)}"
            replies = default_quick_replies(session)
        else:
            plan_msg, replies = business_plan_message(session.business_plan)
            msg = f"{intro}\n\n{plan_msg}" if intro else plan_msg
        session.messages.append(ChatMessage(role="assistant", content=msg))
        return self._response(session, msg, replies), session

    async def _do_handoff(
        self,
        session: ConversationSession,
        handoff: HandoffPayload,
        intro: str | None = None,
    ) -> tuple[CopilotResponse, ConversationSession]:
        lead = build_crm_lead(session.profile, handoff, session.session_id)
        if session.recommendations:
            lead["recommended_skus"] = [r.sku_id for r in session.recommendations]
        assign = await self.jjb.assign_sales(lead)
        await self.jjb.create_lead(lead)
        await self.jjb.notify_sales(
            assign.get("sales_id", "S001"),
            title="Copilot 客户待跟进",
            body=handoff.reason or "客户申请转人工",
            lead=lead,
        )
        handoff.assigned_sales_id = assign.get("sales_id")
        handoff.assigned_sales_name = assign.get("sales_name")
        handoff.callback_sla_minutes = self.settings.sales_callback_sla_minutes
        session.handoff = handoff
        session.phase = ConversationPhase.HANDOFF
        tail = handoff_message(session.profile, handoff.reason or "客户深度沟通", handoff.assigned_sales_name)
        msg = f"{intro}\n\n{tail}" if intro else tail
        session.messages.append(ChatMessage(role="assistant", content=msg))
        return CopilotResponse(
            session_id=session.session_id,
            phase=session.phase,
            message=msg,
            quick_replies=[],
            quick_reply_prompt=None,
            profile=session.profile,
            recommendations=session.recommendations,
            business_plan=session.business_plan,
            business_plans=session.business_plans,
            handoff=handoff,
            actions=[{"type": "handoff", "value": "completed"}],
        ), session

    def _response(
        self,
        session: ConversationSession,
        message: str,
        quick_replies: list[QuickReply],
        recommendations: list | None = None,
        llm_error: str | None = None,
    ) -> CopilotResponse:
        meta: dict = {"llm_enabled": self.llm.enabled}
        err = llm_error or self.llm.last_error
        if err:
            meta["llm_error"] = err
            meta["llm_status"] = "error"
        elif self.llm.enabled:
            meta["llm_status"] = "ok"
        else:
            meta["llm_status"] = "disabled"
        rag_hits = self.rag.search(message[:80] or "批发", limit=2)
        if rag_hits:
            meta["rag_refs"] = [{"title": h.get("title"), "collection": h.get("_collection")} for h in rag_hits]
        return CopilotResponse(
            session_id=session.session_id,
            phase=session.phase,
            message=message,
            quick_replies=quick_replies,
            quick_reply_prompt=default_quick_reply_prompt(session),
            profile=session.profile,
            recommendations=recommendations or session.recommendations,
            business_plan=session.business_plan,
            business_plans=session.business_plans,
            handoff=session.handoff if session.handoff.required else None,
            actions=[{"type": "phase", "value": session.phase.value}],
            metadata=meta,
        )
