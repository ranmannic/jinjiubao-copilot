from app.core.nlp_utils import classify_channels, extract_categories, extract_needs_from_text
from app.models.domain import ChannelScene, CustomerNeeds


def test_retail_pricing_does_not_add_retail_channel():
    text = "白葡萄酒 团购 口感好 零售定价高 当地差异化"
    channels = classify_channels(text)
    assert ChannelScene.RETAIL not in channels


def test_white_wine_not_classified_as_baijiu():
    cats = extract_categories("想找利润型白葡萄酒")
    assert "白葡萄酒" in cats
    assert "国产白酒" not in cats


def test_need_preset_does_not_false_complete_without_price():
    extracted = extract_needs_from_text("白葡萄酒 团购 口感好 零售定价高 当地差异化")
    needs = CustomerNeeds(
        categories=extracted["categories"],
        taste_preferences=extracted["taste_preferences"],
        differentiation=extracted["differentiation"],
    )
    has_price = needs.retail_price_min is not None
    has_margin = needs.margin_priority == "高"
    assert not (needs.categories and (has_price or has_margin))
