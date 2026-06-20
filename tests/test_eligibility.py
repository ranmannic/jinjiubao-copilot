from app.core.eligibility import check_product_eligibility
from app.models.domain import CustomerProfile


def test_block_peer_customer():
    profile = CustomerProfile(customer_id="c1", is_peer=True, tier="peer")
    ok, reason = check_product_eligibility({"sku_id": "X", "in_stock": True}, profile)
    assert not ok
    assert "同行" in (reason or "")


def test_block_no_stock():
    profile = CustomerProfile(customer_id="c1")
    ok, reason = check_product_eligibility({"sku_id": "X", "in_stock": False, "stock_qty": 0}, profile)
    assert not ok
