from galaxy.core.galaxy import register, Integration
from galaxy.core.models import Config
from galaxy.integrations.{{cookiecutter.integration_name}}.client import {{cookiecutter.integration_name_pascalcase}}Client


class {{cookiecutter.integration_name_pascalcase}}(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = {{cookiecutter.integration_name_pascalcase}}Client(self.config, self.logger)

    @register(_methods, group=1)
    async def entities(self) -> list[dict]:
        self.entities = await self.client.api_request()
        entities = await self.mapper.process("entities", self.entities)
        return entities
