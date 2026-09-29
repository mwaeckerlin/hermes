#!/usr/bin/env python3
"""Refuse a gateway configuration that would hand a secret to the agent.

Usage: check-isolation.py <config.yaml>

The agent's tools run in the sandbox; the gateway holds the secrets. hermes
can cross that line in three ways, each of them set in config.yaml:

- terminal.env_passthrough: gateway variables sent to every sandbox command
- terminal.credential_files: gateway files copied into the sandbox
- an mcp_servers entry with `command`: a server started inside the gateway,
  with the gateway's environment, whose input the agent controls

Any of them stops the start with a message naming the setting. MCP servers
are reached by `url`, in a container of their own.
"""
import sys

import yaml

config = yaml.safe_load(open(sys.argv[1])) or {}
terminal = config.get("terminal") or {}
problems = []
if terminal.get("env_passthrough"):
    problems.append(f"terminal.env_passthrough {terminal['env_passthrough']!r} would send gateway variables into the sandbox")
if terminal.get("credential_files"):
    problems.append(f"terminal.credential_files {terminal['credential_files']!r} would copy gateway files into the sandbox")
for name, server in (config.get("mcp_servers") or {}).items():
    if isinstance(server, dict) and server.get("command"):
        problems.append(f"mcp_servers.{name} runs `{server['command']}` inside the gateway, with its secrets; "
                        "run the server in a container of its own and give its url")
if problems:
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)
    sys.exit(1)
print("Isolation: no gateway variable, file or local MCP server reaches the agent")
