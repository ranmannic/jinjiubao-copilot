from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.services.config_store import ConfigStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _store(request: Request) -> ConfigStore:
    return request.app.state.config_store


@router.get("/api-config")
async def get_api_config(request: Request) -> dict:
    store = _store(request)
    data = store.load()
    return data


@router.put("/api-config/base")
async def update_base_url(request: Request, body: dict) -> dict:
    store = _store(request)
    data = store.load()
    data["base_url"] = body.get("base_url", data.get("base_url"))
    store.save(data)
    return {"base_url": data["base_url"]}


@router.put("/api-config/{api_key}")
async def update_api(request: Request, api_key: str, body: dict) -> dict:
    store = _store(request)
    return store.update_api(api_key, body)


@router.post("/api-config/{api_key}/test")
async def test_api(request: Request, api_key: str) -> dict:
    store = _store(request)
    cfg = store.load()
    api = cfg.get("apis", {}).get(api_key)
    if not api:
        raise HTTPException(404, "API not found")

    base = cfg.get("base_url", "").rstrip("/")
    path = api.get("path", "")
    method = api.get("method", "GET").upper()
    params = api.get("params") or {}

    for k, v in list(params.items()):
        placeholder = "{" + k + "}"
        if placeholder in path:
            path = path.replace(placeholder, str(v))
            params.pop(k, None)

    url = f"{base}/{path.lstrip('/')}"
    settings = request.app.state.settings
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.jinjiubao_api_key:
        headers["Authorization"] = f"Bearer {settings.jinjiubao_api_key}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if method == "GET":
                resp = await client.get(url, params=params, headers=headers)
            else:
                resp = await client.request(method, url, json=params, headers=headers)
        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "url": url,
            "body": resp.text[:2000],
        }
    except Exception as exc:
        logger.exception("API test failed")
        return {"ok": False, "url": url, "error": str(exc)}
