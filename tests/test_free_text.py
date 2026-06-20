from app.core.free_text import (
    enrich_needs_from_free_text,
    is_meta_question,
    needs_complete,
)
from app.models.domain import CustomerNeeds, CustomerProfile, CustomerType


def test_meta_question():
    assert is_meta_question("你是哪家AI？")
    assert is_meta_question("什么模型驱动的")
    assert not is_meta_question("我想找白葡萄酒")


def test_enrich_french_aop_under_20():
    needs = CustomerNeeds()
    text = "我想找20以内的法国aop，网上不要有价格或者价格高一点，口感好，包装最好传统一些，勃艮第瓶型"
    enrich_needs_from_free_text(text, needs)
    assert needs.retail_price_max == 20
    assert "葡萄酒" in needs.categories or "白葡萄酒" in needs.categories
    assert "口感好" in needs.taste_preferences
    assert needs_complete(needs)


def test_needs_complete_with_price_max_only():
    needs = CustomerNeeds(categories=["白葡萄酒"], retail_price_max=20.0)
    assert needs_complete(needs)
