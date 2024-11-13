def to_bool(value: str | int | bool) -> bool:
    """
    Convert string on int or bool value to boolean.

    If value is boolean, return it.

    If value is int, return True if value > 0.

    If value is string, return True if value is one of "true", "t", "1", "yes", "y", "on".
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value > 0

    if not isinstance(value, str):
        raise ValueError("invalid literal for boolean. Not a string.")

    return value.lower() in ("true", "t", "1", "yes", "y", "on")
