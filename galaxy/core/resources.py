from importlib import import_module
from pathlib import Path
from types import ModuleType

INTEGRATIONS_MODULE: str = "galaxy.integrations"


class IntegrationModuleNotFoundError(ModuleNotFoundError):
    def __init__(self, integration_type: str):
        super().__init__(f"Integration module not found: {integration_type}")
        self.integration_type = integration_type


def get_integration_module_name(integration_type: str) -> str:
    return f"{INTEGRATIONS_MODULE}.{integration_type}"


def load_integration_module(integration_type: str) -> ModuleType:
    try:
        return import_module(get_integration_module_name(integration_type))
    except ModuleNotFoundError:
        raise IntegrationModuleNotFoundError(integration_type)


def get_integration_resource_path(integration_type: str, filepath: Path | str) -> Path:
    module = load_integration_module(integration_type)
    return Path(module.__path__[0], filepath)


def load_integration_resource(integration_type: str, filepath: Path | str, *, as_text: bool = True) -> str:
    resource = get_integration_resource_path(integration_type, filepath)
    return load_file(resource, as_text=as_text)


def load_file(filepath: Path | str, *, as_text: bool = True) -> str:
    if isinstance(filepath, str):
        filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not filepath.is_file():
        raise IsADirectoryError(f"File is a directory: {filepath}")
    return filepath.read_text() if as_text else filepath.read_bytes()
