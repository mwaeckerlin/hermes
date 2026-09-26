"""The pairing plugin API as the dashboard mounts it, over HTTP, on the
pairing store of the hermes-agent version the image ships."""

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

API_PATH = Path(__file__).resolve().parents[1] / "files" / "pairing-plugin" / "api.py"
PREFIX = "/api/plugins/pairing"


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)
    import gateway.pairing
    monkeypatch.setattr(gateway.pairing, "PAIRING_DIR", tmp_path / "pairing")
    spec = importlib.util.spec_from_file_location("pairing_api", API_PATH)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    app = FastAPI()
    app.include_router(api.router, prefix=PREFIX)
    return api._store, TestClient(app)


def test_list_shows_pending_request_with_its_id(plugin):
    store, client = plugin
    store.generate_code("telegram", "12345", "alice")

    pending = client.get(f"{PREFIX}/list").json()["pending"]

    assert len(pending) == 1
    assert pending[0]["platform"] == "telegram"
    assert pending[0]["user_name"] == "alice"
    assert store.looks_like_request_id(pending[0]["request_id"])


def test_approve_by_request_id_admits_the_user(plugin):
    store, client = plugin
    store.generate_code("telegram", "12345", "alice")
    request_id = client.get(f"{PREFIX}/list").json()["pending"][0]["request_id"]

    result = client.post(f"{PREFIX}/approve", json={"platform": "telegram", "request_id": request_id}).json()

    assert result == {"ok": True, "user_id": "12345", "user_name": "alice"}
    listed = client.get(f"{PREFIX}/list").json()
    assert listed["pending"] == []
    assert [a["user_id"] for a in listed["approved"]] == ["12345"]
    assert store.is_approved("telegram", "12345")


def test_approve_by_code_the_user_reports(plugin):
    store, client = plugin
    code = store.generate_code("discord", "777", "bob")

    result = client.post(f"{PREFIX}/approve", json={"platform": "Discord", "code": code.lower()}).json()

    assert result["ok"] is True
    assert store.is_approved("discord", "777")


def test_unknown_request_is_refused(plugin):
    store, client = plugin
    store.generate_code("telegram", "12345", "alice")

    by_id = client.post(f"{PREFIX}/approve", json={"platform": "telegram", "request_id": "0123456789abcdef"}).json()
    by_code = client.post(f"{PREFIX}/approve", json={"platform": "telegram", "code": "AAAAAAAA"}).json()
    neither = client.post(f"{PREFIX}/approve", json={"platform": "telegram"})

    assert by_id == {"ok": False, "error": "Request not found or expired"}
    assert by_code == {"ok": False, "error": "Code not found or expired"}
    assert neither.status_code == 400
    assert not store.is_approved("telegram", "12345")


def test_revoke_removes_the_user(plugin):
    store, client = plugin
    code = store.generate_code("telegram", "12345", "alice")
    client.post(f"{PREFIX}/approve", json={"platform": "telegram", "code": code})

    assert client.post(f"{PREFIX}/revoke", json={"platform": "telegram", "user_id": "12345"}).json() == {"ok": True}
    assert client.post(f"{PREFIX}/revoke", json={"platform": "telegram", "user_id": "12345"}).json() == {"ok": False}
    assert client.get(f"{PREFIX}/list").json()["approved"] == []
