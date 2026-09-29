"""Hermes' Hindsight memory end to end: the gateway image's plugin, loaded by
hermes' own provider lookup, against a real Hindsight server behind a proxy
that adds the key (test/docker-compose.yml). The test container holds no key.
"""

import json
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "files" / "render-config.py"
HINDSIGHT = ROOT / "files" / "hindsight-config.json.j2"
CONFIG = ROOT / "files" / "config.yaml.j2"
PROXY = os.environ["HINDSIGHT_TEST_PROXY_URL"]


def render(template, target, env):
    subprocess.run([os.sys.executable, str(RENDER), str(template), str(target)],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)


@pytest.fixture
def provider(tmp_path, monkeypatch):
    bank = f"hermes-e2e-{uuid.uuid4().hex[:8]}"
    home = tmp_path / "home"
    (home / "hindsight").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("HINDSIGHT_API_KEY")}
    env.update({"HINDSIGHT_API_URL": PROXY, "HINDSIGHT_BANK_ID": bank, "HINDSIGHT_RETAIN_TAGS": "e2e"})
    render(HINDSIGHT, home / "hindsight" / "config.json", env)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HINDSIGHT_API_KEY", raising=False)
    from plugins.memory import load_memory_provider
    memory = load_memory_provider("hindsight")
    assert memory is not None, "hermes does not find the hindsight memory provider"
    assert memory.is_available()
    memory.initialize(session_id=f"session-{bank}", hermes_home=str(home), platform="cli")
    yield memory, bank
    memory.shutdown()


def test_container_holds_no_hindsight_key():
    assert not os.environ.get("HINDSIGHT_API_KEY")


def test_server_refuses_a_request_without_the_proxy():
    request = urllib.request.Request(os.environ["HINDSIGHT_TEST_DIRECT_URL"] + "/v1/default/banks")
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=30)
    refused.value.close()
    assert refused.value.code in (401, 403)


def test_retain_and_recall_through_the_proxy(provider):
    memory, bank = provider
    tools = {schema["name"] for schema in memory.get_tool_schemas()}
    assert tools == {"hindsight_retain", "hindsight_recall", "hindsight_reflect"}

    stored = json.loads(memory.handle_tool_call(
        "hindsight_retain", {"content": "Marc's build host is called saturn."}))
    assert "error" not in stored, stored

    found = ""
    for _ in range(30):
        found = memory.handle_tool_call("hindsight_recall", {"query": "What is the build host called?"})
        if "saturn" in found:
            break
        time.sleep(2)
    assert "saturn" in found, found


def test_shared_bank_is_an_mcp_server_of_hermes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    url = PROXY + "/mcp/shared/"
    env = dict(os.environ, HINDSIGHT_SHARED_MCP_URL=url, TERMINAL_SSH_KEY="/tmp/test-key",
               HERMES_DEFAULT_MODEL="test/model")
    render(CONFIG, home / "config.yaml", env)
    monkeypatch.setenv("HERMES_HOME", str(home))
    from tools.mcp_tool_config import _load_mcp_config
    servers = _load_mcp_config()

    assert servers["hindsight-shared"]["url"] == url
    # the endpoint answers the MCP handshake through the proxy
    request = urllib.request.Request(url, method="POST", data=json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "hermes-e2e", "version": "1"}},
    }).encode(), headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(request, timeout=60) as response:
        assert response.status == 200
        assert "serverInfo" in response.read().decode()
