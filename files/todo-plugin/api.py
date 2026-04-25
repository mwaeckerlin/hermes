"""Local TODO-list API for the Hermes dashboard plugin."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from .storage import TodoStore, VALID_STATUSES
except ImportError:  # pragma: no cover - dashboard plugin loader path
    from storage import TodoStore, VALID_STATUSES

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


@router.post("/delete")
async def delete_todo(req: DeleteTodoRequest):
    """Delete a TODO item."""
    return {"ok": _store.delete(req.id)}
