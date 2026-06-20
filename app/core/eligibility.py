from __future__ import annotations

"""产品可推荐性预检：代理、身份、同行、库存等。"""

from app.models.domain import CustomerProfile, CustomerType


def check_product_eligibility(
    product: dict,
    profile: CustomerProfile,
    region_competition: dict[str, int] | None = None,
) -> tuple[bool, str | None]:
    region_competition = region_competition or {}
    sku = product.get("sku_id", "")
    city = profile.needs.region_city or (profile.region or "").split("-")[-1] or "当地"

    if product.get("in_stock") is False or int(product.get("stock_qty", 1)) <= 0:
        return False, "当前无货，暂不可推荐"

    if profile.is_peer or profile.tier == "peer":
        return False, "同行客户不在线报价，请转销售对接"

    exclusive_regions = product.get("exclusive_regions") or []
    if city and city in exclusive_regions:
        return False, f"{city}已有区域代理，该产品不可报价"

    competitors = region_competition.get(sku, 0)
    agent_threshold = int(product.get("max_local_agents", 99))
    if competitors >= agent_threshold and product.get("agent_restricted"):
        return False, f"{city}该 SKU 代理名额已满（已有 {competitors} 家）"

    tier = (profile.tier or "standard").lower()
    min_tier = (product.get("min_customer_tier") or "standard").lower()
    tier_rank = {"trial": 0, "standard": 1, "vip": 2, "dealer": 3}
    if tier_rank.get(tier, 1) < tier_rank.get(min_tier, 1):
        return False, f"您的客户等级（{tier}）仅可查看常规批发价，详细政策请转销售"

    if profile.customer_type == CustomerType.IMPORTER and product.get("importer_only") is False:
        pass  # ok

    return True, None


def regular_wholesale_policy_note() -> str:
    return (
        "以下为**常规批发价及标准政策**（含标准 MOQ、常规物流条款）。"
        "如需了解区域代理、混合批发、大批量订购（≥100件）等特殊政策，"
        "请点击「转人工」由销售经理具体沟通。"
    )
