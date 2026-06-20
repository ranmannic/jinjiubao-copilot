from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.agents.copilot_agent import CopilotAgent
from app.api.admin_routes import router as admin_router
from app.api.rag_routes import router as rag_router
from app.api.routes import router
from app.config import get_settings
from app.core.product_media import render_product_svg
from app.services.config_store import ConfigStore
from app.services.rag_store import RagStore
from app.services.customer_registry import CustomerRegistry
from app.services.history_store import HistoryStore
from app.services.session_service import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    app = FastAPI(
        title="进酒宝 AI 酒商 Copilot",
        description="登录后接待、分类、挖需、推品、推方案、转销售",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.session_store = SessionStore(settings)
    app.state.customer_registry = CustomerRegistry(
        settings.sqlite_path.replace("sessions.db", "known_customers.json")
    )
    app.state.history_store = HistoryStore(
        settings.sqlite_path.replace("sessions.db", "customer_history")
    )
    app.state.config_store = ConfigStore(settings.sqlite_path.replace("sessions.db", "api_config.json"))
    app.state.rag_store = RagStore(settings.sqlite_path.replace("sessions.db", "rag_knowledge.json"))
    app.state.copilot_agent = CopilotAgent(
        settings,
        registry=app.state.customer_registry,
        history=app.state.history_store,
    )
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(rag_router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/admin")
    async def admin_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "admin.html")

    @app.get("/rag")
    async def rag_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "rag.html")

    @app.get("/")
    async def chat_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "chat.html")

    @app.get("/products/{sku_id}/img/{view}.svg")
    async def product_image_svg(sku_id: str, view: str) -> Response:
        name = sku_id
        for p in app.state.copilot_agent.jjb._mock_products():
            if p.get("sku_id") == sku_id:
                name = p.get("name", sku_id)
                break
        svg = render_product_svg(sku_id, view, name)
        return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/chat")
    async def chat_ui_alias() -> RedirectResponse:
        return RedirectResponse(url="/")

    @app.on_event("startup")
    async def startup() -> None:
        agent: CopilotAgent = app.state.copilot_agent
        if agent.llm.enabled:
            for note in settings.llm_config_notes:
                logger.warning("LLM config: %s", note)
            logger.info(
                "Copilot started with LLM model=%s base=%s",
                settings.llm_model,
                settings.llm_base_url,
            )
            ok, err = await agent.llm.resolve_connection()
            if ok:
                logger.info("LLM connection OK: %s @ %s", settings.llm_model, settings.llm_base_url)
            else:
                logger.warning("LLM connection issue: %s", err)
        else:
            logger.warning(
                "Copilot started WITHOUT LLM — set LLM_API_KEY in .env for AI conversation"
            )

    return app


app = create_app()
