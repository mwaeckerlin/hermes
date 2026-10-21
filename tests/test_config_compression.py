"""The model of the context compression, rendered from the environment with
the renderer and the template the gateway image ships."""

import os
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

yaml = YAML(typ="safe")
ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "files" / "render-config.py"
CONFIG = ROOT / "files" / "config.yaml.j2"
PROVIDER_KEYS = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY")

# the provider key the operator sets, and what the compression gets without HERMES_COMPRESSION_MODEL
DEFAULTS = [
    ({"OPENROUTER_API_KEY": "or-key"}, {"provider": "main"}),
    ({"ANTHROPIC_API_KEY": "ant-key"}, {"provider": "anthropic", "model": "claude-haiku-4-5"}),
    ({"GOOGLE_API_KEY": "g-key"}, {"provider": "gemini", "model": "gemini-2.0-flash"}),
    ({"GEMINI_API_KEY": "g-key"}, {"provider": "gemini", "model": "gemini-2.0-flash"}),
    ({"OPENAI_API_KEY": "oa-key"}, {"base_url": "https://api.openai.com/v1", "model": "o4-mini"}),
    ({"LITELLM_BASE_URL": "http://litellm:4000"}, {"base_url": "http://litellm:4000", "model": "gpt-4o-mini", "key_env": "LITELLM_API_KEY"}),
    ({"LITELLM_BASE_URL": "http://litellm:4000", "LITELLM_DEFAULT_MODEL": "local/model"}, {"base_url": "http://litellm:4000", "model": "local/model", "key_env": "LITELLM_API_KEY"}),
    ({}, {"provider": "auto"}),
]


def compression(tmp_path, **extra_env):
    output = tmp_path / "config.yaml"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "LITELLM_", "HINDSIGHT_")) and k not in PROVIDER_KEYS}
    env.update({"TERMINAL_SSH_KEY": "/tmp/test-key", "HERMES_DEFAULT_MODEL": "test/model"})
    env.update(extra_env)
    subprocess.run([os.sys.executable, str(RENDER), str(CONFIG), str(output)],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)
    return yaml.load(output.read_text())["auxiliary"]["compression"]


@pytest.mark.parametrize("provider_env, expected", DEFAULTS)
def test_compression_model_defaults_per_provider(tmp_path, provider_env, expected):
    assert compression(tmp_path, **provider_env) == expected


@pytest.mark.parametrize("provider_env, expected", DEFAULTS)
def test_compression_model_from_the_environment(tmp_path, provider_env, expected):
    assert compression(tmp_path, HERMES_COMPRESSION_MODEL="vendor/compressor", **provider_env) == {**expected, "model": "vendor/compressor"}


def test_compression_model_cannot_inject_keys(tmp_path):
    hostile = 'x"\n    provider: "evil'

    assert compression(tmp_path, ANTHROPIC_API_KEY="ant-key", HERMES_COMPRESSION_MODEL=hostile) == {"provider": "anthropic", "model": hostile}
