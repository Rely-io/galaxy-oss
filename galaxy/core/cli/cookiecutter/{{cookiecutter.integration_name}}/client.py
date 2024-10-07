from types import TracebackType
from typing import Any
from galaxy.core.utils import make_request
from galaxy.utils.requests import ClientSession, RequestError, create_session

__all__ = ["{{ cookiecutter.integration_name_pascalcase }}Client"]


class {{ cookiecutter.integration_name_pascalcase }}Client:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        # (If needed) Client session
        self._session: ClientSession | None = None

    # (If needed) Implement logic for client context manager
    async def __aenter__(self) -> "{{ cookiecutter.integration_name_pascalcase }}Client":
        self._session = create_session(headers=self._headers)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    # (If needed) Session request utilities
    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        retry: bool = True,
        raise_on_error: bool = False,
        none_on_404: bool = True,
        **kwargs: Any,
    ) -> Any:
        try:
            return await make_request(
                self._session,
                method,
                url,
                **kwargs,
                logger=self.logger,
                retry_policy=self._retry_policy,
                retry=retry,
                none_on_404=none_on_404,
            )
        except RequestError as e:
            if raise_on_error:
                raise
            self.logger.error(f"Error while making request, defaulting to empty response. ({e})")
            return None


    # Implement the logic to make the API requests in this class
    async def api_request(self):
        return [{"id": 12345, "name": "rely test", "created_at": "2024-01-01T00:00:00Z", "url": "http://www.rely.io"}]
