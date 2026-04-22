"""Exponential-backoff retry decorator for Pantheon async operations.

Usage::

    from utils.retry import retry, RetryError

    # As a decorator
    @retry(max_attempts=3, base_delay=1.0, exceptions=(httpx.HTTPError,))
    async def call_llm(prompt: str) -> str:
        ...

    # As a context wrapper
    result = await retry_call(call_llm, prompt="hello", max_attempts=3)
"""

from __future__ import annotations

import asyncio
import functools
import random
from typing import Any, Awaitable, Callable, Sequence, Type, TypeVar

from utils.logging_config import get_logger

log = get_logger(__name__)

T = TypeVar("T")

# Default exceptions that trigger a retry
_DEFAULT_EXCEPTIONS: tuple[Type[BaseException], ...] = (Exception,)


class RetryError(Exception):
    """Raised after all retry attempts are exhausted.

    Attributes:
        attempts: Number of attempts made.
        last_exception: The exception from the final attempt.
    """

    def __init__(self, attempts: int, last_exception: BaseException) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"All {attempts} attempt(s) failed. "
            f"Last error: {type(last_exception).__name__}: {last_exception}"
        )


def _compute_delay(attempt: int, base_delay: float, max_delay: float, jitter: bool) -> float:
    """Return the sleep duration for *attempt* (0-indexed)."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    if jitter:
        delay *= random.uniform(0.5, 1.5)
    return delay


def retry(
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Sequence[Type[BaseException]] = _DEFAULT_EXCEPTIONS,
    label: str | None = None,
) -> Callable:
    """Decorator: retry an async function with exponential backoff.

    Args:
        max_attempts: Total number of calls (including the first).  Must be ≥ 1.
        base_delay: Seconds to wait before the 2nd attempt (doubles each round).
        max_delay: Upper bound on wait time between attempts.
        jitter: If ``True``, adds ±50 % random jitter to the delay.
        exceptions: Tuple of exception types that trigger a retry.
            All other exceptions propagate immediately.
        label: Human-readable name for log messages; defaults to function name.

    Returns:
        A decorator that wraps an ``async def`` function.

    Raises:
        RetryError: When *max_attempts* is reached without success.
        Any non-retryable exception immediately.
    """
    retryable = tuple(exceptions)

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        _label = label or fn.__name__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: BaseException | None = None

            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except BaseException as exc:
                    if not isinstance(exc, retryable):
                        raise
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = _compute_delay(attempt, base_delay, max_delay, jitter)
                        log.warning(
                            "retry_scheduled",
                            label=_label,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay_s=round(delay, 2),
                            error=str(exc),
                        )
                        await asyncio.sleep(delay)
                    else:
                        log.error(
                            "retry_exhausted",
                            label=_label,
                            attempts=max_attempts,
                            error=str(exc),
                        )

            raise RetryError(attempts=max_attempts, last_exception=last_exc)  # type: ignore[arg-type]

        return wrapper

    return decorator


async def retry_call(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Sequence[Type[BaseException]] = _DEFAULT_EXCEPTIONS,
    label: str | None = None,
    **kwargs: Any,
) -> T:
    """Functional form of :func:`retry` — useful when you can't use a decorator.

    Args:
        fn: Async callable to invoke.
        *args: Positional arguments forwarded to *fn*.
        max_attempts: See :func:`retry`.
        base_delay: See :func:`retry`.
        max_delay: See :func:`retry`.
        jitter: See :func:`retry`.
        exceptions: See :func:`retry`.
        label: See :func:`retry`.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The value returned by *fn* on success.
    """
    wrapped = retry(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        exceptions=exceptions,
        label=label or getattr(fn, "__name__", "fn"),
    )(fn)
    return await wrapped(*args, **kwargs)
