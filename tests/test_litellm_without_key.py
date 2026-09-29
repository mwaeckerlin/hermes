"""The gateway calls an OpenAI-compatible endpoint (LiteLLM, or the proxy in
front of it) given by LITELLM_BASE_URL alone, and holds no real key.

The endpoint here stands where the proxy stands in the deployment: it records
every request hermes sends and answers like LiteLLM. What the test measures is
the request hermes itself sends, with the real hermes CLI of the image.
"""

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "files" / "render-config.py"
CONFIG = ROOT / "files" / "config.yaml.j2"
HERMES = "/opt/hermes/.venv/bin/hermes"
ANSWER = "pong from the proxy"
KEY_VARIABLES = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                 "GEMINI_API_KEY", "LITELLM_API_KEY")


class Recorder(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def _send(self, body, content_type="application/json"):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Recorder.requests.append(("GET", self.path, self.headers.get("Authorization")))
        self._send(json.dumps({"object": "list", "data": [{"id": "test-model", "object": "model"}]}))

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        Recorder.requests.append(("POST", self.path, self.headers.get("Authorization")))
        message = {"role": "assistant", "content": ANSWER}
        if body.get("stream"):
            chunks = [
                {"id": "1", "object": "chat.completion.chunk", "model": "test-model",
                 "choices": [{"index": 0, "delta": message, "finish_reason": None}]},
                {"id": "1", "object": "chat.completion.chunk", "model": "test-model",
                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            self._send("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n",
                       "text/event-stream")
        else:
            self._send(json.dumps({
                "id": "1", "object": "chat.completion", "model": "test-model",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }))


def test_request_reaches_litellm_without_a_real_key(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}/v1"
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in KEY_VARIABLES and not k.startswith(("HERMES_", "LITELLM_", "HINDSIGHT_"))}
    env.update({"HERMES_HOME": str(home), "HOME": str(tmp_path), "TERMINAL_SSH_KEY": "/tmp/test-key",
                "LITELLM_BASE_URL": base_url, "LITELLM_DEFAULT_MODEL": "test-model",
                "HERMES_DEFAULT_MODEL": "test-model"})
    subprocess.run([os.sys.executable, str(RENDER), str(CONFIG), str(home / "config.yaml")],
                   check=True, cwd=ROOT, env=env, capture_output=True, text=True)
    try:
        result = subprocess.run([HERMES, "-z", "ping"], env=env, capture_output=True, text=True, timeout=180)
    finally:
        server.shutdown()
        server.server_close()

    chat = [r for r in Recorder.requests if r[0] == "POST" and r[1].endswith("/chat/completions")]
    assert chat, f"no chat request reached the endpoint; stdout={result.stdout!r} stderr={result.stderr[-2000:]!r}"
    assert ANSWER in result.stdout
    print("requests hermes sent (method, path, Authorization):", Recorder.requests)
    # no key in the container: the chat request carries hermes' fixed
    # placeholder, which the proxy replaces; nothing else carries a key
    assert {r[2] for r in chat} == {"Bearer no-key-required"}
    assert {r[2] for r in Recorder.requests} <= {None, "Bearer no-key-required"}
