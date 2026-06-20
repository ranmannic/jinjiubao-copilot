from __future__ import annotations

from typing import Any

from app.models.domain import CustomerProfile


def _product_attrs_line(p: dict) -> str:
    parts = []
    for key, label in [
        ("origin_country", "产国"),
        ("origin_region", "产区"),
        ("category", "品类"),
        ("grape_variety", "品种"),
        ("bottle_type", "瓶型"),
        ("spec", "规格"),
        ("baijiu_aroma", "香型"),
        ("grade", "等级"),
        ("outer_pack", "外箱"),
        ("retail_band", "零售价位段"),
    ]:
        if p.get(key):
            parts.append(f"{label}:{p[key]}")
    return " · ".join(parts)


def detect_mismatches(product: dict, profile: CustomerProfile) -> list[str]:
    """需求与 SKU 属性不完全匹配时，说明为何仍推荐。"""
    notes: list[str] = []
    needs = profile.needs
    notes_text = (needs.notes or "") + " ".join(needs.categories + needs.taste_preferences)

    if "勃艮第" in notes_text and product.get("bottle_type") and "勃艮第" not in str(product.get("bottle_type")):
        notes.append(f"瓶型为{product.get('bottle_type')}（非勃艮第瓶），但口感/价位更匹配您的描述")
    if "法国" in notes_text and product.get("origin_country") and "法国" not in str(product.get("origin_country")):
        notes.append(f"产国为{product.get('origin_country')}，同价位段内动销与毛利更优")
    if needs.retail_price_max and product.get("retail_max"):
        if float(product["retail_max"]) > needs.retail_price_max * 1.2:
            notes.append("零售价略超目标上限，但供货政策与区域差异化更好")
    if needs.categories and product.get("category"):
        cat = product["category"]
        if not any(c in cat for c in needs.categories):
            notes.append(f"品类为{cat}，作为同场景替代款推荐")
    return notes


def product_detail_line(rec: Any) -> str:
    data = rec.model_dump() if hasattr(rec, "model_dump") else rec
    return _product_attrs_line(data)
