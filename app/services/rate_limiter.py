from datetime import date

import redis.asyncio as aioredis

from app.models import TierEnum

RATE_LIMITS: dict[str, int | None] = {
    TierEnum.free.value: 100,
    TierEnum.pro.value: 10_000,
    TierEnum.enterprise.value: None,  # unlimited
}


class RateLimiter:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def is_allowed(self, key_id: int, tier: str) -> tuple[bool, int]:
        """Returns (is_allowed, current_daily_count). Enterprise always allowed."""
        limit = RATE_LIMITS.get(tier)
        if limit is None:
            return True, 0

        redis_key = f"rate_limit:{key_id}:{date.today().isoformat()}"
        count = await self.redis.incr(redis_key)

        if count == 1:
            # Expire at end of day — 86 400 s is a safe upper bound
            await self.redis.expire(redis_key, 86_400)

        return count <= limit, count
