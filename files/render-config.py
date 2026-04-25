#!/usr/bin/env python3
"""Render a Jinja2 config.yaml template with environment variable context.

Invoked by gateway-entrypoint.sh as:
  /opt/hermes/.venv/bin/python3 /render-config.py <template> <output>

jinja2 is a core dependency of hermes-agent (pyproject.toml) and is always
available inside the hermes virtualenv.
"""
import os
import sys

try:
    from jinja2 import Environment, BaseLoader, Undefined
except ImportError:
    print("ERROR: jinja2 not found. Run using /opt/hermes/.venv/bin/python3", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <template_file> <output_file>", file=sys.stderr)
    sys.exit(1)

template_file = sys.argv[1]
output_file = sys.argv[2]

with open(template_file) as fh:
    template_str = fh.read()

env = Environment(
    loader=BaseLoader(),
    autoescape=False,
    keep_trailing_newline=True,
    undefined=Undefined,
)

template = env.from_string(template_str)
context = dict(os.environ)
rendered = template.render(context)

with open(output_file, "w") as fh:
    fh.write(rendered)

print(f"Configuration rendered: {template_file} -> {output_file}")
