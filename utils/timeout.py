"""Async timeout wrapper for Pantheon agent operations.

Usage::

    from utils.timeout import with_timeout

    result = await with_timeout(some_coroutine(), seconds=30, label="researcher")
"""

import asyncio
import functools
from typing import Awaitable, TypeVar

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when an operation exceeds its allowed wall-clock time."""

    def __init__(self, label: str, seconds: float) -> None:
        self.label = label
        self.seconds = seconds
        super().__init__(f"Operation '{label}' timed out after {seconds}s")


async def with_timeout(
    coro: Awaitable[T],
    *,
    seconds: float,
    label: str = "operation",
) -> T:
    """Await *coro* and raise :class:`TimeoutError` if it exceeds *seconds*.

    Args:
        coro: The awaitable to wrap.
        seconds: Wall-clock deadline in seconds.
        label: Human-readable name used in the error message and logs.

    Returns:
        The value returned by *coro*.

    Raises:
        TimeoutError: If *coro* does not complete within *seconds*.
    """
    try:
        return await asyncio.wait_for(asyncio.ensure_future(coro), timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(label=label, seconds=seconds)


def timeout(seconds: float, label: str | None = None):
    """Decorator that applies :func:`with_timeout` to an async function.

    Args:
        seconds: Wall-clock deadline in seconds.
        label: Override label; defaults to the decorated function's name.

    Example::

        @timeout(30)
        async def fetch_data():
            ...
    """
    def decorator(fn):
        _label = label or fn.__name__

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await with_timeout(fn(*args, **kwargs), seconds=seconds, label=_label)

        return wrapper

    return decorator
