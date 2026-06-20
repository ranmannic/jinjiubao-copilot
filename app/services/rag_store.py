from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

DEFAULT_DOCS: dict[str, list[dict[str, Any]]] = {
    "products": [
        {
            "id": "kb-001",
            "title": "洛齐雷司令半甜白",
            "content": "法国风格半甜白，口感顺、易推销，适合团购与零售。勃艮第瓶型可选。",
            "tags": ["白葡萄酒", "半甜", "团购"],
        }
    ],
    "scripts": [
        {
            "id": "sc-001",
            "title": "团购白葡萄酒开场",
            "content": "这款半甜白入口顺、男女都能接受，家宴宴请不踩雷，同价位本地做的人少。",
            "tags": ["团购", "白葡萄酒"],
        }
    ],
    "policies": [
        {
            "id": "po-001",
            "title": "常规批发政策",
            "content": "标准 MOQ 6 瓶/箱起；常规物流按进酒宝标准。代理/混批/100件以上转销售。",
            "tags": ["批发", "MOQ"],
        }
    ],
}

FORMAT_HINTS = {
    "products": '{"id":"string","title":"string","content":"string","tags":["string"]}',
    "scripts": '{"id":"string","title":"string","content":"string","tags":["string"]}',
    "policies": '{"id":"string","title":"string","content":"string","tags":["string"]}',
}


class RagStore:
    def __init__(self, path: str = "./data/rag_knowledge.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(DEFAULT_DOCS)

    def load(self) -> dict[str, list[dict[str, Any]]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_collection(self, collection: str) -> list[dict[str, Any]]:
        return self.load().get(collection, [])

    def add(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        items = data.setdefault(collection, [])
        doc = {**doc, "id": doc.get("id") or str(uuid.uuid4())[:8]}
        items.append(doc)
        self.save(data)
        return doc

    def update(self, collection: str, doc_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = self.load()
        items = data.get(collection, [])
        for i, item in enumerate(items):
            if item.get("id") == doc_id:
                items[i] = {**item, **payload, "id": doc_id}
                self.save(data)
                return items[i]
        return None

    def delete(self, collection: str, doc_id: str) -> bool:
        data = self.load()
        items = data.get(collection, [])
        new_items = [x for x in items if x.get("id") != doc_id]
        if len(new_items) == len(items):
            return False
        data[collection] = new_items
        self.save(data)
        return True

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        q = query.lower()
        hits: list[dict[str, Any]] = []
        for collection, items in self.load().items():
            for item in items:
                text = f"{item.get('title','')} {item.get('content','')} {' '.join(item.get('tags',[]))}".lower()
                if any(w in text for w in q.split() if len(w) > 1):
                    hits.append({**item, "_collection": collection})
        return hits[:limit]
