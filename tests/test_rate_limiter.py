from unittest.mock import AsyncMock

import pytest

from app.models import TierEnum
from app.services.rate_limiter import RATE_LIMITS, RateLimiter


@pytest.mark.asyncio
async def test_free_tier_within_limit():
    redis = AsyncMock()
    redis.incr.return_value = 50
    limiter = RateLimiter(redis)

    allowed, count = await limiter.is_allowed(1, TierEnum.free.value)

    assert allowed is True
    assert count == 50


@pytest.mark.asyncio
async def test_free_tier_at_exact_limit():
    redis = AsyncMock()
    redis.incr.return_value = 100
    limiter = RateLimiter(redis)

    allowed, count = await limiter.is_allowed(1, TierEnum.free.value)

    assert allowed is True
    assert count == 100


@pytest.mark.asyncio
async def test_free_tier_exceeds_limit():
    redis = AsyncMock()
    redis.incr.return_value = 101
    limiter = RateLimiter(redis)

    allowed, count = await limiter.is_allowed(1, TierEnum.free.value)

    assert allowed is False
    assert count == 101


@pytest.mark.asyncio
async def test_pro_tier_limit():
    redis = AsyncMock()
    redis.incr.return_value = 9_999
    limiter = RateLimiter(redis)

    allowed, _ = await limiter.is_allowed(2, TierEnum.pro.value)
    assert allowed is True


@pytest.mark.asyncio
async def test_enterprise_never_hits_redis():
    redis = AsyncMock()
    limiter = RateLimiter(redis)

    allowed, count = await limiter.is_allowed(3, TierEnum.enterprise.value)

    assert allowed is True
    assert count == 0
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_expire_set_on_first_call():
    redis = AsyncMock()
    redis.incr.return_value = 1  # first call of the day
    limiter = RateLimiter(redis)

    await limiter.is_allowed(4, TierEnum.free.value)

    redis.expire.assert_called_once()
    _, ttl = redis.expire.call_args.args
    assert ttl == 86_400


@pytest.mark.asyncio
async def test_expire_not_set_on_subsequent_calls():
    redis = AsyncMock()
    redis.incr.return_value = 5  # not the first call
    limiter = RateLimiter(redis)

    await limiter.is_allowed(5, TierEnum.free.value)

    redis.expire.assert_not_called()


def test_rate_limit_constants():
    assert RATE_LIMITS[TierEnum.free.value] == 100
    assert RATE_LIMITS[TierEnum.pro.value] == 10_000
    assert RATE_LIMITS[TierEnum.enterprise.value] is None
