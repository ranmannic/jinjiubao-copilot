from app.core.recommender import recommend_products
from app.models.domain import ChannelScene, CustomerNeeds, CustomerProfile, CustomerType


def test_recommend_white_wine_group_purchase():
    profile = CustomerProfile(
        customer_id="c1",
        customer_type=CustomerType.PREMIUM_WINE_SHOP,
        channels=[ChannelScene.GROUP_PURCHASE],
        needs=CustomerNeeds(
            categories=["白葡萄酒"],
            taste_preferences=["口感好", "零售定价高"],
            differentiation=["当地差异化"],
            margin_priority="高",
            retail_price_min=80,
            retail_price_max=150,
        ),
    )
    products = [
        {
            "sku_id": "JJ-LQ-001",
            "name": "洛齐雷司令半甜白",
            "brand": "洛齐",
            "category": "白葡萄酒",
            "supply_price": 38,
            "retail_min": 68,
            "retail_max": 88,
            "tags": ["易推销", "高周转"],
            "strategic_weight": 5,
        },
        {
            "sku_id": "JJ-JC-S100",
            "name": "金锤 S100 干白",
            "brand": "金锤",
            "category": "白葡萄酒",
            "supply_price": 72,
            "retail_min": 128,
            "retail_max": 168,
            "tags": ["品牌势能", "礼盒"],
            "strategic_weight": 8,
        },
    ]
    recs, blocked = recommend_products(products, profile, {"JJ-LQ-001": 1, "JJ-JC-S100": 2})
    assert len(recs) >= 1
    assert recs[0].category == "白葡萄酒"
    assert all(r.eligible for r in recs)
