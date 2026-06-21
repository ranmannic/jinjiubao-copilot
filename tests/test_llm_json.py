from app.core.llm_json import parse_llm_json


def test_parse_llm_json_with_markdown_fence():
    raw = '```json\n{"reply": "你好", "actions": []}\n```'
    data = parse_llm_json(raw)
    assert data["reply"] == "你好"


def test_parse_llm_json_trailing_comma():
    raw = '{"reply": "测试", "profile_updates": {},}'
    data = parse_llm_json(raw)
    assert data["reply"] == "测试"


def test_parse_llm_json_fallback_reply_extract():
    raw = '前缀文字 {"reply": "降级回复", "profile_updates": {broken'
    data = parse_llm_json(raw)
    assert "降级回复" in data["reply"]
