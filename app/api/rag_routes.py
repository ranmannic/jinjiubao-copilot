from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.rag_store import FORMAT_HINTS, RagStore

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


def _store(request: Request) -> RagStore:
    return request.app.state.rag_store


@router.get("/collections")
async def list_collections(request: Request) -> dict:
    store = _store(request)
    data = store.load()
    return {"collections": list(data.keys()), "format_hints": FORMAT_HINTS}


@router.get("/search/query")
async def search(request: Request, q: str, limit: int = 5) -> dict:
    store = _store(request)
    return {"results": store.search(q, limit=limit)}


@router.get("/{collection}")
async def list_docs(request: Request, collection: str) -> dict:
    store = _store(request)
    return {"items": store.list_collection(collection), "format_hint": FORMAT_HINTS.get(collection)}


@router.post("/{collection}")
async def add_doc(request: Request, collection: str, body: dict) -> dict:
    store = _store(request)
    return store.add(collection, body)


@router.put("/{collection}/{doc_id}")
async def update_doc(request: Request, collection: str, doc_id: str, body: dict) -> dict:
    store = _store(request)
    doc = store.update(collection, doc_id, body)
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


@router.delete("/{collection}/{doc_id}")
async def delete_doc(request: Request, collection: str, doc_id: str) -> dict:
    store = _store(request)
    if not store.delete(collection, doc_id):
        raise HTTPException(404, "document not found")
    return {"deleted": doc_id}
