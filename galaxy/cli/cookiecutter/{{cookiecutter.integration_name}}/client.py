from types import TracebackType

from galaxy.utils.requests import ClientSession, create_session

__all__ = ["{{ cookiecutter.integration_name_pascalcase }}Client"]


class {{ cookiecutter.integration_name_pascalcase }}Client:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        # (If needed) Client session
        self._session: ClientSession | None = None
        self._headers = {}

    # (If needed) Implement logic for client context manager
    async def __aenter__(self) -> "{{ cookiecutter.integration_name_pascalcase }}Client":
        self._session = create_session(headers=self._headers)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise ValueError("client session has not been created")

        return self._session


    # Implement the logic to make the API requests in this class
    async def api_request(self):
        return [{"id": 12345, "name": "rely test", "created_at": "2024-01-01T00:00:00Z", "url": "http://www.rely.io"}]
