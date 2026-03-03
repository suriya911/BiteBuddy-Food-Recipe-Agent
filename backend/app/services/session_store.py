from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from app.schemas import ChatMessage, UserProfile


@dataclass
class SessionState:
    session_id: str
    profile: UserProfile = field(default_factory=UserProfile)
    history: list[ChatMessage] = field(default_factory=list)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str | None) -> SessionState:
        with self._lock:
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]

            resolved_id = session_id or str(uuid4())
            session = self._sessions.get(resolved_id)
            if session is None:
                session = SessionState(session_id=resolved_id)
                self._sessions[resolved_id] = session
            return session

    def update(
        self,
        *,
        session_id: str,
        profile: UserProfile,
        history: list[ChatMessage],
    ) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionState(session_id=session_id)
                self._sessions[session_id] = session
            session.profile = profile
            session.history = history
            return session
