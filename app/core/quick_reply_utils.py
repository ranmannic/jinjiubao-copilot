from __future__ import annotations

from app.models.domain import QuickReply


def handoff_reply() -> QuickReply:
    return QuickReply(
        id="handoff_always",
        label="转人工",
        value="handoff",
        reply_type="handoff",
        style="primary-outline",
    )


def with_handoff(replies: list[QuickReply], max_items: int = 9) -> list[QuickReply]:
    out = [r for r in replies if r.value != "handoff"][:max_items]
    if not any(r.value == "handoff" for r in out):
        out.append(handoff_reply())
    return out
