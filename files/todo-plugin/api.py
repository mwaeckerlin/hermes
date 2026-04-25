"""Local TODO-list API for the Hermes dashboard plugin."""

import importlib.util
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_storage_path = Path(__file__).with_name("storage.py")
_storage_spec = importlib.util.spec_from_file_location("hermes_todo_storage", _storage_path)
if _storage_spec is None or _storage_spec.loader is None:  # pragma: no cover
    raise RuntimeError("Cannot load TODO storage module")
_storage_module = importlib.util.module_from_spec(_storage_spec)
_storage_spec.loader.exec_module(_storage_module)
TodoStore = _storage_module.TodoStore
VALID_STATUSES = _storage_module.VALID_STATUSES

router = APIRouter()
_store = TodoStore()


class AddTodoRequest(BaseModel):
    title: str
    notes: str = ""


class UpdateTodoRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    notes: str | None = None
    progress_note: str | None = None


class DeleteTodoRequest(BaseModel):
    id: str


@router.get("/list")
async def list_todos():
    """Return all TODO items and valid statuses."""
    data = _store.list()
    data["statuses"] = list(VALID_STATUSES)
    return data


@router.post("/add")
async def add_todo(req: AddTodoRequest):
    """Create a TODO item."""
    try:
        return {"ok": True, "item": _store.add(req.title, req.notes)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update/{item_id}")
async def update_todo(item_id: str, req: UpdateTodoRequest):
    """Update title, notes, status, or append a progress note."""
    try:
        item = _store.update(
            item_id,
            title=req.title,
            status=req.status,
            notes=req.notes,
            progress_note=req.progress_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.post("/claim-next")
async def claim_next_todo():
    """Move the first open TODO item to in_progress."""
    item = _store.claim_next()
    return {"ok": item is not None, "item": item}


@router.post("/cancel/{item_id}")
async def cancel_todo(item_id: str, req: UpdateTodoRequest):
    """Cancel a TODO with an optional human comment."""
    try:
        item = _store.update(item_id, status="cancelled", progress_note=req.progress_note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.post("/reject/{item_id}")
async def reject_todo(item_id: str, req: UpdateTodoRequest):
    """Reject a done TODO and move it back to open with a human comment."""
    try:
        item = _store.update(item_id, status="open", progress_note=req.progress_note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.post("/delete")
async def delete_todo(req: DeleteTodoRequest):
    """Delete a TODO item."""
    return {"ok": _store.delete(req.id)}
