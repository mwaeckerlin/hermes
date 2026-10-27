"""HERMES_BASE_PATH: parsing, the request routing of BasePathApp, the hook
that puts it in front of uvicorn's application, and the upstream contract the
dashboard build checks (files/base-path)."""
import asyncio
import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "files" / "base-path"
spec = importlib.util.spec_from_file_location("hermes_base_path", HOOK / "hermes_base_path.py")
hermes_base_path = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hermes_base_path)
spec = importlib.util.spec_from_file_location("install_hook", HOOK / "install-hook.py")
install_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_hook)


@pytest.mark.parametrize("value", [None, "", "  ", "/"])
def test_unset_or_root_serves_at_the_root(value):
    assert hermes_base_path.parse_base_path(value) == ""


@pytest.mark.parametrize("value, base", [
    ("/hermes", "/hermes"), ("/hermes/", "/hermes"), (" /hermes ", "/hermes"),
    ("/a/b-c/d_e.f~g", "/a/b-c/d_e.f~g"), ("/Hermes2", "/Hermes2"),
])
def test_base_path_is_normalised(value, base):
    assert hermes_base_path.parse_base_path(value) == base


@pytest.mark.parametrize("value", [
    "hermes", "/a b", "/x/../y", "/hermes/..", "/./x", "//x", "/x//y", "/x?y", "/x#y", "/x%2fy", '/x"y', "/x<y>", "/ü",
])
def test_wrong_base_path_names_the_variable(value):
    with pytest.raises(hermes_base_path.ConfigurationError) as wrong:
        hermes_base_path.parse_base_path(value)
    assert str(wrong.value).startswith(f"HERMES_BASE_PATH is {value!r}; it must be a path such as /hermes")


def serve(scope, base="/hermes", answer=None):
    """Runs one request through BasePathApp; returns the scope the dashboard
    saw (or None) and the messages sent back to the client."""
    seen, sent = [], []
    answer = answer or [{"type": "http.response.start", "status": 200, "headers": []},
                        {"type": "http.response.body", "body": b"ok"}]

    async def dashboard(inner, receive, send):
        seen.append(inner)
        for message in answer:
            await send(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(hermes_base_path.BasePathApp(dashboard, base)(scope, receive, send))
    return (seen[0] if seen else None), sent


def http(path, query=b"", headers=(), kind="http"):
    return {"type": kind, "path": path, "raw_path": path.encode(), "query_string": query, "root_path": "",
            "headers": [(b"host", b"proxy:8080"), *headers]}


def prefix_of(scope):
    return [value for name, value in scope["headers"] if name == b"x-forwarded-prefix"]


@pytest.mark.parametrize("kind", ["http", "websocket"])
def test_request_below_the_base_path_reaches_the_dashboard_without_it(kind):
    seen, _ = serve(http("/hermes/api/status", b"a=1", kind=kind),
                    answer=[] if kind == "websocket" else None)
    assert seen["path"] == "/api/status"
    assert seen["raw_path"] == b"/api/status"
    assert seen["query_string"] == b"a=1"
    assert seen["root_path"] == ""
    assert prefix_of(seen) == [b"/hermes"]


def test_slash_form_of_the_base_path_reaches_the_root_of_the_dashboard():
    seen, _ = serve(http("/hermes/"))
    assert seen["path"] == "/"
    assert prefix_of(seen) == [b"/hermes"]


def test_a_prefix_header_of_the_client_is_replaced():
    seen, _ = serve(http("/hermes/login", headers=[(b"X-Forwarded-Prefix", b"/elsewhere")]))
    assert prefix_of(seen) == [b"/hermes"]
    assert all(name.lower() != b"x-forwarded-prefix" or value == b"/hermes" for name, value in seen["headers"])


def test_request_outside_the_base_path_reaches_the_dashboard_at_the_root():
    seen, sent = serve(http("/login", headers=[(b"x-forwarded-prefix", b"/elsewhere")]))
    assert seen["path"] == "/login"
    assert seen["raw_path"] == b"/login"
    assert prefix_of(seen) == []
    assert sent[0]["status"] == 200


@pytest.mark.parametrize("path", ["/hermesx/api", "/hermes-other", "/other/hermes/x"])
def test_a_path_that_only_starts_like_the_base_path_lies_outside(path):
    seen, _ = serve(http(path))
    assert seen["path"] == path
    assert prefix_of(seen) == []


@pytest.mark.parametrize("query, location", [(b"", b"/hermes/"), (b"next=%2F", b"/hermes/?next=%2F")])
def test_bare_base_path_redirects_to_its_slash_form(query, location):
    seen, sent = serve(http("/hermes", query))
    assert seen is None
    assert sent[0]["status"] == 308
    assert (b"location", location) in sent[0]["headers"]
    assert sent[1] == {"type": "http.response.body", "body": b""}


def test_bare_base_path_refuses_a_websocket():
    seen, sent = serve(http("/hermes", kind="websocket"))
    assert seen is None
    assert sent == [{"type": "websocket.close", "code": 1008}]


def test_lifespan_reaches_the_dashboard_unchanged():
    scope = {"type": "lifespan"}
    seen, _ = serve(scope, answer=[])
    assert seen is scope


def redirect(location, path="/hermes/x"):
    _, sent = serve(http(path), answer=[
        {"type": "http.response.start", "status": 302, "headers": [(b"location", location), (b"set-cookie", b"a=/b")]},
        {"type": "http.response.body", "body": b""},
    ])
    return dict(sent[0]["headers"])


@pytest.mark.parametrize("location, prefixed", [
    (b"/login?next=%2F", b"/hermes/login?next=%2F"),
    (b"/", b"/hermes/"),
    (b"http://proxy:8080/api/x/", b"http://proxy:8080/hermes/api/x/"),
])
def test_redirect_of_the_dashboard_gets_the_base_path(location, prefixed):
    headers = redirect(location)
    assert headers[b"location"] == prefixed
    assert headers[b"set-cookie"] == b"a=/b"


@pytest.mark.parametrize("location", [
    b"/hermes/login", b"/hermes", b"/hermes?next=x", b"https://example.org/x", b"//cdn.example.org/x",
    b"/\\example.org", b"http://other:8080/x", b"relative/path", b"",
])
def test_prefixed_foreign_and_relative_redirects_stay(location):
    assert redirect(location)[b"location"] == location


def test_redirect_outside_the_base_path_stays():
    assert redirect(b"/login", path="/x")[b"location"] == b"/login"


FAKE_UVICORN = {
    "uvicorn/__init__.py": "from uvicorn.config import Config\n",
    "uvicorn/config.py": textwrap.dedent("""
        class Config:
            def __init__(self, app):
                self.app = app
            def load(self):
                self.loaded_app = self.app
    """),
}

RUN_HOOK = textwrap.dedent("""
    import hermes_base_path
    hermes_base_path.install()
    import uvicorn
    async def app(scope, receive, send):
        pass
    config = uvicorn.Config(app)
    config.load()
    loaded = config.loaded_app
    print(type(loaded).__name__, getattr(loaded, "base", ""), getattr(loaded, "app", None) is app)
""")


def run_hook(tmp_path, base_path):
    for name, text in FAKE_UVICORN.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    environ = {key: value for key, value in os.environ.items() if key != "HERMES_BASE_PATH"}
    environ["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(HOOK)])
    if base_path is not None:
        environ["HERMES_BASE_PATH"] = base_path
    return subprocess.run([sys.executable, "-c", RUN_HOOK], env=environ, capture_output=True, text=True, timeout=60)


def test_hook_serves_uvicorn_through_base_path_app(tmp_path):
    result = run_hook(tmp_path, "/hermes/")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["BasePathApp", "/hermes", "True"]
    assert result.stderr.count("hermes-dashboard: serving below /hermes/") == 1


@pytest.mark.parametrize("value", [None, "", "/"])
def test_hook_leaves_uvicorn_alone_without_a_base_path(tmp_path, value):
    result = run_hook(tmp_path, value)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["function", "False"]
    assert result.stderr == ""


@pytest.mark.parametrize("value", ["hermes", "/a b", "/x/../y"])
def test_hook_stops_the_start_on_a_wrong_base_path(tmp_path, value):
    result = run_hook(tmp_path, value)
    assert result.returncode == 1
    assert result.stdout == ""
    assert f"hermes-dashboard: configuration error: HERMES_BASE_PATH is {value!r}" in result.stderr


def upstream_tree(tmp_path, **changed):
    for file, text, allowed in install_hook.CONTRACT:
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write((text + "\n") * changed.get(file.rsplit("/", 1)[-1].split(".")[0], allowed[0]))
    return tmp_path


def test_upstream_contract_holds_on_the_counted_texts(tmp_path):
    install_hook.check_contract(upstream_tree(tmp_path))


def test_changed_upstream_stops_the_build_and_names_file_and_text(tmp_path):
    with pytest.raises(install_hook.InstallError) as changed:
        install_hook.check_contract(upstream_tree(tmp_path, prefix=0))
    message = str(changed.value)
    assert "hermes_cli/dashboard_auth/prefix.py carries 'request.headers.get(\"x-forwarded-prefix\")' 0 times instead of 1" in message
    assert "web_server_dashboard.py" not in message


# Vite's preload helper for the base "/", as getPreloadCode of Vite 8 writes it
# (packages/vite/src/node/plugins/importAnalysisBuild.ts, v8.2.4 and v8.3.4)
VITE_HELPER = ("const scriptRel = 'modulepreload';const assetsURL = function(dep) { return \"/\"+dep };"
               "const seen = {};export const __vitePreload = function preload(baseModule, deps, importerUrl) {")
# the same helper minified by rolldown, as a Vite 8 build publishes it
MINIFIED_HELPER = ("var t=`modulepreload`,n=function(e){return`/`+e},r={},i=function(e,i,a){let o=Promise.resolve();"
                   "if(i&&i.length>0){function u(e){return import.meta.resolve?import.meta.resolve(e):new URL(e,import.meta.url).href}"
                   "o=l(i.map(i=>{if(i=n(i,a),i=u(i),i in r)return;")


def bundle(tmp_path, *scripts):
    assets = tmp_path / "assets"
    assets.mkdir()
    for index, text in enumerate(scripts):
        (assets / f"chunk-{index}.js").write_text(text)
    (assets / "index.css").write_text('a{content:"modulepreload"}')
    return tmp_path


@pytest.mark.parametrize("helper, patched", [
    (VITE_HELPER, "const assetsURL = function(dep){return(window.__HERMES_BASE_PATH__||\"\")+\"/\"+dep};const seen = {};"),
    (MINIFIED_HELPER, "n=function(e){return(window.__HERMES_BASE_PATH__||\"\")+\"/\"+e},r={},"),
])
def test_preload_helper_builds_its_urls_below_the_base_path(tmp_path, helper, patched):
    dist = bundle(tmp_path, "export const page = `/`+x;", helper + "rest of the chunk")
    script = install_hook.patch_preload_helper(dist)
    assert script.name == "chunk-1.js"
    text = script.read_text()
    assert patched in text
    assert text.endswith("rest of the chunk")
    assert (dist / "assets" / "chunk-0.js").read_text() == "export const page = `/`+x;"


def test_bundle_without_the_preload_helper_stops_the_build(tmp_path):
    dist = bundle(tmp_path, MINIFIED_HELPER.replace("return`/`+e", "return`./`+e"), "e=>`/`+e")
    with pytest.raises(install_hook.InstallError) as changed:
        install_hook.patch_preload_helper(dist)
    assert "0 times instead of 1 (no script)" in str(changed.value)
    assert str(dist / "assets") in str(changed.value)


def test_preload_helper_twice_stops_the_build(tmp_path):
    dist = bundle(tmp_path, MINIFIED_HELPER, VITE_HELPER)
    with pytest.raises(install_hook.InstallError) as twice:
        install_hook.patch_preload_helper(dist)
    assert "2 times instead of 1 (chunk-0.js (1), chunk-1.js (1))" in str(twice.value)
    assert (dist / "assets" / "chunk-0.js").read_text() == MINIFIED_HELPER


def test_missing_upstream_file_stops_the_build(tmp_path):
    with pytest.raises(install_hook.InstallError) as missing:
        install_hook.check_contract(tmp_path)
    assert str(missing.value).count("cannot be read") == len(install_hook.CONTRACT)
