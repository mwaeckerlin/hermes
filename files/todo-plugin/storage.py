"""Local TODO storage for the Hermes dashboard TODO plugin.

The storage format is a tiny JSON document under ``$HERMES_HOME/todo-plugin`` by
default.  Keeping the logic in a separate module makes the API and the tests use
exactly the same behavior.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_STATUSES = ("open", "blocked", "in_progress", "done", "accepted", "cancelled")
DEFAULT_STATUS = "open"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_storage_path() -> Path:
    """Resolve the default TODO storage path.

    ``HERMES_TODO_FILE`` is useful for tests or custom deployments. Otherwise the
    file lives in ``$HERMES_HOME/todo-plugin/todos.json`` so it is persisted in
    the normal Hermes data volume.
    """
    explicit = os.getenv("HERMES_TODO_FILE")
    if explicit:
        return Path(explicit).expanduser()
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return hermes_home / "todo-plugin" / "todos.json"


class TodoStore:
    """Small file-backed TODO store."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path else default_storage_path()

    def list(self) -> Dict[str, Any]:
        return self._read()

    def add(self, title: str, notes: str = "") -> Dict[str, Any]:
        title = title.strip()
        if not title:
            raise ValueError("Title is required")
        data = self._read()
        now = utc_now()
        item = {
            "id": str(data["next_id"]),
            "title": title,
            "status": DEFAULT_STATUS,
            "notes": notes.strip(),
            "progress": [],
            "created_at": now,
            "updated_at": now,
        }
        data["next_id"] += 1
        data["items"].append(item)
        self._write(data)
        return item

    def update(
        self,
        item_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        progress_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        if status is not None:
            raise ValueError("Use role-specific transition methods to change status")
        data = self._read()
        item = self._find(data, item_id)
        if title is not None:
            clean_title = title.strip()
            if not clean_title:
                raise ValueError("Title is required")
            item["title"] = clean_title
        if notes is not None:
            item["notes"] = notes.strip()
        self._append_progress(item, progress_note)
        item["updated_at"] = utc_now()
        self._write(data)
        return item

    def delete(self, item_id: str) -> bool:
        data = self._read()
        item = self._find(data, item_id)
        if item.get("status") not in ("cancelled", "accepted"):
            raise ValueError("Only cancelled or accepted TODO items can be deleted")
        before = len(data["items"])
        data["items"] = [item for item in data["items"] if item.get("id") != str(item_id)]
        deleted = len(data["items"]) != before
        if deleted:
            self._write(data)
        return deleted

    def claim_next(self) -> Optional[Dict[str, Any]]:
        data = self._read()
        for item in data["items"]:
            if item.get("status") == "open":
                self._transition(item, "in_progress", progress_note="Claimed by agent")
                self._write(data)
                return item
        return None

    def agent_done(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=("in_progress",),
            target="done",
            progress_note=progress_note,
        )

    def block(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=("open", "in_progress"),
            target="blocked",
            progress_note=progress_note,
        )

    def reopen(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=("blocked",),
            target="open",
            progress_note=progress_note,
        )

    def agent_cancel(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        raise ValueError("Agents cannot cancel TODO items")

    def user_cancel(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=VALID_STATUSES,
            target="cancelled",
            progress_note=progress_note,
        )

    def user_reject(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=("done",),
            target="open",
            progress_note=progress_note,
        )

    def user_accept(self, item_id: str, progress_note: Optional[str] = None) -> Dict[str, Any]:
        return self._transition_item(
            item_id,
            allowed_from=("done",),
            target="accepted",
            progress_note=progress_note,
        )

    def _transition_item(
        self,
        item_id: str,
        *,
        allowed_from: tuple[str, ...],
        target: str,
        progress_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._read()
        item = self._find(data, item_id)
        if item.get("status") not in allowed_from:
            raise ValueError(f"Cannot move TODO item from {item.get('status')} to {target}")
        self._transition(item, target, progress_note=progress_note)
        self._write(data)
        return item

    def _transition(self, item: Dict[str, Any], status: str, progress_note: Optional[str] = None) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        item["status"] = status
        self._append_progress(item, progress_note)
        item["updated_at"] = utc_now()

    def _append_progress(self, item: Dict[str, Any], progress_note: Optional[str] = None) -> None:
        if progress_note is not None:
            clean_note = progress_note.strip()
            if clean_note:
                item.setdefault("progress", []).append({"at": utc_now(), "note": clean_note})

    def _find(self, data: Dict[str, Any], item_id: str) -> Dict[str, Any]:
        for item in data["items"]:
            if item.get("id") == str(item_id):
                return item
        raise KeyError(f"TODO item not found: {item_id}")

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"next_id": 1, "items": []}
        with self.path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []
        next_id = data.get("next_id")
        if not isinstance(next_id, int) or next_id < 1:
            next_id = self._next_id_from_items(items)
        return {"next_id": next_id, "items": self._normalize_items(items)}

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix="todos-", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _normalize_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        now = utc_now()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item["id"] = str(item.get("id", "")).strip()
            item["title"] = str(item.get("title", "")).strip()
            if not item["id"] or not item["title"]:
                continue
            if item.get("status") not in VALID_STATUSES:
                item["status"] = DEFAULT_STATUS
            item["notes"] = str(item.get("notes", ""))
            progress = item.get("progress", [])
            item["progress"] = progress if isinstance(progress, list) else []
            item.setdefault("created_at", now)
            item.setdefault("updated_at", item["created_at"])
            normalized.append(item)
        return normalized

    def _next_id_from_items(self, items: List[Dict[str, Any]]) -> int:
        numeric_ids = []
        for item in items:
            try:
                numeric_ids.append(int(item.get("id")))
            except (TypeError, ValueError):
                pass
        return max(numeric_ids, default=0) + 1
