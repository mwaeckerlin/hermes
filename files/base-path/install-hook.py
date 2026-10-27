"""Installs the base path hook into the hermes virtualenv and checks it.

Run by Dockerfile.dashboard with the virtualenv's python:

    install-hook.py <hermes directory> <hook directory> <dashboard bundle directory>

1. The upstream contract the hook relies on: the dashboard reads the header
   X-Forwarded-Prefix and writes it into the page. Every text is counted, so
   a changed upstream stops the build and names the file and the text.
2. The preload helper of the dashboard bundle: Vite builds it for the base
   "/" and preloads every dependency of a lazily loaded page from "/" + file;
   it gets the base path the page carries in window.__HERMES_BASE_PATH__,
   which is empty at the root.
3. hermes-base-path.pth in the site-packages of the virtualenv, which puts
   the hook directory on the path and calls hermes_base_path.install() at the
   start of every python of the virtualenv.
4. A fresh python of the virtualenv with HERMES_BASE_PATH set serves uvicorn's
   application through BasePathApp; without the variable, it does not.
"""
import os
import re
import subprocess
import sys
import sysconfig
from pathlib import Path

PTH = "hermes-base-path.pth"

# file below the hermes directory, text upstream carries, the counts allowed
CONTRACT = [
    ("hermes_cli/dashboard_auth/prefix.py", 'request.headers.get("x-forwarded-prefix")', (1,)),
    ("hermes_cli/web_server_dashboard.py", 'request.headers.get("x-forwarded-prefix")', (2,)),
    ("hermes_cli/web_server_dashboard.py", "window.__HERMES_BASE_PATH__=\"{prefix}\";", (1,)),
    ("hermes_cli/dashboard_auth/middleware.py", 'f"{prefix}/login', (2,)),
]

# Vite's preload helper for the base "/": `const scriptRel = 'modulepreload';
# const assetsURL = function(dep) { return "/"+dep }`, minified by rolldown to
# `t=`modulepreload`,n=function(e){return`/`+e}`
PRELOAD_HELPER = re.compile(
    r"(?P<head>([\"'`])modulepreload\2\s*[,;]\s*(?:(?:const|let|var)\s+)?[A-Za-z_$][\w$]*\s*=\s*)"
    r"function\s*\(\s*(?P<dep>[A-Za-z_$][\w$]*)\s*\)\s*\{\s*return\s*([\"'`])/\4\s*\+\s*(?P=dep)\s*;?\s*\}"
)
PRELOAD_BASE = 'window.__HERMES_BASE_PATH__||""'

CHECK = """
import uvicorn.config
from hermes_base_path import BasePathApp
async def app(scope, receive, send):
    pass
config = uvicorn.config.Config(app)
config.load()
print(isinstance(config.loaded_app, BasePathApp))
"""


class InstallError(Exception):
    pass


def check_contract(hermes):
    findings = []
    for file, text, allowed in CONTRACT:
        path = hermes / file
        try:
            found = path.read_text(encoding="utf-8").count(text)
        except OSError as error:
            findings.append(f"{path} cannot be read: {error.strerror}")
            continue
        if found not in allowed:
            findings.append(
                f"{path} carries {text!r} {found} times instead of {' or '.join(map(str, allowed))}; "
                "upstream changed how the dashboard serves below a path, check whether the hook still applies"
            )
    if findings:
        raise InstallError("\n".join(findings))


def patch_preload_helper(web_dist):
    """Puts window.__HERMES_BASE_PATH__ in front of every URL the preload
    helper of the dashboard bundle builds; returns the patched file."""
    assets = web_dist / "assets"
    found = []
    for script in sorted(assets.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        count = len(PRELOAD_HELPER.findall(text))
        if count:
            found.append((script, text, count))
    total = sum(count for _, _, count in found)
    if total != 1:
        where = ", ".join(f"{script.name} ({count})" for script, _, count in found) or "no script"
        raise InstallError(
            f"the scripts in {assets} carry the preload helper of Vite for the base \"/\", "
            f"'function(e){{return\"/\"+e}}' after 'modulepreload', {total} times instead of 1 ({where}); "
            "upstream changed how its bundle preloads a page, check whether the patch still applies"
        )
    script, text, _ = found[0]
    patched = PRELOAD_HELPER.sub(
        lambda match: f'{match["head"]}function({match["dep"]}){{return({PRELOAD_BASE})+"/"+{match["dep"]}}}', text
    )
    script.write_text(patched, encoding="utf-8")
    return script


def write_pth(hook):
    site = Path(sysconfig.get_paths()["purelib"])
    (site / PTH).write_text(f"{hook}\nimport hermes_base_path; hermes_base_path.install()\n", encoding="utf-8")
    return site / PTH


def served_below_base_path(base_path):
    environ = {key: value for key, value in os.environ.items() if key != "HERMES_BASE_PATH"}
    if base_path is not None:
        environ["HERMES_BASE_PATH"] = base_path
    result = subprocess.run([sys.executable, "-c", CHECK], env=environ, capture_output=True, text=True)
    if result.returncode != 0:
        raise InstallError(f"the check of the hook failed with HERMES_BASE_PATH={base_path!r}:\n{result.stderr}")
    return result.stdout.strip() == "True"


def main(argv):
    if len(argv) != 4 or not argv[3]:
        raise InstallError("usage: install-hook.py <hermes directory> <hook directory> <dashboard bundle directory>")
    hermes, hook, web_dist = Path(argv[1]), Path(argv[2]), Path(argv[3])
    check_contract(hermes)
    helper = patch_preload_helper(web_dist)
    print(f"install-hook: {helper} preloads below window.__HERMES_BASE_PATH__")
    pth = write_pth(hook)
    if not served_below_base_path("/hermes"):
        raise InstallError(f"{pth} is installed, but uvicorn does not serve through BasePathApp with HERMES_BASE_PATH=/hermes")
    if served_below_base_path(None):
        raise InstallError(f"{pth} is installed, and uvicorn serves through BasePathApp without HERMES_BASE_PATH")
    print(f"install-hook: {pth} serves the dashboard below HERMES_BASE_PATH")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except InstallError as error:
        sys.exit(f"install-hook: {error}")
