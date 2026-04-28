"""Tests for mcp-gitea integration in the sandbox entrypoint."""
import re
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[1] / "files" / "sandbox-entrypoint.sh"
COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def test_entrypoint_exports_mcp_gitea_url():
    """sandbox-entrypoint.sh must export MCP_GITEA_URL to /etc/environment."""
    script = ENTRYPOINT.read_text()
    assert "MCP_GITEA_URL" in script
    assert "/etc/environment" in script
    # The export block mirrors the MCP_GITHUB_URL pattern
    assert re.search(
        r'MCP_GITEA_URL=\$\{MCP_GITEA_URL\}.*>>.*/etc/environment',
        script,
    ), "Expected 'echo MCP_GITEA_URL=... >> /etc/environment' pattern"


def test_compose_defines_mcp_gitea_service():
    """docker-compose.yml must define an mcp-gitea service."""
    compose = COMPOSE.read_text()
    assert "mcp-gitea:" in compose


def test_compose_mcp_gitea_has_gitea_token():
    """mcp-gitea service must pass GITEA_TOKEN for authentication."""
    compose = COMPOSE.read_text()
    # GITEA_TOKEN should appear as an environment variable
    assert "GITEA_TOKEN" in compose


def test_compose_mcp_gitea_has_gitea_url():
    """mcp-gitea service must accept GITEA_URL for the Gitea instance."""
    compose = COMPOSE.read_text()
    assert "GITEA_URL" in compose


def test_compose_sandbox_receives_mcp_gitea_url():
    """hermes-sandbox must have MCP_GITEA_URL in its environment."""
    compose = COMPOSE.read_text()
    assert "MCP_GITEA_URL" in compose


def test_compose_sandbox_mcp_gitea_network_defined():
    """sandbox-mcp-gitea network must be declared."""
    compose = COMPOSE.read_text()
    assert "sandbox-mcp-gitea" in compose
