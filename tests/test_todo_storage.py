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


def test_agent_can_complete_only_in_progress_item(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Implement")
    store.claim_next()

    completed = store.agent_done(item["id"], progress_note="Finished tests")

    assert completed["status"] == "done"
    assert completed["progress"][-1]["note"] == "Finished tests"


def test_agent_cannot_complete_open_item(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Implement")

    with pytest.raises(ValueError):
        store.agent_done(item["id"], progress_note="Too early")


def test_user_rejects_done_item_to_open_with_comment(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Review me")
    store.claim_next()
    store.agent_done(item["id"])

    reopened = store.user_reject(item["id"], progress_note="Needs more work")

    assert reopened["status"] == "open"
    assert reopened["progress"][-1]["note"] == "Needs more work"


def test_user_accepts_done_item(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Accept me")
    store.claim_next()
    store.agent_done(item["id"])

    accepted = store.user_accept(item["id"], progress_note="Looks good")

    assert accepted["status"] == "accepted"
    assert accepted["progress"][-1]["note"] == "Looks good"


def test_user_cancels_any_state_but_agent_cannot_cancel(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Cancel me")

    cancelled = store.user_cancel(item["id"], progress_note="Cancelled by Marc")

    assert cancelled["status"] == "cancelled"
    assert cancelled["progress"][-1]["note"] == "Cancelled by Marc"
    with pytest.raises(ValueError):
        store.agent_cancel(item["id"], progress_note="Agent should not cancel")


def test_delete_only_removes_cancelled_or_accepted_items(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    open_item = store.add("Keep me")
    cancelled_item = store.add("Remove cancelled")
    accepted_item = store.add("Remove accepted")
    store.user_cancel(cancelled_item["id"])
    store.claim_next()
    store.agent_done(open_item["id"])
    store.claim_next()
    store.agent_done(accepted_item["id"])
    store.user_accept(accepted_item["id"])

    with pytest.raises(ValueError):
        store.delete(open_item["id"])
    assert store.delete(cancelled_item["id"]) is True
    assert store.delete(accepted_item["id"]) is True


def test_update_rejects_direct_status_change(tmp_path):
    store = TodoStore(tmp_path / "todos.json")
    item = store.add("Implement")

    with pytest.raises(ValueError):
        store.update(item["id"], status="done")
