from collections.abc import Collection, Generator
from typing import TypeVar

T = TypeVar("T")


def chunks(lst: Collection[T], n: int) -> Generator[list[T], None, None]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]