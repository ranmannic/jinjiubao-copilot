from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RETENTION_DAYS = 30


class HistoryStore:
    """按 customer_id 保存会话摘要，保留 30 天。"""

    def __init__(self, path: str = "./data/customer_history"):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _file(self, customer_id: str) -> Path:
        safe = customer_id.replace("/", "_")
        return self.path / f"{safe}.json"

    def _purge_old(self, records: list[dict]) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        kept = []
        for r in records:
            try:
                ts = datetime.fromisoformat(r.get("updated_at", ""))
            except ValueError:
                continue
            if ts >= cutoff:
                kept.append(r)
        return kept

    def list_sessions(self, customer_id: str) -> list[dict[str, Any]]:
        f = self._file(customer_id)
        if not f.exists():
            return []
        records = self._purge_old(json.loads(f.read_text(encoding="utf-8")))
        f.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return sorted(records, key=lambda x: x.get("updated_at", ""), reverse=True)

    def save_session(self, customer_id: str, session_data: dict[str, Any]) -> None:
        records = self.list_sessions(customer_id)
        sid = session_data.get("session_id")
        records = [r for r in records if r.get("session_id") != sid]
        records.insert(0, session_data)
        self._file(customer_id).write_text(
            json.dumps(self._purge_old(records), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_session(self, customer_id: str, session_id: str) -> dict[str, Any] | None:
        for r in self.list_sessions(customer_id):
            if r.get("session_id") == session_id:
                return r
        return None
