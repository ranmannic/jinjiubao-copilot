from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.product_media import attach_product_media

logger = logging.getLogger(__name__)


class JinjiubaoClient:
    """进酒宝 SaaS 对接客户端。开发模式下使用内置 mock 数据。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.use_mock = settings.app_env == "development" or not settings.jinjiubao_api_key

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.settings.jinjiubao_api_key:
            headers["Authorization"] = f"Bearer {self.settings.jinjiubao_api_key}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.settings.jinjiubao_api_base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.settings.jinjiubao_api_timeout) as client:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def get_customer(self, customer_id: str, token: str | None = None) -> dict:
        if self.use_mock:
            return self._mock_customer(customer_id)
        params = {"token": token} if token else None
        return await self._request("GET", f"/v1/customers/{customer_id}", params=params)

    async def list_products(
        self,
        customer_id: str,
        category: str | None = None,
        region: str | None = None,
    ) -> list[dict]:
        if self.use_mock:
            products = [attach_product_media(p) for p in self._mock_products()]
            if category:
                products = [p for p in products if category in p.get("category", "")]
            return products
        params: dict[str, str] = {"customer_id": customer_id}
        if category:
            params["category"] = category
        if region:
            params["region"] = region
        data = await self._request("GET", "/v1/products", params=params)
        return data.get("items", data)

    async def get_region_competition(self, sku_ids: list[str], city: str | None) -> dict[str, int]:
        if self.use_mock:
            return {sku: {"JJ-LQ-001": 1, "JJ-JC-S100": 2, "JJ-WB-001": 3, "JJ-GF-001": 4, "JJ-LQ-002": 1}.get(sku, 2) for sku in sku_ids}
        data = await self._request(
            "POST",
            "/v1/analytics/region-competition",
            json={"sku_ids": sku_ids, "city": city},
        )
        return data.get("counts", {})

    async def assign_sales(self, lead: dict) -> dict:
        if self.use_mock:
            return {"sales_id": "S001", "sales_name": "张经理", "phone": "13800000001"}
        return await self._request("POST", "/v1/crm/leads/assign", json=lead)

    async def create_lead(self, lead: dict) -> dict:
        if self.use_mock:
            logger.info("Mock CRM lead created: %s", lead.get("session_id"))
            return {"lead_id": f"LEAD-{lead.get('session_id', '')[:8]}", "status": "assigned"}
        return await self._request("POST", "/v1/crm/leads", json=lead)

    async def add_to_cart(self, customer_id: str, sku_id: str, quantity: int = 1) -> dict:
        if self.use_mock:
            return {"cart_id": "CART-MOCK", "sku_id": sku_id, "quantity": quantity}
        return await self._request(
            "POST",
            "/v1/cart/items",
            json={"customer_id": customer_id, "sku_id": sku_id, "quantity": quantity},
        )

    async def notify_sales(
        self,
        sales_id: str,
        title: str,
        body: str,
        lead: dict | None = None,
    ) -> dict:
        if self.use_mock:
            logger.info("Mock notify sales %s: %s - %s", sales_id, title, body)
            return {"status": "sent", "sales_id": sales_id}
        payload = {"sales_id": sales_id, "title": title, "body": body}
        if lead:
            payload["lead"] = lead
        return await self._request("POST", "/v1/notifications/sales", json=payload)

    def _mock_customer(self, customer_id: str) -> dict:
        return {
            "customer_id": customer_id,
            "name": "王总",
            "phone": "13800001234",
            "tier": "standard",
            "region": "浙江省-杭州市",
            "is_returning": customer_id in {"cust_demo_001", "cust_returning"},
            "last_order_category": "白葡萄酒",
        }

    def _mock_products(self) -> list[dict]:
        return [
            {
                "sku_id": "JJ-LQ-001",
                "name": "洛齐雷司令半甜白 750ml",
                "brand": "洛齐",
                "category": "白葡萄酒",
                "origin_country": "德国",
                "origin_region": "摩泽尔",
                "grape_variety": "雷司令",
                "bottle_type": "莱茵瓶",
                "spec": "750ml",
                "outer_pack": "纸箱",
                "retail_band": "50-100元",
                "supply_price": 38,
                "retail_min": 68,
                "retail_max": 88,
                "tags": ["易推销", "高周转", "半甜"],
                "strategic_weight": 5,
                "moq": 6,
                "in_stock": True,
                "stock_qty": 500,
            },
            {
                "sku_id": "JJ-JC-S100",
                "name": "金锤 S100 干白 750ml",
                "brand": "金锤",
                "category": "白葡萄酒",
                "origin_country": "法国",
                "origin_region": "朗格多克",
                "grape_variety": "霞多丽",
                "bottle_type": "波尔多瓶",
                "spec": "750ml",
                "grade": "AOP",
                "outer_pack": "礼盒箱",
                "retail_band": "100-200元",
                "supply_price": 72,
                "retail_min": 128,
                "retail_max": 168,
                "tags": ["品牌势能", "宴请", "礼盒"],
                "strategic_weight": 8,
                "moq": 6,
                "in_stock": True,
                "agent_restricted": True,
                "max_local_agents": 2,
            },
            {
                "sku_id": "JJ-WB-001",
                "name": "翁布里亚进口精酿 330ml",
                "brand": "翁布里亚",
                "category": "精酿啤酒",
                "origin_country": "意大利",
                "origin_region": "翁布里亚",
                "spec": "330ml",
                "outer_pack": "纸箱",
                "retail_band": "30-50元",
                "supply_price": 28,
                "retail_min": 50,
                "retail_max": 80,
                "tags": ["进口", "高周转"],
                "strategic_weight": 3,
            },
            {
                "sku_id": "JJ-GF-001",
                "name": "毛府经典 500ml",
                "brand": "毛府",
                "category": "国产白酒",
                "origin_country": "中国",
                "origin_region": "四川",
                "baijiu_aroma": "浓香型",
                "spec": "500ml",
                "grade": "优级",
                "outer_pack": "纸箱",
                "retail_band": "50-100元",
                "supply_price": 45,
                "retail_min": 78,
                "retail_max": 98,
                "tags": ["走量", "宴席"],
                "strategic_weight": 4,
            },
            {
                "sku_id": "JJ-LQ-002",
                "name": "洛齐枫车果酒 375ml",
                "brand": "洛齐",
                "category": "果酒",
                "origin_country": "德国",
                "spec": "375ml",
                "outer_pack": "飞机箱",
                "retail_band": "30-50元",
                "supply_price": 22,
                "retail_min": 39,
                "retail_max": 59,
                "tags": ["高周转", "易推销"],
                "strategic_weight": 4,
            },
            {
                "sku_id": "JJ-JC-G500",
                "name": "金锤 G500 干红 750ml",
                "brand": "金锤",
                "category": "红葡萄酒",
                "origin_country": "法国",
                "origin_region": "波尔多",
                "grape_variety": "赤霞珠",
                "bottle_type": "波尔多瓶",
                "spec": "750ml",
                "grade": "AOP",
                "outer_pack": "木箱",
                "retail_band": "200-300元",
                "supply_price": 118,
                "retail_min": 198,
                "retail_max": 268,
                "tags": ["品牌势能", "宴请", "礼盒"],
                "strategic_weight": 10,
            },
        ]
