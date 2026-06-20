from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from app.config import Settings
from app.core.llm_config import model_error_hint, probe_candidates
from app.models.domain import ConversationSession, QuickReply

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是进酒宝 AI 酒商选品顾问「小进」，像资深业务员一样与客户自然交流。

## 主线任务（按顺序推进，但不要机械问卷）
1. 了解业态（经销商/高端烟酒店/便利店/餐厅/会所/企业团购/进口商）
2. 了解渠道（团购关系、门店零售、宴席、餐饮配酒等）
3. 了解选品需求（品类、口感、毛利、差异化、零售价位）
4. 信息充分时推品（由系统生成具体 SKU，你不要编造产品名和价格）
5. 推卖货方案、必要时转销售电话对接

## 交流原则
- **必须**自然回应客户的任何输入：闲聊、追问、比价、顾虑、行业吐槽、身份询问都可以接
- 客户问「你是哪家AI/什么模型」时，如实回答：进酒宝 AI 选品顾问，由 Kimi（Moonshot）大模型驱动
- 每次回复先回应客户刚说的话，再**用 1 句话** gently 引回选品主线
- 每次最多问 1 个问题；**禁止**一次要求同时补充品类+零售价+供货价
- 客户已给出详细需求（如价位、产区、包装、口感）时，不要重复追问已有信息
- **禁止**编造 SKU、供货价、库存；具体推品由系统完成
- 客户问独家价、大批量、账期、样品、议价时，action 设 handoff
- 业态/渠道/需求已基本清楚时，action 设 recommend

## 输出格式
严格返回 JSON（不要 markdown 代码块）：
{
  "reply": "给客户看的自然语言回复",
  "profile_updates": {
    "customer_type": "dealer|importer|premium_wine_shop|retail_convenience|restaurant|club_bar|corporate_gift|null",
    "channels": ["group_purchase"],
    "categories": ["白葡萄酒"],
    "taste_preferences": ["口感好"],
    "differentiation": ["当地差异化"],
    "retail_price_min": null,
    "retail_price_max": 20,
    "margin_priority": "高|null",
    "region_city": null,
    "order_intent": null,
    "notes": "法国AOP、勃艮第瓶型、传统包装"
  },
  "actions": [],
  "handoff_reason": null,
  "quick_replies": [{"label":"显示文字","value":"发送值"}]
}

actions 可选：recommend、show_plan、handoff
quick_replies 最多 4 个，可选。"""


class LLMTurnResult:
    def __init__(
        self,
        reply: str,
        profile_updates: Optional[Dict[str, Any]] = None,
        actions: Optional[List[str]] = None,
        handoff_reason: Optional[str] = None,
        quick_replies: Optional[List[QuickReply]] = None,
    ):
        self.reply = reply
        self.profile_updates = profile_updates or {}
        self.actions = actions or []
        self.handoff_reason = handoff_reason
        self.quick_replies = quick_replies or []


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.llm_api_key) and settings.llm_enabled
        self.last_error: Optional[str] = None
        self.resolve_note: Optional[str] = None
        self.auth_ok = False
        self._client = None
        self._resolved = False
        if self.enabled:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
            except ImportError:
                logger.warning("openai package not installed; run: pip install openai")
                self.enabled = False
                self.last_error = "未安装 openai 包"

    def _make_client(self, base_url: str):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.settings.llm_api_key, base_url=base_url)

    def _apply_endpoint(self, base_url: str, model: str, note: str | None = None) -> None:
        base_url = base_url.rstrip("/")
        if self.settings.llm_base_url != base_url or self.settings.llm_model != model:
            logger.info("LLM endpoint resolved: model=%s base=%s", model, base_url)
        self.settings.llm_base_url = base_url
        self.settings.llm_model = model
        self._client = self._make_client(base_url)
        if note:
            self.resolve_note = note
            if note not in self.settings.llm_config_notes:
                self.settings.llm_config_notes.append(note)

    def _friendly_error(self, exc: Exception, base: str | None = None, model: str | None = None) -> str:
        msg = str(exc)
        lower = msg.lower()
        model = model or self.settings.llm_model
        base = base or self.settings.llm_base_url

        if isinstance(exc, RateLimitError) or "429" in msg or "insufficient balance" in lower:
            return "Kimi/Moonshot 账户余额不足或配额用尽，请登录 platform.moonshot.cn 充值后再试"

        if isinstance(exc, AuthenticationError) or "401" in msg:
            if "moonshot.ai" in base:
                return (
                    "API Key 无法用于 api.moonshot.ai（国内 Key 仅支持 api.moonshot.cn）。"
                    "请将 .env 改为 LLM_BASE_URL=https://api.moonshot.cn/v1、"
                    "LLM_MODEL=moonshot-v1-8k；或使用 platform.kimi.ai 国际版 Key 调用 kimi-k2.6"
                )
            return "LLM API Key 无效或已过期，请到 platform.moonshot.cn 控制台检查密钥"

        model_not_found = (
            isinstance(exc, NotFoundError)
            or "does not exist" in lower
            or "unknown model" in lower
            or ("model" in lower and "not found" in lower)
        )
        if model_not_found:
            return f"模型名称无效（当前：{model}，端点：{base}）{model_error_hint(model, base)}"

        if isinstance(exc, BadRequestError) and "model" in lower:
            return f"模型或参数错误（model={model}，端点：{base}）{model_error_hint(model, base)}"

        if isinstance(exc, APIConnectionError):
            return f"无法连接 LLM 服务（{base}），请检查网络和 LLM_BASE_URL"

        return f"LLM 调用失败：{msg[:160]}"

    async def resolve_connection(self, force: bool = False) -> tuple[bool, str | None]:
        """探测国内/国际端点，自动选用与 Key 匹配的配置。"""
        if not self.enabled:
            return False, self.last_error or "LLM 未配置"
        if self._resolved and not force:
            return self.auth_ok and not self.last_error, self.last_error

        candidates = probe_candidates(self.settings.llm_base_url, self.settings.llm_model)
        last_err: str | None = None
        balance_err: str | None = None
        balance_pair: tuple[str, str] | None = None

        for base, model in candidates:
            client = self._make_client(base)
            try:
                await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    temperature=0,
                )
                note = None
                if (base, model) != (
                    self.settings.llm_base_url.rstrip("/"),
                    self.settings.llm_model,
                ):
                    note = f"已自动匹配 Key：{model} @ {base}"
                self._apply_endpoint(base, model, note)
                self.last_error = None
                self.auth_ok = True
                self._resolved = True
                return True, None
            except RateLimitError as exc:
                balance_err = self._friendly_error(exc, base, model)
                balance_pair = (base, model)
                last_err = balance_err
                continue
            except (AuthenticationError, NotFoundError, BadRequestError) as exc:
                last_err = self._friendly_error(exc, base, model)
                continue
            except Exception as exc:
                last_err = self._friendly_error(exc, base, model)
                continue

        if balance_pair:
            base, model = balance_pair
            note = f"Key 有效但余额不足，已匹配 {model} @ {base}"
            self._apply_endpoint(base, model, note)
            self.last_error = balance_err
            self.auth_ok = True
            self._resolved = True
            return False, balance_err

        self.last_error = last_err or "无法连接任何 Moonshot 端点，请检查 LLM_API_KEY"
        self.auth_ok = False
        self._resolved = True
        return False, self.last_error

    def _history_messages(self, session: ConversationSession, limit: int = 12) -> List[dict]:
        msgs = session.messages[-limit:]
        return [
            {"role": "assistant" if m.role == "assistant" else "user", "content": m.content}
            for m in msgs
        ]

    def _context_block(self, session: ConversationSession) -> str:
        profile = session.profile
        needs = profile.needs
        missing = []
        if profile.customer_type.value == "unknown":
            missing.append("业态")
        if not profile.channels:
            missing.append("销售渠道")
        if not needs.categories and not needs.notes:
            missing.append("品类/产区")
        if needs.retail_price_min is None and needs.retail_price_max is None and needs.margin_priority != "高":
            missing.append("零售价位")

        return json.dumps(
            {
                "phase": session.phase.value,
                "customer_name": profile.customer_name,
                "region": profile.region,
                "profile": profile.model_dump(),
                "missing_for_recommendation": missing,
                "has_recommendations": bool(session.recommendations),
            },
            ensure_ascii=False,
        )

    async def generate_turn(
        self,
        session: ConversationSession,
        user_text: str,
        quick_reply_value: Optional[str] = None,
    ) -> Tuple[Optional[LLMTurnResult], Optional[str]]:
        if not self.enabled or not self._client:
            return None, self.last_error or "LLM 未配置"

        ok, err = await self.resolve_connection()
        if not ok and err and not self.auth_ok:
            return None, err

        user_block = user_text
        if quick_reply_value and quick_reply_value != user_text:
            user_block = f"[快捷选项:{quick_reply_value}] {user_text}".strip()

        messages: List[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"当前会话上下文：{self._context_block(session)}"},
        ]
        messages.extend(self._history_messages(session))
        if not session.messages or session.messages[-1].role != "user":
            messages.append({"role": "user", "content": user_block})

        try:
            resp = await self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=0.65,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)
            self.last_error = None
            qrs = []
            for item in data.get("quick_replies") or []:
                if item.get("label") and item.get("value"):
                    qrs.append(
                        QuickReply(
                            id=f"llm_{len(qrs)}",
                            label=str(item["label"])[:30],
                            value=str(item["value"])[:200],
                        )
                    )
            return (
                LLMTurnResult(
                    reply=str(data.get("reply") or "好的，请继续说说您的需求。"),
                    profile_updates=data.get("profile_updates") or {},
                    actions=[str(a) for a in (data.get("actions") or [])],
                    handoff_reason=data.get("handoff_reason"),
                    quick_replies=qrs[:4],
                ),
                None,
            )
        except Exception as exc:
            self.last_error = self._friendly_error(exc)
            logger.exception("LLM generate_turn failed: %s", self.last_error)
            return None, self.last_error

    async def probe(self) -> tuple[bool, str | None]:
        ok, err = await self.resolve_connection(force=True)
        return ok, err

    async def generate_welcome(
        self, session: ConversationSession
    ) -> Tuple[Optional[LLMTurnResult], Optional[str]]:
        if not self.enabled or not self._client:
            return None, self.last_error or "LLM 未配置"

        ok, err = await self.resolve_connection()
        if not ok and err and not self.auth_ok:
            return None, err

        name = session.profile.customer_name or "老板"
        prompt = (
            f"客户{name}刚登录进酒宝，{'是老客户回访' if session.profile.is_returning else '是新客户'}。"
            f"请生成简短欢迎语，说明你是进酒宝 AI 选品顾问（Kimi 驱动），可以聊任何选酒问题。"
            f"返回 JSON，actions 为空。"
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            self.last_error = None
            return (
                LLMTurnResult(
                    reply=str(data.get("reply") or ""),
                    profile_updates={},
                    quick_replies=[
                        QuickReply(id="t_premium", label="高端烟酒店", value="premium_wine_shop"),
                        QuickReply(id="t_dealer", label="经销商/批发", value="dealer"),
                        QuickReply(id="t_retail", label="便利店/零售", value="retail_convenience"),
                        QuickReply(id="t_corporate", label="企业团购/礼品", value="corporate_gift"),
                    ],
                ),
                None,
            )
        except Exception as exc:
            self.last_error = self._friendly_error(exc)
            logger.exception("LLM welcome failed")
            return None, self.last_error
