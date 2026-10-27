"""Serves the Hermes dashboard below HERMES_BASE_PATH, such as /hermes.

Every Python process of the hermes virtualenv imports this module through
hermes-base-path.pth and calls install(). Without HERMES_BASE_PATH it returns
at once and nothing changes. With it, the uvicorn server of the dashboard
serves its application through BasePathApp.

Upstream already serves below a path when a proxy strips that path and names
it in the header X-Forwarded-Prefix: it writes the prefix into the page, the
asset URLs, the stylesheets, the login page, the cookies and its redirects,
and the browser bundle builds every API call, websocket and route from it.
BasePathApp takes the place of that proxy inside the image: it takes the base
path off every HTTP request and websocket below it and sets X-Forwarded-Prefix
to the base path, so the reverse proxy forwards the path unchanged.
"""
import importlib.abc
import importlib.util
import os
import sys
from urllib.parse import urlsplit, urlunsplit

VARIABLE = "HERMES_BASE_PATH"
PREFIX_HEADER = b"x-forwarded-prefix"
_SEGMENT_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-")


class ConfigurationError(Exception):
    pass


def parse_base_path(value):
    """"" for the root, otherwise "/segment[/segment...]" without a trailing slash."""
    raw = (value or "").strip()
    if raw in ("", "/"):
        return ""
    trimmed = raw.rstrip("/")
    segments = trimmed.split("/")
    valid = (
        len(segments) >= 2
        and segments[0] == ""
        and all(segment and set(segment) <= _SEGMENT_CHARACTERS and segment not in (".", "..") for segment in segments[1:])
    )
    if not valid:
        raise ConfigurationError(
            f"{VARIABLE} is {value!r}; it must be a path such as /hermes: "
            "a leading slash, then segments of letters, digits, '.', '_', '~' and '-'"
        )
    return trimmed


def route_path(path, base):
    """Where a request path lies relative to the base path: ("inside", path
    below it), ("bare", None) or ("outside", path unchanged)."""
    if not base or not path.startswith("/"):
        return "outside", path
    if path == base:
        return "bare", None
    if path.startswith(base + "/"):
        return "inside", path[len(base):]
    return "outside", path


def _below(path, base):
    return path == base or path.startswith(base + "/")


def prefix_location(value, base, host=""):
    """A redirect to an address of hermes itself gets the base path in front:
    a root-absolute path, or an absolute URL of the host the request named.
    An address already below the base path and a foreign address stay."""
    if not base or not value:
        return value
    if value.startswith("/"):
        if value.startswith("//") or value.startswith("/\\"):
            return value
        parts = urlsplit(value)
        return value if _below(parts.path, base) else base + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not host or parts.netloc.lower() != host.lower():
        return value
    if _below(parts.path or "/", base):
        return value
    return urlunsplit(parts._replace(path=base + (parts.path or "/")))


class BasePathApp:
    """ASGI application in front of the dashboard (see the module comment).

    Requests outside the base path reach the dashboard unchanged, at the root,
    as the dashboard's own self-test and clients inside the container address
    it. A client's own X-Forwarded-Prefix never reaches the dashboard: the
    image alone decides the prefix."""

    def __init__(self, app, base):
        self.app = app
        self.base = base

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = [(name, value) for name, value in scope.get("headers", []) if name.lower() != PREFIX_HEADER]
        kind, path = route_path(scope["path"], self.base)
        if kind == "bare":
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            query = scope.get("query_string", b"").decode("latin-1")
            location = self.base + "/" + (f"?{query}" if query else "")
            await send({"type": "http.response.start", "status": 308,
                        "headers": [(b"location", location.encode("latin-1")), (b"content-length", b"0")]})
            return await send({"type": "http.response.body", "body": b""})
        scope = dict(scope, headers=headers)
        if kind == "inside":
            scope["path"] = path
            raw_path = scope.get("raw_path")
            if raw_path is not None and raw_path.startswith(self.base.encode("ascii") + b"/"):
                scope["raw_path"] = raw_path[len(self.base):]
            scope["headers"] = headers + [(PREFIX_HEADER, self.base.encode("ascii"))]
            if scope["type"] == "http":
                send = self._prefix_redirects(send, headers)
        return await self.app(scope, receive, send)

    def _prefix_redirects(self, send, headers):
        host = next((value.decode("latin-1") for name, value in headers if name.lower() == b"host"), "")

        async def prefixed(message):
            if message["type"] == "http.response.start":
                message = dict(message, headers=[
                    (name, prefix_location(value.decode("latin-1"), self.base, host).encode("latin-1"))
                    if name.lower() == b"location" else (name, value)
                    for name, value in message.get("headers", [])
                ])
            return await send(message)

        return prefixed


def _wrap_config(config_class, base, error):
    """Config.load resolves the application uvicorn serves; BasePathApp goes in
    front of it. A wrong HERMES_BASE_PATH stops the start of the server."""
    if getattr(config_class.load, "hermes_base_path", False):
        return
    load = config_class.load

    def load_below_base_path(self, *args, **kwargs):
        if error is not None:
            raise SystemExit(f"hermes-dashboard: configuration error: {error}")
        result = load(self, *args, **kwargs)
        if not isinstance(self.loaded_app, BasePathApp):
            self.loaded_app = BasePathApp(self.loaded_app, base)
            print(f"hermes-dashboard: serving below {base}/", file=sys.stderr, flush=True)
        return result

    load_below_base_path.hermes_base_path = True
    config_class.load = load_below_base_path


class _UvicornConfigHook(importlib.abc.MetaPathFinder):
    """Wraps uvicorn.config.Config once the dashboard imports it."""

    def __init__(self, base, error):
        self.base = base
        self.error = error

    def find_spec(self, name, path=None, target=None):
        if name != "uvicorn.config":
            return None
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(name)
        if spec is None or spec.loader is None:
            return spec
        exec_module = spec.loader.exec_module
        base, error = self.base, self.error

        def exec_and_wrap(module):
            exec_module(module)
            _wrap_config(module.Config, base, error)

        spec.loader.exec_module = exec_and_wrap
        return spec


def install(environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get(VARIABLE, "")
    if not value.strip():
        return
    try:
        base, error = parse_base_path(value), None
    except ConfigurationError as wrong:
        base, error = "", wrong
    if not base and error is None:
        return
    config = sys.modules.get("uvicorn.config")
    if config is not None:
        _wrap_config(config.Config, base, error)
    elif not any(isinstance(finder, _UvicornConfigHook) for finder in sys.meta_path):
        sys.meta_path.insert(0, _UvicornConfigHook(base, error))
