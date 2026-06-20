from __future__ import annotations

"""产品相册 URL 与 SVG 占位图生成。"""

from html import escape

SKU_THEMES: dict[str, dict[str, str]] = {
    "JJ-LQ-001": {"c1": "#c8e6a0", "c2": "#5a7a2a", "accent": "#f0f9c4"},
    "JJ-JC-S100": {"c1": "#fde68a", "c2": "#92400e", "accent": "#fffbeb"},
    "JJ-WB-001": {"c1": "#fdba74", "c2": "#9a3412", "accent": "#ffedd5"},
    "JJ-GF-001": {"c1": "#fecaca", "c2": "#991b1b", "accent": "#fef2f2"},
    "JJ-LQ-002": {"c1": "#f9a8d4", "c2": "#9d174d", "accent": "#fce7f3"},
    "JJ-JC-G500": {"c1": "#a78bfa", "c2": "#4c1d95", "accent": "#ede9fe"},
}

GALLERY_VIEWS = [
    ("cover", "产品主图"),
    ("label", "瓶标细节"),
    ("pack", "外箱包装"),
    ("scene", "陈列场景"),
]

DEFAULT_THEME = {"c1": "#67e8f9", "c2": "#0e7490", "accent": "#ecfeff"}


def product_gallery(sku_id: str, name: str) -> tuple[str, list[dict[str, str]]]:
    base = f"/products/{sku_id}/img"
    cover = f"{base}/cover.svg"
    gallery = [{"url": f"{base}/{view}.svg", "label": label} for view, label in GALLERY_VIEWS]
    return cover, gallery


def attach_product_media(product: dict) -> dict:
    sku = product.get("sku_id", "unknown")
    name = product.get("name", sku)
    cover, gallery = product_gallery(sku, name)
    product = dict(product)
    product["cover_image"] = cover
    product["gallery"] = gallery
    return product


def render_product_svg(sku_id: str, view: str, title: str = "") -> str:
    theme = SKU_THEMES.get(sku_id, DEFAULT_THEME)
    c1, c2, accent = theme["c1"], theme["c2"], theme["accent"]
    safe_title = escape(title or sku_id)
    view = view if view in {"cover", "label", "pack", "scene"} else "cover"

    if view == "pack":
        body = f"""
        <rect x="60" y="140" width="280" height="220" rx="12" fill="{c2}" opacity="0.85"/>
        <rect x="75" y="155" width="250" height="190" rx="8" fill="{c1}" opacity="0.35"/>
        <text x="200" y="260" text-anchor="middle" fill="#fff" font-size="22" font-weight="600">{safe_title}</text>
        <text x="200" y="290" text-anchor="middle" fill="{accent}" font-size="13" opacity="0.9">外箱包装</text>
        """
    elif view == "label":
        body = f"""
        <circle cx="200" cy="250" r="110" fill="{c2}" opacity="0.25"/>
        <rect x="130" y="170" width="140" height="160" rx="16" fill="{c1}"/>
        <rect x="145" y="190" width="110" height="50" rx="6" fill="{c2}" opacity="0.7"/>
        <text x="200" y="225" text-anchor="middle" fill="#fff" font-size="14" font-weight="600">{safe_title[:8]}</text>
        <text x="200" y="310" text-anchor="middle" fill="{accent}" font-size="13">瓶标细节</text>
        """
    elif view == "scene":
        body = f"""
        <rect x="40" y="300" width="320" height="80" rx="8" fill="#1e293b"/>
        <rect x="70" y="120" width="40" height="180" rx="6" fill="{c1}" opacity="0.9"/>
        <rect x="130" y="100" width="40" height="200" rx="6" fill="{c2}" opacity="0.85"/>
        <rect x="190" y="130" width="40" height="170" rx="6" fill="{c1}" opacity="0.75"/>
        <rect x="250" y="110" width="40" height="190" rx="6" fill="{accent}" opacity="0.6"/>
        <text x="200" y="355" text-anchor="middle" fill="#94a3b8" font-size="13">门店陈列场景</text>
        """
    else:
        body = f"""
        <ellipse cx="200" cy="400" rx="70" ry="14" fill="#000" opacity="0.35"/>
        <path d="M168 110 L232 110 L238 390 L162 390 Z" fill="url(#bottle)" />
        <rect x="172" y="75" width="56" height="38" rx="6" fill="{c2}"/>
        <rect x="178" y="200" width="44" height="90" rx="4" fill="{accent}" opacity="0.55"/>
        <text x="200" y="440" text-anchor="middle" fill="#94a3b8" font-size="14">{safe_title}</text>
        """

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="480" viewBox="0 0 400 480">
  <defs>
    <linearGradient id="bottle" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
  </defs>
  <rect width="400" height="480" fill="url(#bg)"/>
  <circle cx="320" cy="80" r="60" fill="{c1}" opacity="0.08"/>
  <circle cx="60" cy="400" r="80" fill="{c2}" opacity="0.12"/>
  {body}
</svg>"""
