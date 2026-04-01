"""Tests for utils/timeout.py"""

import asyncio
import pytest

from utils.timeout import with_timeout, timeout, TimeoutError as PantheonTimeoutError


# --------------------------------------------------------------------------- #
# with_timeout                                                                 #
# --------------------------------------------------------------------------- #

async def test_with_timeout_returns_value():
    async def fast():
        return 42

    result = await with_timeout(fast(), seconds=5, label="fast_op")
    assert result == 42


async def test_with_timeout_raises_on_slow_coroutine():
    async def slow():
        await asyncio.sleep(10)

    with pytest.raises(PantheonTimeoutError) as exc_info:
        await with_timeout(slow(), seconds=0.05, label="slow_op")

    assert exc_info.value.label == "slow_op"
    assert exc_info.value.seconds == 0.05
    assert "slow_op" in str(exc_info.value)


async def test_with_timeout_error_message_contains_seconds():
    async def slow():
        await asyncio.sleep(10)

    with pytest.raises(PantheonTimeoutError) as exc_info:
        await with_timeout(slow(), seconds=0.01, label="test")

    assert "0.01" in str(exc_info.value)


async def test_with_timeout_propagates_non_timeout_exceptions():
    async def boom():
        raise ValueError("oops")

    with pytest.raises(ValueError, match="oops"):
        await with_timeout(boom(), seconds=5, label="boom_op")


async def test_with_timeout_completes_just_before_deadline():
    async def nearly_slow():
        await asyncio.sleep(0.01)
        return "ok"

    result = await with_timeout(nearly_slow(), seconds=5, label="nearly_slow")
    assert result == "ok"


# --------------------------------------------------------------------------- #
# @timeout decorator                                                           #
# --------------------------------------------------------------------------- #

async def test_timeout_decorator_passes_through():
    @timeout(5)
    async def fast():
        return "hello"

    assert await fast() == "hello"


async def test_timeout_decorator_raises_on_slow():
    @timeout(0.05, label="decorated_slow")
    async def slow():
        await asyncio.sleep(10)

    with pytest.raises(PantheonTimeoutError) as exc_info:
        await slow()

    assert exc_info.value.label == "decorated_slow"


async def test_timeout_decorator_default_label_is_function_name():
    @timeout(0.05)
    async def my_special_func():
        await asyncio.sleep(10)

    with pytest.raises(PantheonTimeoutError) as exc_info:
        await my_special_func()

    assert exc_info.value.label == "my_special_func"


async def test_timeout_decorator_preserves_function_name():
    @timeout(5)
    async def named_function():
        return True

    assert named_function.__name__ == "named_function"


async def test_timeout_decorator_forwards_args():
    @timeout(5)
    async def add(a, b):
        return a + b

    assert await add(3, 4) == 7


# --------------------------------------------------------------------------- #
# PantheonTimeoutError attributes                                              #
# --------------------------------------------------------------------------- #

def test_timeout_error_attributes():
    err = PantheonTimeoutError(label="op", seconds=30.0)
    assert err.label == "op"
    assert err.seconds == 30.0
    assert isinstance(err, Exception)
