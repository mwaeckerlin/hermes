import importlib.util
import json
from pathlib import Path

import pytest

STORAGE_PATH = Path(__file__).resolve().parents[1] / "files" / "todo-plugin" / "storage.py"
spec = importlib.util.spec_from_file_location("todo_storage", STORAGE_PATH)
todo_storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(todo_storage)
TodoStore = todo_storage.TodoStore


def test_add_todo_persists_item(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)

    item = store.add("Write docs", "Short note")

    assert item["id"] == "1"
    assert item["status"] == "open"
    assert item["title"] == "Write docs"
    assert item["notes"] == "Short note"
    persisted = json.loads(path.read_text())
    assert persisted["items"][0]["title"] == "Write docs"


def test_claim_next_moves_first_open_item_to_in_progress(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    first = store.add("First")
    second = store.add("Second")

    claimed = store.claim_next()

    data = store.list()
    assert claimed["id"] == first["id"]
    assert data["items"][0]["status"] == "in_progress"
    assert data["items"][1]["id"] == second["id"]
    assert data["items"][0]["progress"][0]["note"] == "Claimed by agent"


def test_update_validates_status_and_appends_progress(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Implement")

    updated = store.update(item["id"], status="done", progress_note="Finished tests")

    assert updated["status"] == "done"
    assert updated["progress"][-1]["note"] == "Finished tests"


def test_cancelled_is_a_valid_status(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Cancel me")

    updated = store.update(item["id"], status="cancelled", progress_note="Cancelled by Marc")

    assert updated["status"] == "cancelled"
    assert updated["progress"][-1]["note"] == "Cancelled by Marc"


def test_reject_done_item_reopens_with_comment(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Review me")
    store.update(item["id"], status="done")

    reopened = store.update(item["id"], status="open", progress_note="Needs more work")

    assert reopened["status"] == "open"
    assert reopened["progress"][-1]["note"] == "Needs more work"


def test_update_rejects_invalid_status(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Implement")

    with pytest.raises(ValueError):
        store.update(item["id"], status="blocked")


def test_delete_removes_item(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Remove me")

    assert store.delete(item["id"]) is True
    assert store.list()["items"] == []
