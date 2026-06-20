from app.core.handoff import should_handoff
from app.models.domain import ConversationPhase, CustomerNeeds, CustomerProfile, CustomerType


def test_handoff_on_bulk_request():
    profile = CustomerProfile(customer_id="c1", needs=CustomerNeeds(order_intent="bulk"))
    result = should_handoff(profile, "我要100箱", ConversationPhase.RECOMMENDATION, threshold=70)
    assert result.required is True
    assert result.intent_score >= 70


def test_handoff_on_explicit():
    profile = CustomerProfile(customer_id="c1")
    result = should_handoff(profile, "handoff", ConversationPhase.NEED_DISCOVERY, explicit=True)
    assert result.required is True
