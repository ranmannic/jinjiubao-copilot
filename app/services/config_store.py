from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_APIS: dict[str, dict[str, Any]] = {
    "get_customer": {
        "name": "获取客户信息",
        "method": "GET",
        "path": "/v1/customers/{customer_id}",
        "params": {"customer_id": "cust_demo_001", "token": ""},
        "description": "登录后拉取客户画像、等级、区域",
    },
    "list_products": {
        "name": "商品列表",
        "method": "GET",
        "path": "/v1/products",
        "params": {"customer_id": "cust_demo_001", "category": "白葡萄酒", "region": "浙江省-杭州市"},
        "description": "按品类/区域拉取可售 SKU",
    },
    "region_competition": {
        "name": "区域竞争度",
        "method": "POST",
        "path": "/v1/analytics/region-competition",
        "params": {"sku_ids": ["JJ-LQ-001"], "city": "杭州市"},
        "description": "查询当地已有多少客户在卖",
    },
    "assign_sales": {
        "name": "转接销售-分配",
        "method": "POST",
        "path": "/v1/crm/leads/assign",
        "params": {"session_id": "demo", "customer_id": "cust_demo_001", "reason": "客户申请转人工"},
        "description": "转人工时分派销售并发送通知",
    },
    "create_lead": {
        "name": "转接销售-创建线索",
        "method": "POST",
        "path": "/v1/crm/leads",
        "params": {"session_id": "demo", "customer_id": "cust_demo_001", "reason": "转人工"},
        "description": "写入 CRM 线索",
    },
    "notify_sales": {
        "name": "转接销售-消息通知",
        "method": "POST",
        "path": "/v1/notifications/sales",
        "params": {"sales_id": "S001", "title": "新客户待跟进", "body": "Copilot 转接"},
        "description": "给销售发 App/短信提醒",
    },
    "add_to_cart": {
        "name": "加入进货单",
        "method": "POST",
        "path": "/v1/cart/items",
        "params": {"customer_id": "cust_demo_001", "sku_id": "JJ-LQ-001", "quantity": 1},
        "description": "将推荐 SKU 加入进货单",
    },
}


class ConfigStore:
    def __init__(self, path: str = "./data/api_config.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save({"base_url": "https://api.jinjiubao.example.com", "apis": DEFAULT_APIS})

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_api(self, key: str) -> dict[str, Any] | None:
        return self.load().get("apis", {}).get(key)

    def update_api(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        data.setdefault("apis", {})[key] = {**data.get("apis", {}).get(key, {}), **payload}
        self.save(data)
        return data["apis"][key]

    def list_apis(self) -> dict[str, dict[str, Any]]:
        return self.load().get("apis", DEFAULT_APIS)
