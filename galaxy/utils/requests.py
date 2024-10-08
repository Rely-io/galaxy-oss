import logging
import traceback
from collections.abc import Generator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from typing import Any, ClassVar, TypeAlias

from aiohttp import ClientResponseError, ClientTimeout, ContentTypeError
from aiohttp import ClientSession as AiohttpClientSession
from aiohttp.client_exceptions import ClientError as AiohttpClientError
from attr import define
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .serializers import json_serialize

ClientSession: TypeAlias = AiohttpClientSession
error_dataclass = partial(dataclass, kw_only=True, frozen=True, slots=True)


@error_dataclass
class RequestError(Exception):
    """Base class for all request errors."""

    message: str
    response_content: Any
    method: str
    url: str
    headers: dict[str, str] | None = None

    def __str__(self) -> str:
        return self.message


@error_dataclass
class RequestHTTPError(RequestError):
    """Base class for all HTTP errors."""

    status_code: int


@error_dataclass
class ServerError(RequestError):
    """Base class for all server errors."""


@error_dataclass
class ClientError(RequestError):
    """Base class for all client errors."""

    status: ClassVar[int] = 400


@error_dataclass
class UnauthorizedError(ClientError):
    status_code: ClassVar[int] = 401


@error_dataclass
class NotFoundError(ClientError):
    status_code: ClassVar[int] = 404


@error_dataclass
class ContentTooLargeError(ClientError):
    status_code: ClassVar[int] = 413


@error_dataclass
class RateLimitError(ClientError):
    status_code: ClassVar[int] = 429


@define(kw_only=True)
class RetryPolicy:
    max_attempts: int = 5
    exceptions_to_retry: tuple[type[Exception], ...] = (ServerError, RateLimitError)

    wait_multiplier: int = 1
    wait_max: int = 10
    wait_min: int = 60

    reraise: bool = True
    logger: logging.Logger | None = None

    def retry_attempts(self) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_random_exponential(min=self.wait_min, max=self.wait_max, multiplier=self.wait_multiplier),
            before_sleep=before_sleep_log(self.logger, logging.WARNING) if self.logger else None,
            reraise=self.reraise,
            retry=retry_if_exception_type(self.exceptions_to_retry),
        )


def create_session(*, timeout: int = 30, headers: dict[str, str] | None = None, **kwargs: Any) -> ClientSession:
    return ClientSession(
        timeout=ClientTimeout(total=timeout),
        # aiohttp expects json_serialize to return string
        json_serialize=kwargs.pop("json_serialize", lambda obj: json_serialize(obj).decode()),
        headers=headers,
        **kwargs,
    )


@asynccontextmanager
async def with_session(
    *, timeout: int = 30, headers: dict[str, str] | None = None, **kwargs: Any
) -> Generator[ClientSession, None, None]:
    async with create_session(timeout=timeout, headers=headers, **kwargs) as session:
        yield session


async def make_request(
    session: ClientSession,
    method: str,
    url: str,
    *,
    logger: logging.Logger | None = None,
    retry: bool = True,
    retry_policy: RetryPolicy | None = None,
    none_on_404: bool = False,
    **kwargs: Any,
) -> Any:
    response_content: Any | None = None
    try:
        if not retry:
            response_content = await _make_request(session, method, url, **kwargs)

        if retry_policy is None:
            retry_policy = RetryPolicy(logger=logger)

        async for attempt in retry_policy.retry_attempts():
            with attempt:
                response_content = await _make_request(session, method, url, **kwargs)

        return response_content
    except NotFoundError as e:
        if none_on_404:
            if logger is not None:
                logger.warning(e.message)
            return None
    except RequestError:
        raise
    except Exception as e:
        traceback.print_exc()
        raise RequestError(
            message=f"Unexpected error during {method} {url}: {str(e)}",
            response_content=response_content,
            method=method,
            url=url,
        )


async def _make_request(session: ClientSession, method: str, url: str, **kwargs: Any) -> Any:
    response_content: Any | None = None
    try:
        async with session.request(method, url, **kwargs) as response:
            # Try parsing the response even for error statuses
            try:
                try:
                    if response.content_type == "text/plain":
                        response_content = await response.text()
                    response_content = await response.json()
                except ContentTypeError:
                    # Fallback to plain text if JSON parsing fails
                    response_content = await response.text()
            except Exception:
                response_content = None

            response.raise_for_status()
            return response_content
    except ClientResponseError as e:
        match e.status:
            case 401:
                error_cls = UnauthorizedError
                error_message = f"Unauthorized ({e.status}): Invalid API credentials for {method} {url}"
            case 404:
                error_cls = NotFoundError
                error_message = f"Not Found ({e.status}): {e.message} during {method} {url}"
            case 413:
                error_cls = ContentTooLargeError
                error_message = f"Content too large ({e.status}): Request body too large for {method} {url}"
            case 429:
                error_cls = RateLimitError
                error_message = f"Rate limit exceeded ({e.status}): Too many requests for {method} {url}"
            case _ if 400 <= e.status < 500:
                error_cls = ClientError
                error_message = f"Client Error ({e.status}): {e.message} during {method} {url}"
            case _ if 500 <= e.status < 600:
                error_cls = ServerError
                error_message = f"Server Error ({e.status}): {e.message} during {method} {url}"
            case _:
                error_cls = RequestError
                error_message = f"Request Error ({e.status}): {e.message} during {method} {url}"

        raise error_cls(
            message=error_message, response_content=response_content, headers=e.headers, method=method, url=url
        )

    except AiohttpClientError as e:
        raise RequestError(
            message=f"Request failed for {method} {url}: {str(e)}",
            response_content=response_content,
            method=method,
            url=url,
        )
