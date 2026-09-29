"""Reads what the scripted model recorded (tests/isolation/scripted_model.py):
every request body holds everything the agent has seen, tool results
included. No secret value of the gateway may appear there, and the probe
steps must really have run, or the test proves nothing."""

import json
import os
from pathlib import Path

RECORDS = Path(os.environ.get("RECORDS", "/records")) / "requests.jsonl"
VARIABLES = os.environ["PROBE_VARIABLES"].split()
PRIVATE_KEY = os.environ["PROBE_PRIVATE_KEY"].replace("\\n", "\n")


def records():
    return [json.loads(line) for line in RECORDS.read_text().splitlines() if line.strip()]


def chat_bodies():
    return [r["body"] for r in records() if r["path"].endswith("/chat/completions")]


def decoded(content):
    """A tool result as text: hermes hands most of them over as JSON, the
    terminal's as {"output": …}."""
    text = str(content)
    try:
        value = json.loads(text)
    except ValueError:
        return text
    if isinstance(value, dict) and isinstance(value.get("output"), str):
        return value["output"]
    return json.dumps(value, indent=1)


def tool_results(body):
    return {m.get("tool_call_id"): decoded(m.get("content")) for m in body.get("messages", []) if m.get("role") == "tool"}


def conversation():
    """The agent's own conversation: the request carrying the most tool results
    (hermes also sends side requests, a session title for one, without them)."""
    return max(chat_bodies(), key=lambda body: len(tool_results(body)))


def secrets():
    values = {name: f"hermes-canary-{name.lower()}" for name in VARIABLES}
    key_lines = [line for line in PRIVATE_KEY.splitlines() if line and "PRIVATE KEY" not in line]
    values.update({f"private key line {i}": line for i, line in enumerate(key_lines)})
    return values


def test_every_probe_step_ran():
    results = tool_results(conversation())
    for call, result in sorted(results.items()):
        print(f"===== {call}\n{result}")
    assert set(results) == {"call_0", "call_1"}, results.keys()
    # the probe skill was found and loaded, so hermes registered what it asks for
    skill = json.loads(results["call_0"])
    assert skill.get("success") is True, results["call_0"]
    assert skill.get("name") == "isolation-probe", results["call_0"]
    terminal = results["call_1"]
    assert "== env" in terminal and "== canary search" in terminal and "== end" in terminal, terminal[-2000:]
    assert "PATH=" in terminal


def test_no_secret_reaches_the_agent():
    seen = "\n".join(json.dumps(body) for body in chat_bodies())
    leaked = [name for name, value in secrets().items() if value in seen]
    assert not leaked, f"the agent saw: {leaked}"


def test_gateway_uses_its_litellm_key():
    """The gateway holds LITELLM_API_KEY (a Docker secret in production) and
    sends it to the endpoint; test_no_secret_reaches_the_agent shows the agent
    never sees it."""
    sent = {r["authorization"] for r in records() if r["path"].endswith("/chat/completions")}
    assert sent == {"Bearer hermes-canary-litellm_api_key"}, sent


def test_sandbox_cannot_reach_the_dashboard():
    terminal = tool_results(conversation())["call_1"]
    dashboard = terminal.split("== dashboard", 1)[1].split("== canary search", 1)[0]
    assert "dashboard unreachable" in dashboard, dashboard


def test_agent_is_told_never_to_ask_for_a_secret():
    system = " ".join(str(m.get("content")) for m in conversation().get("messages", [])
                      if m.get("role") == "system")
    assert "Never ask the user for a password, token, API key or private key" in system
    assert "first warn that it becomes part of this conversation" in system


def test_no_private_key_in_the_sandbox():
    terminal = tool_results(conversation())["call_1"]
    search = terminal.split("== canary search", 1)[1].split("== end", 1)[0]
    assert search.strip() == "", f"files in the sandbox with a canary or a private key:\n{search}"
