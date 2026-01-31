import asyncio

from app.llm.retry import with_retry


def test_with_retry_succeeds_after_retries():
    attempts = {"count": 0}

    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("boom")
        return "ok"

    result = asyncio.run(with_retry(flaky, max_retries=3, base_delay=0))
    assert result == "ok"
    assert attempts["count"] == 3


def test_with_retry_raises_after_exhausted():
    attempts = {"count": 0}

    async def always_fail():
        attempts["count"] += 1
        raise RuntimeError("nope")

    try:
        asyncio.run(with_retry(always_fail, max_retries=2, base_delay=0))
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass

    assert attempts["count"] == 2


def test_with_retry_respects_retry_on_filter():
    attempts = {"count": 0}

    async def fail_type():
        attempts["count"] += 1
        raise ValueError("no retry")

    try:
        asyncio.run(with_retry(fail_type, max_retries=3, base_delay=0, retry_on=(RuntimeError,)))
        assert False, "Expected ValueError"
    except ValueError:
        pass

    assert attempts["count"] == 1


def test_with_retry_uses_exponential_backoff():
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    original_sleep = asyncio.sleep
    asyncio.sleep = fake_sleep
    try:
        async def always_fail():
            raise RuntimeError("nope")

        try:
            asyncio.run(with_retry(always_fail, max_retries=3, base_delay=0.5))
            assert False, "Expected RuntimeError"
        except RuntimeError:
            pass
    finally:
        asyncio.sleep = original_sleep

    assert delays == [0.5, 1.0]
