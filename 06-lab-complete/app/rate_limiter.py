"""Redis sliding-window rate limiter."""
import time
import uuid

from fastapi import HTTPException
from redis import Redis


class RateLimiter:
	def __init__(self, redis_client: Redis, limit: int, window_seconds: int):
		self.redis = redis_client
		self.limit = limit
		self.window_seconds = window_seconds

	def check_rate_limit(self, user_id: str) -> dict[str, int]:
		now_ms = int(time.time() * 1000)
		window_start_ms = now_ms - (self.window_seconds * 1000)

		key = f"rl:{user_id}"
		member = f"{now_ms}:{uuid.uuid4().hex}"

		pipe = self.redis.pipeline()
		pipe.zremrangebyscore(key, 0, window_start_ms)
		pipe.zcard(key)
		_, current_count = pipe.execute()

		if int(current_count) >= self.limit:
			oldest = self.redis.zrange(key, 0, 0, withscores=True)
			retry_after = self.window_seconds
			if oldest:
				oldest_ms = int(oldest[0][1])
				retry_after = max(1, int((oldest_ms + (self.window_seconds * 1000) - now_ms) / 1000))

			raise HTTPException(
				status_code=429,
				detail="Rate limit exceeded",
				headers={"Retry-After": str(retry_after)},
			)

		pipe = self.redis.pipeline()
		pipe.zadd(key, {member: now_ms})
		pipe.expire(key, self.window_seconds + 5)
		pipe.execute()

		return {
			"limit": self.limit,
			"remaining": max(0, self.limit - int(current_count) - 1),
			"window_seconds": self.window_seconds,
		}
