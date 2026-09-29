"""The gateway refuses a configuration that would hand a secret to the agent:
variables or files passed into the sandbox, or an MCP server run inside the
gateway. The check and the template are the ones the gateway image ships."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "files" / "render-config.py"
CONFIG = ROOT / "files" / "config.yaml.j2"
CHECK = ROOT / "files" / "check-isolation.py"


def check(tmp_path, **extra_env):
    config = tmp_path / "config.yaml"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "HINDSIGHT_", "LITELLM_"))}
    env.update({"TERMINAL_SSH_KEY": "/run/hermes-ssh/hermes-sandbox", "HERMES_DEFAULT_MODEL": "test/model"})
    env.update(extra_env)
    subprocess.run([os.sys.executable, str(RENDER), str(CONFIG), str(config)],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)
    return subprocess.run([os.sys.executable, str(CHECK), str(config)], capture_output=True, text=True)


def test_default_configuration_passes(tmp_path):
    result = check(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "no gateway variable, file or local MCP server reaches the agent" in result.stdout


def test_remote_mcp_servers_pass(tmp_path):
    result = check(tmp_path, HINDSIGHT_SHARED_MCP_URL="http://hindsight:8888/mcp/shared/",
                   HERMES_MCP_SERVERS_YAML='{"github":{"url":"http://mcp-github:4000/mcp"}}')

    assert result.returncode == 0, result.stderr


def test_env_passthrough_is_refused(tmp_path):
    result = check(tmp_path, HERMES_TERMINAL_YAML='{"backend":"ssh","env_passthrough":["HINDSIGHT_API_KEY"]}')

    assert result.returncode == 1
    assert "terminal.env_passthrough" in result.stderr


def test_credential_files_are_refused(tmp_path):
    result = check(tmp_path, HERMES_TERMINAL_YAML='{"backend":"ssh","credential_files":["hindsight/config.json"]}')

    assert result.returncode == 1
    assert "terminal.credential_files" in result.stderr


def test_local_mcp_server_is_refused(tmp_path):
    result = check(tmp_path, HERMES_MCP_SERVERS_YAML='{"time":{"command":"uvx","args":["mcp-server-time"]}}')

    assert result.returncode == 1
    assert "mcp_servers.time runs `uvx` inside the gateway" in result.stderr
