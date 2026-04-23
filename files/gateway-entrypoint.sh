#!/bin/sh -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"

echo "==== Reading Docker Secrets ===="
for secret in /run/secrets/*; do
  test -e "$secret" || continue
  varname=$(basename "$secret" | tr '[:lower:]-' '[:upper:]_')
  echo "Setting $varname from $secret"
  export "$varname=$(sed -z 's/\n/\\n/g' "$secret")"
done

echo "==== Setting Derived Variables ===="
# Whisper/TTS: VOICE_TOOLS_OPENAI_KEY is Hermes's real env var for voice features.
# Fall back to OPENAI_API_KEY if not set separately.
if [ -z "$VOICE_TOOLS_OPENAI_KEY" ] && [ -n "$OPENAI_API_KEY" ]; then
  export VOICE_TOOLS_OPENAI_KEY="$OPENAI_API_KEY"
  echo "VOICE_TOOLS_OPENAI_KEY set from OPENAI_API_KEY"
fi

# Auto-select default model based on available API keys (overridable via HERMES_DEFAULT_MODEL).
if [ -z "$HERMES_DEFAULT_MODEL" ]; then
  if [ -n "$OPENROUTER_API_KEY" ]; then
    export HERMES_DEFAULT_MODEL="openrouter/anthropic/claude-opus-4.6"
  elif [ -n "$ANTHROPIC_API_KEY" ]; then
    export HERMES_DEFAULT_MODEL="anthropic/claude-opus-4.6"
  elif [ -n "$GOOGLE_API_KEY" ] || [ -n "$GEMINI_API_KEY" ]; then
    export HERMES_DEFAULT_MODEL="gemini/gemini-2.5-pro"
  else
    export HERMES_DEFAULT_MODEL="openai/gpt-4o"
  fi
  echo "HERMES_DEFAULT_MODEL auto-selected: $HERMES_DEFAULT_MODEL"
fi

echo "==== Setting Up SSH Key for Sandbox ===="
if [ -z "$HERMES_SANDBOX_SSH_PRIVATE_KEY" ]; then
  echo "ERROR: HERMES_SANDBOX_SSH_PRIVATE_KEY is not set." >&2
  echo "       Provide it as an environment variable or as Docker secret hermes_sandbox_ssh_private_key." >&2
  exit 1
fi
mkdir -p "${HERMES_HOME}/.ssh"
printf '%b' "${HERMES_SANDBOX_SSH_PRIVATE_KEY}" > "${HERMES_HOME}/.ssh/hermes-sandbox"
chmod 600 "${HERMES_HOME}/.ssh/hermes-sandbox"
# TERMINAL_SSH_KEY is the env var Hermes reads for the SSH private key path.
export TERMINAL_SSH_KEY="${HERMES_HOME}/.ssh/hermes-sandbox"

echo "==== Rendering Jinja2 Configuration ===="
/opt/hermes/.venv/bin/python3 /render-config.py \
  /config.yaml.j2.default \
  "${HERMES_HOME}/config.yaml.rendered"

echo "==== Configuring Hermes ===="
if [ -n "$OVERWRITE_CONFIG" ] || [ ! -e "${HERMES_HOME}/config.yaml" ]; then
  cp "${HERMES_HOME}/config.yaml.rendered" "${HERMES_HOME}/config.yaml"
  echo "config.yaml written"
fi

echo "==== Cleaning Up Stale PID Files ===="
find "${HERMES_HOME}" -maxdepth 3 -name "*.pid" -delete 2>/dev/null || true

echo "==== Starting Hermes Gateway ===="
exec /opt/hermes/docker/entrypoint.sh "$@"
