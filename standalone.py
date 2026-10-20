import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent / 'backend'
    name = 'hermes_usage_manager_backend_' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        spec.loader.exec_module(package)
    importlib.import_module(name + '.standalone').main()


if __name__ == '__main__':
    main()
