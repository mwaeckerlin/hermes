"""The TODO plugin API as the dashboard mounts it, over HTTP."""

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

API_PATH = Path(__file__).resolve().parents[1] / "files" / "todo-plugin" / "api.py"
PREFIX = "/api/plugins/todo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_TODO_FILE", str(tmp_path / "todos.json"))
    spec = importlib.util.spec_from_file_location("todo_api", API_PATH)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    app = FastAPI()
    app.include_router(api.router, prefix=PREFIX)
    return TestClient(app)


def test_full_review_cycle(client):
    item = client.post(f"{PREFIX}/add", json={"title": "Write docs", "notes": "README"}).json()["item"]
    assert item["status"] == "open"

    claimed = client.post(f"{PREFIX}/claim-next").json()
    assert claimed["ok"] and claimed["item"]["status"] == "in_progress"

    done = client.post(f"{PREFIX}/done/{item['id']}", json={"progress_note": "written"}).json()["item"]
    assert done["status"] == "done"

    rejected = client.post(f"{PREFIX}/reject/{item['id']}", json={"progress_note": "too short"}).json()["item"]
    assert rejected["status"] == "open"
    assert rejected["progress"][-1]["note"] == "too short"

    client.post(f"{PREFIX}/claim-next")
    client.post(f"{PREFIX}/done/{item['id']}", json={})
    accepted = client.post(f"{PREFIX}/accept/{item['id']}", json={"progress_note": "fine"}).json()["item"]
    assert accepted["status"] == "accepted"

    assert client.post(f"{PREFIX}/delete", json={"id": item["id"]}).json() == {"ok": True}
    listed = client.get(f"{PREFIX}/list").json()
    assert listed["items"] == []
    assert listed["statuses"] == ["open", "in_progress", "done", "accepted", "cancelled"]


def test_claim_next_without_open_task(client):
    assert client.post(f"{PREFIX}/claim-next").json() == {"ok": False, "item": None}


def test_forbidden_transitions_answer_400(client):
    item = client.post(f"{PREFIX}/add", json={"title": "Open task"}).json()["item"]

    assert client.post(f"{PREFIX}/done/{item['id']}", json={}).status_code == 400
    assert client.post(f"{PREFIX}/accept/{item['id']}", json={}).status_code == 400
    assert client.post(f"{PREFIX}/delete", json={"id": item["id"]}).status_code == 400
    assert client.post(f"{PREFIX}/add", json={"title": "  "}).status_code == 400


def test_unknown_task_answers_404(client):
    assert client.post(f"{PREFIX}/cancel/99", json={}).status_code == 404
    assert client.post(f"{PREFIX}/update/99", json={"title": "x"}).status_code == 404


def test_cancel_then_delete(client):
    item = client.post(f"{PREFIX}/add", json={"title": "Drop me"}).json()["item"]
    cancelled = client.post(f"{PREFIX}/cancel/{item['id']}", json={"progress_note": "not needed"}).json()["item"]
    assert cancelled["status"] == "cancelled"
    assert client.post(f"{PREFIX}/delete", json={"id": item["id"]}).json() == {"ok": True}
