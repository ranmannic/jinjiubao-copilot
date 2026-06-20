from __future__ import annotations

import json
from pathlib import Path


class CustomerRegistry:
    """本地记录已访问过的 customer_id；新 ID 视为新用户。"""

    def __init__(self, path: str = "./data/known_customers.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(set())

    def load(self) -> set[str]:
        return set(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, ids: set[str]) -> None:
        self.path.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8")

    def is_new(self, customer_id: str) -> bool:
        return customer_id not in self.load()

    def mark_seen(self, customer_id: str) -> None:
        ids = self.load()
        ids.add(customer_id)
        self.save(ids)
