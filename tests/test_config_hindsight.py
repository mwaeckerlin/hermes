"""Hindsight memory and LiteLLM settings rendered from the environment, with
the renderer and the templates the gateway image ships."""

import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "files" / "render-config.py"
CONFIG = ROOT / "files" / "config.yaml.j2"
HINDSIGHT = ROOT / "files" / "hindsight-config.json.j2"


def render(template, tmp_path, **extra_env):
    output = tmp_path / "out"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HINDSIGHT_", "HERMES_", "LITELLM_"))}
    env.update({"TERMINAL_SSH_KEY": "/tmp/test-key", "HERMES_DEFAULT_MODEL": "test/model"})
    env.update(extra_env)
    subprocess.run([os.sys.executable, str(RENDER), str(template), str(output)],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)
    return output.read_text()


def test_memory_provider_from_environment(tmp_path):
    config = yaml.safe_load(render(CONFIG, tmp_path, HERMES_MEMORY_PROVIDER="hindsight"))

    assert config["memory"]["provider"] == "hindsight"
    assert config["memory"]["memory_enabled"] is True


def test_no_memory_provider_by_default(tmp_path):
    config = yaml.safe_load(render(CONFIG, tmp_path))

    assert "provider" not in config["memory"]


def test_shared_bank_rendered_as_mcp_server(tmp_path):
    url = "http://hindsight-proxy:8888/mcp/shared/"
    config = yaml.safe_load(render(CONFIG, tmp_path, HINDSIGHT_SHARED_MCP_URL=url))

    assert config["mcp_servers"] == {"hindsight-shared": {"url": url}}


def test_shared_bank_joins_explicit_mcp_servers(tmp_path):
    url = "http://hindsight-proxy:8888/mcp/shared/"
    config = yaml.safe_load(render(
        CONFIG, tmp_path,
        HINDSIGHT_SHARED_MCP_URL=url,
        HERMES_MCP_SERVERS_YAML='{"github":{"url":"http://mcp-github:4000/mcp"}}',
    ))

    assert config["mcp_servers"]["hindsight-shared"] == {"url": url}
    assert config["mcp_servers"]["github"] == {"url": "http://mcp-github:4000/mcp"}


def test_no_mcp_servers_by_default(tmp_path):
    config = yaml.safe_load(render(CONFIG, tmp_path))

    assert "mcp_servers" not in config


def test_hindsight_defaults_to_external_server_and_hybrid_mode(tmp_path):
    settings = json.loads(render(HINDSIGHT, tmp_path))

    assert settings["mode"] == "local_external"
    assert settings["memory_mode"] == "hybrid"
    assert settings["bank_id"] == "hermes"
    assert settings["api_url"] == "http://localhost:8888"


def test_hindsight_settings_from_environment(tmp_path):
    settings = json.loads(render(
        HINDSIGHT, tmp_path,
        HINDSIGHT_API_URL="http://hindsight-proxy:8888",
        HINDSIGHT_BANK_ID="hermes-own",
        HINDSIGHT_MEMORY_MODE="tools",
        HINDSIGHT_BUDGET="high",
        HINDSIGHT_RETAIN_TAGS="hermes,agent",
    ))

    assert settings["api_url"] == "http://hindsight-proxy:8888"
    assert settings["bank_id"] == "hermes-own"
    assert settings["memory_mode"] == "tools"
    assert settings["recall_budget"] == "high"
    assert settings["retain_tags"] == "hermes,agent"


def test_hindsight_settings_never_hold_a_key(tmp_path):
    text = render(HINDSIGHT, tmp_path, HINDSIGHT_API_KEY="secret-value-123")

    assert "secret-value-123" not in text
    assert "apiKey" not in json.loads(text)
    assert "api_key" not in json.loads(text)


def test_litellm_base_url_alone_selects_litellm(tmp_path):
    config = yaml.safe_load(render(CONFIG, tmp_path, LITELLM_BASE_URL="http://litellm-proxy:4000/v1"))

    assert config["model"]["base_url"] == "http://litellm-proxy:4000/v1"


def test_litellm_key_is_named_never_written(tmp_path):
    text = render(CONFIG, tmp_path, LITELLM_BASE_URL="http://litellm:4000/v1", LITELLM_API_KEY="litellm-secret-123")
    config = yaml.safe_load(text)

    assert "litellm-secret-123" not in text
    assert config["model"]["key_env"] == "LITELLM_API_KEY"
    assert config["auxiliary"]["compression"]["key_env"] == "LITELLM_API_KEY"
    assert config["auxiliary"]["vision"]["key_env"] == "LITELLM_API_KEY"
