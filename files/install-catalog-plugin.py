#!/usr/bin/env python3
"""Install a memory provider plugin of the hermes-agent plugin catalog into the
image, at the commit the catalog of the installed hermes-agent pins.

Usage: install-catalog-plugin.py <name> [<package exempt from the quarantine> …]

hermes-agent moved its memory providers out of its own tree into their
projects and lists each one in plugin-catalog/<name>.yaml with repo, sha and
subdir. `hermes plugins install` would put the plugin into $HERMES_HOME, which
is the data volume at runtime; this script puts it where hermes looks first,
/opt/hermes/plugins/memory/<name>, so it is part of the image, and installs
the plugin's pip dependencies into the hermes virtualenv.

The dependencies resolve under hermes' own uv settings in /opt/hermes, which
hide every release younger than 14 days (`exclude-newer`). A package named
after the plugin is exempt from that window, and only that package; what it
depends on stays under the window.
"""
import io
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

import yaml

HERMES = Path("/opt/hermes")
name, exempt = sys.argv[1], sys.argv[2:]
entry = yaml.safe_load((HERMES / "plugin-catalog" / f"{name}.yaml").read_text())
owner_repo = entry["repo"].removeprefix("https://github.com/").removesuffix(".git")
target = HERMES / "plugins" / "memory" / name
print(f"{name}: {owner_repo} {entry['sha']} {entry['subdir']} -> {target}")

archive = urllib.request.urlopen(
    f"https://codeload.github.com/{owner_repo}/tar.gz/{entry['sha']}", timeout=1800).read()
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    prefix = tar.getnames()[0].split("/")[0] + "/" + entry["subdir"].strip("/") + "/"
    members = [m for m in tar.getmembers() if m.name.startswith(prefix) and "/tests/" not in m.name]
    if not members:
        sys.exit(f"{name}: {entry['subdir']} not found in {owner_repo}@{entry['sha']}")
    for member in members:
        member.name = member.name[len(prefix):]
        if member.name:
            tar.extract(member, target, filter="data")

manifest = yaml.safe_load((target / "plugin.yaml").read_text())
dependencies = manifest.get("pip_dependencies") or []
if dependencies:
    exemptions = [flag for package in exempt for flag in ("--exclude-newer-package", f"{package}=false")]
    subprocess.run(["uv", "pip", "install", "--no-cache", "--python", str(HERMES / ".venv" / "bin" / "python3"),
                    *exemptions, *dependencies], check=True, cwd=HERMES)
print(f"{name}: installed", *dependencies, *(f"(exempt from the quarantine: {p})" for p in exempt))
