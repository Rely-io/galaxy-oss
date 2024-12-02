from types import TracebackType
from typing import Any

from galaxy.core.galaxy import register, Integration
from galaxy.core.models import Config
from galaxy.integrations.{{ cookiecutter.integration_name }}.client import {{ cookiecutter.integration_name_pascalcase }}Client


class {{ cookiecutter.integration_name_pascalcase }}(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = {{ cookiecutter.integration_name_pascalcase }}Client(self.config, self.logger)

    async def __aenter__(self) -> "{{ cookiecutter.integration_name_pascalcase }}":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @register(_methods, group=1)
    async def entities(self) -> tuple[Any]:
        entities = await self.client.api_request()
        mapped_entities = await self.mapper.process("entities", entities)
        return mapped_entities
