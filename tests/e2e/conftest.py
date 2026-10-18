"""Select hermes' dependency environment before the tests import a plugin.

hermes installs a plugin's Python dependencies into an environment of
HERMES_HOME and selects it when a hermes process boots
(pm.environments.activate_dependencies); the pytest process boots from the
image's base environment, so it selects the same one here, before any plugin
import.

activate_dependencies takes every site-packages directory off sys.path and
puts the selected environment in front. pytest and pluggy live in the base
environment, so pytest no longer found pluggy's metadata and stopped at the
start («No package metadata was found for pluggy», measured 2026-10-18 with
pm/environments.py lines 495-497). The base directories go back behind the
selected environment: the plugin's dependencies still win, and pytest finds
its own.
"""
import sys

from pm.environments import activate_dependencies
from pm.paths import install_root

_base_paths = [entry for entry in sys.path if entry.endswith(("site-packages", "dist-packages"))]
activate_dependencies(install_root())
sys.path.extend(entry for entry in _base_paths if entry not in sys.path)
