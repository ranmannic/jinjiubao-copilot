from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.agents.copilot_agent import CopilotAgent
from app.core.llm_config import SUPPORTED_MODEL_HINT
from app.api.schemas import ChatRequest, SessionResponse, StartSessionRequest
from app.models.domain import CopilotResponse
from app.services.session_service import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


def _agent(request: Request) -> CopilotAgent:
    return request.app.state.copilot_agent


def _store(request: Request) -> SessionStore:
    return request.app.state.session_store


@router.get("/health")
async def health(request: Request) -> dict:
    agent = _agent(request)
    llm_status = "disabled"
    llm_ok = False
    if agent.llm.enabled:
        llm_ok, probe_err = await agent.llm.probe()
        llm_status = "ok" if llm_ok else "error"
        if probe_err and not agent.llm.last_error:
            agent.llm.last_error = probe_err
    settings = agent.settings
    return {
        "status": "ok",
        "service": "jinjiubao-copilot",
        "llm_enabled": agent.llm.enabled,
        "llm_model": settings.llm_model if agent.llm.enabled else None,
        "llm_base_url": settings.llm_base_url if agent.llm.enabled else None,
        "llm_status": llm_status,
        "llm_error": agent.llm.last_error,
        "llm_config_notes": settings.llm_config_notes,
        "supported_models_hint": SUPPORTED_MODEL_HINT,
    }


@router.post("/sessions/start", response_model=CopilotResponse)
async def start_session(body: StartSessionRequest, request: Request) -> CopilotResponse:
    agent = _agent(request)
    store = _store(request)
    response, session = await agent.start_session(body.customer_id, body.token)
    store.create(session)
    return response


@router.get("/customers/{customer_id}/history")
async def list_customer_history(customer_id: str, request: Request) -> dict:
    agent = _agent(request)
    items = agent.history.list_sessions(customer_id)
    return {"customer_id": customer_id, "sessions": items}


@router.get("/customers/{customer_id}/history/{session_id}")
async def get_customer_history_session(
    customer_id: str, session_id: str, request: Request
) -> dict:
    agent = _agent(request)
    record = agent.history.get_session(customer_id, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="history session not found")
    return record


@router.post("/chat", response_model=CopilotResponse)
async def chat(body: ChatRequest, request: Request) -> CopilotResponse:
    agent = _agent(request)
    store = _store(request)
    session = store.get(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    response, updated = await agent.handle_message(session, body.message, body.quick_reply_value)
    agent._persist_history(updated)
    store.update(updated)
    return response


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    store = _store(request)
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        phase=session.phase.value,
        profile=session.profile.model_dump(),
        handoff=session.handoff.model_dump() if session.handoff.required else None,
        message_count=len(session.messages),
    )
