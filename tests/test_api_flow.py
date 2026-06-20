from fastapi.testclient import TestClient

from app.main import create_app


def test_full_conversation_flow():
    client = TestClient(create_app())

    start = client.post("/api/v1/copilot/sessions/start", json={"customer_id": "cust_demo_001"})
    assert start.status_code == 200
    data = start.json()
    session_id = data["session_id"]
    assert data["phase"] == "type_identification"

    r1 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "premium_wine_shop"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "group_purchase"},
    )
    assert r2.status_code == 200

    r3 = client.post(
        "/api/v1/copilot/chat",
        json={
            "session_id": session_id,
            "message": "团购关系客户，想找利润型白葡萄酒，口感好、供货便宜、零售定价高、当地不透明",
            "quick_reply_value": "白葡萄酒 团购 口感好 零售定价高 当地差异化",
        },
    )
    assert r3.status_code == 200

    r4 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "retail_80_120"},
    )
    assert r4.status_code == 200
    body = r4.json()
    assert body.get("recommendations") or body["phase"] in {"recommendation", "need_discovery"}

    r5 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "大批量100箱，让销售联系我"},
    )
    assert r5.status_code == 200
    final = r5.json()
    if final["phase"] == "handoff":
        assert final["handoff"]["required"] is True
