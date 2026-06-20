from fastapi.testclient import TestClient

from app.main import create_app


def test_full_conversation_flow():
    client = TestClient(create_app())
    customer_id = "cust_pytest_new_flow"

    start = client.post("/api/v1/copilot/sessions/start", json={"customer_id": customer_id})
    assert start.status_code == 200
    data = start.json()
    session_id = data["session_id"]
    assert data["phase"] in {"type_identification", "need_discovery"}
    assert "初次见面" in data["message"] or data["phase"] == "type_identification"

    r1 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "premium_wine_shop"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "city:杭州市"},
    )
    assert r2.status_code == 200

    r3 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "need_cat:白葡萄酒"},
    )
    assert r3.status_code == 200

    r4 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "need_taste:口感好"},
    )
    assert r4.status_code == 200

    r5 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "", "quick_reply_value": "retail_80_120"},
    )
    assert r5.status_code == 200
    body = r5.json()
    assert body.get("recommendations") or body["phase"] in {"recommendation", "need_discovery"}

    r6 = client.post(
        "/api/v1/copilot/chat",
        json={"session_id": session_id, "message": "大批量100箱，让销售联系我"},
    )
    assert r6.status_code == 200
    final = r6.json()
    if final["phase"] == "handoff":
        assert final["handoff"]["required"] is True


def test_returning_customer_skips_onboarding():
    client = TestClient(create_app())
    cid = "cust_pytest_returning"
    client.post("/api/v1/copilot/sessions/start", json={"customer_id": cid})
    second = client.post("/api/v1/copilot/sessions/start", json={"customer_id": cid}).json()
    assert second["phase"] == "need_discovery"
    assert "欢迎回来" in second["message"]


def test_history_list():
    client = TestClient(create_app())
    cid = "cust_pytest_history"
    start = client.post("/api/v1/copilot/sessions/start", json={"customer_id": cid}).json()
    client.post(
        "/api/v1/copilot/chat",
        json={"session_id": start["session_id"], "message": "你好", "quick_reply_value": None},
    )
    hist = client.get(f"/api/v1/copilot/customers/{cid}/history")
    assert hist.status_code == 200
    assert len(hist.json().get("sessions", [])) >= 1
