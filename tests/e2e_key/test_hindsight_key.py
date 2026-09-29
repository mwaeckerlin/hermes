"""Hermes' Hindsight memory with the Hindsight key held by the gateway
(HINDSIGHT_API_KEY, from a Docker secret in production) against the real
server directly, while hindsight/config.json stays without a key."""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "files" / "render-config.py"
HINDSIGHT = ROOT / "files" / "hindsight-config.json.j2"
SERVER = os.environ["HINDSIGHT_TEST_DIRECT_URL"]


def test_retain_and_recall_with_the_key_in_the_environment(tmp_path, monkeypatch):
    key = os.environ["HINDSIGHT_API_KEY"]
    assert key
    bank = f"hermes-key-{uuid.uuid4().hex[:8]}"
    home = tmp_path / "home"
    (home / "hindsight").mkdir(parents=True)
    env = dict(os.environ, HINDSIGHT_API_URL=SERVER, HINDSIGHT_BANK_ID=bank)
    subprocess.run([os.sys.executable, str(RENDER), str(HINDSIGHT), str(home / "hindsight" / "config.json")],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)
    assert key not in (home / "hindsight" / "config.json").read_text()
    monkeypatch.setenv("HERMES_HOME", str(home))
    from plugins.memory import load_memory_provider
    memory = load_memory_provider("hindsight")
    memory.initialize(session_id=f"session-{bank}", hermes_home=str(home), platform="cli")
    try:
        stored = json.loads(memory.handle_tool_call(
            "hindsight_retain", {"content": "The shared test bank lives on the host called jupiter."}))
        assert "error" not in stored, stored
        found = ""
        for _ in range(30):
            found = memory.handle_tool_call("hindsight_recall", {"query": "Which host holds the shared test bank?"})
            if "jupiter" in found:
                break
            time.sleep(2)
        assert "jupiter" in found, found
    finally:
        memory.shutdown()
