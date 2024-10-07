from typing import Any

import msgspec

__all__ = ["json_serialize", "json_deserialize"]


def json_serialize(obj: Any) -> bytes:
    return msgspec.json.encode(obj)


def json_deserialize(obj: str | bytes) -> Any:
    return msgspec.json.decode(obj)
