from app.executor.retry import RetryPolicy


def test_retry_policy_exponential_backoff() -> None:
    policy = RetryPolicy(max_retries=3, base_delay=1.0, multiplier=2.0)
    assert policy.get_delay(1) == 1.0
    assert policy.get_delay(2) == 2.0
    assert policy.get_delay(3) == 4.0
