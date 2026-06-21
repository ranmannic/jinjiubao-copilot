from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def _strip_thinking(text: str) -> str:
    lowered = text.lower()
    idx = 0
    while True:
        start = lowered.find("<think", idx)
        if start < 0:
            break
        close = lowered.find(">", start)
        if close < 0:
            break
        tag = lowered[start + 1 : close].strip()
        end_tag = f"</{tag}>"
        end = lowered.find(end_tag, close)
        if end < 0:
            break
        text = text[:start] + text[end + len(end_tag) :]
        lowered = text.lower()
        idx = start
    return text.strip()


def _extract_json_blob(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _fallback_from_raw(raw: str) -> dict:
    reply_m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
    if reply_m:
        reply = reply_m.group(1).replace("\\n", "\n").replace('\\"', '"')
        return {"reply": reply, "profile_updates": {}, "actions": []}
    cleaned = _strip_thinking(raw)
    if cleaned and not cleaned.lstrip().startswith("{"):
        return {"reply": cleaned[:800], "profile_updates": {}, "actions": []}
    return {"reply": "好的，请继续说说您的需求。", "profile_updates": {}, "actions": []}


def parse_llm_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON，兼容 markdown 包裹、尾逗号、thinking 前缀等。"""
    if not raw or not str(raw).strip():
        return {"reply": "好的，请继续说说您的需求。", "profile_updates": {}, "actions": []}

    text = _strip_thinking(str(raw).strip())
    blob = _extract_json_blob(text)

    try:
        data = json.loads(blob)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        logger.warning("LLM JSON parse failed: %s | snippet=%r", exc, blob[:240])

    return _fallback_from_raw(raw)
