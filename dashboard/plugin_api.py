"""Hermes file loader entry; load a path-scoped package without sys.path changes."""

import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "backend"
package_name = "hermes_usage_manager_backend_" + hashlib.sha256(str(root).encode()).hexdigest()[:12]
if package_name not in sys.modules:
    spec = importlib.util.spec_from_file_location(package_name, root / "__init__.py", submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
api = importlib.import_module(package_name + ".api")
router = api.router
data_source = api.data_source
get_runtime = api.get_runtime
get_principal = api.get_principal
Runtime = api.Runtime
