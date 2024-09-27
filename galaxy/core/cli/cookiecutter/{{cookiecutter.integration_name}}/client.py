
__all__ = ["{{ cookiecutter.integration_name_pascalcase }}Client"]


class {{ cookiecutter.integration_name_pascalcase }}Client:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    # Implement the logic to make the API requests in this class
    async def api_request(self):
        return[{"id": 12345, "name": "rely test", "created_at": "2024-01-01T00:00:00Z", "url": "http://www.rely.io"}]
