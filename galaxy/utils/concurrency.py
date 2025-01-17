import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import anyio
import uvloop
from anyio import to_thread
from anyio.abc import Semaphore, TaskGroup

__all__ = ["loop_setup", "set_thread_pool_limit", "run", "run_in_thread", "task_group_run_with_semaphore"]

P = ParamSpec("P")
T = TypeVar("T")


def loop_setup() -> None:
    """Set the event loop policy to use uvloop."""
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def set_thread_pool_limit(limit: int) -> None:
    """Set the maximum number of worker threads."""
    to_thread.current_default_thread_limiter().total_tokens = limit


def run(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run the given coroutine function in an asynchronous event loop."""
    if kwargs:
        func = functools.partial(func, **kwargs)
    return anyio.run(func, *args, backend="asyncio", backend_options={"loop_factory": uvloop.new_event_loop})


async def run_in_thread(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Call the given function with the given arguments in a worker thread."""
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await to_thread.run_sync(func, *args)


async def task_group_run_with_semaphore(
    task_group: TaskGroup, semaphore: Semaphore, func: Callable[P, Awaitable[T]], *args: P.args, **kwargs: P.kwargs
) -> None:
    await semaphore.acquire()

    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        finally:
            semaphore.release()

    task_group.start_soon(wrapper, *args, **kwargs)
