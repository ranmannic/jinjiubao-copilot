from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models.domain import ConversationSession


class SessionStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._memory: dict[str, ConversationSession] = {}
        self._dir = Path(settings.sqlite_path).parent / "sessions"
        if settings.session_backend == "sqlite":
            self._dir.mkdir(parents=True, exist_ok=True)

    def create(self, session: ConversationSession) -> ConversationSession:
        if self.settings.session_backend == "memory":
            self._memory[session.session_id] = session
            return session
        self._save(session)
        return session

    def get(self, session_id: str) -> ConversationSession | None:
        if self.settings.session_backend == "memory":
            return self._memory.get(session_id)
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        return ConversationSession.model_validate_json(path.read_text(encoding="utf-8"))

    def update(self, session: ConversationSession) -> ConversationSession:
        session.updated_at = datetime.utcnow()
        if self.settings.session_backend == "memory":
            self._memory[session.session_id] = session
            return session
        self._save(session)
        return session

    def _save(self, session: ConversationSession) -> None:
        path = self._dir / f"{session.session_id}.json"
        path.write_text(session.model_dump_json(), encoding="utf-8")


def new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:16]}"
