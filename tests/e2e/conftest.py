"""Select hermes' dependency environment before the tests import a plugin.

hermes installs a plugin's Python dependencies into an environment of
HERMES_HOME and selects it when a hermes process boots
(pm.environments.activate_dependencies); the pytest process boots from the
image's base environment, so it selects the same one here, before any plugin
import.
"""
from pm.environments import activate_dependencies
from pm.paths import install_root

activate_dependencies(install_root())
