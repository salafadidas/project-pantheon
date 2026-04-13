"""Tests for utils/retry.py"""

import pytest

from utils.retry import retry, retry_call, RetryError


# --------------------------------------------------------------------------- #
# @retry decorator — success paths                                             #
# --------------------------------------------------------------------------- #

async def test_retry_succeeds_first_attempt():
    call_count = 0

    @retry(max_attempts=3, base_delay=0.01)
    async def fn():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await fn()
    assert result == "ok"
    assert call_count == 1


async def test_retry_succeeds_on_second_attempt():
    call_count = 0

    @retry(max_attempts=3, base_delay=0.01, jitter=False)
    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("transient")
        return "recovered"

    result = await fn()
    assert result == "recovered"
    assert call_count == 2


async def test_retry_succeeds_on_last_attempt():
    call_count = 0

    @retry(max_attempts=4, base_delay=0.01, jitter=False)
    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise RuntimeError("fail")
        return "final"

    result = await fn()
    assert result == "final"
    assert call_count == 4


# --------------------------------------------------------------------------- #
# @retry decorator — failure paths                                             #
# --------------------------------------------------------------------------- #

async def test_retry_raises_retry_error_when_exhausted():
    @retry(max_attempts=3, base_delay=0.01, jitter=False)
    async def always_fails():
        raise ValueError("permanent")

    with pytest.raises(RetryError) as exc_info:
        await always_fails()

    assert exc_info.value.attempts == 3
    assert isinstance(exc_info.value.last_exception, ValueError)
    assert "permanent" in str(exc_info.value)


async def test_retry_propagates_non_retryable_exception():
    @retry(max_attempts=5, base_delay=0.01, exceptions=(TypeError,))
    async def fn():
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        await fn()


async def test_retry_only_catches_specified_exceptions():
    call_count = 0

    @retry(max_attempts=5, base_delay=0.01, exceptions=(IOError,))
    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise IOError("retryable")
        raise ValueError("stops here")

    with pytest.raises(ValueError, match="stops here"):
        await fn()

    assert call_count == 2


# --------------------------------------------------------------------------- #
# @retry — single attempt                                                      #
# --------------------------------------------------------------------------- #

async def test_retry_max_attempts_one_no_retry():
    call_count = 0

    @retry(max_attempts=1, base_delay=0.01)
    async def fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    with pytest.raises(RetryError):
        await fn()

    assert call_count == 1


# --------------------------------------------------------------------------- #
# retry_call functional form                                                   #
# --------------------------------------------------------------------------- #

async def test_retry_call_success():
    async def add(a, b):
        return a + b

    result = await retry_call(add, 2, 3, max_attempts=2)
    assert result == 5


async def test_retry_call_retries_on_failure():
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("first fail")
        return "good"

    result = await retry_call(flaky, max_attempts=3, base_delay=0.01, jitter=False)
    assert result == "good"
    assert call_count == 2


async def test_retry_call_raises_retry_error_when_exhausted():
    async def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RetryError):
        await retry_call(always_fails, max_attempts=2, base_delay=0.01, jitter=False)


# --------------------------------------------------------------------------- #
# RetryError attributes                                                        #
# --------------------------------------------------------------------------- #

def test_retry_error_attributes():
    cause = ValueError("root cause")
    err = RetryError(attempts=3, last_exception=cause)
    assert err.attempts == 3
    assert err.last_exception is cause
    assert "3" in str(err)
    assert isinstance(err, Exception)
