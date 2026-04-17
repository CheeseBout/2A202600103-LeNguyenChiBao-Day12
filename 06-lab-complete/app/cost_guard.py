"""Monthly cost guard backed by Redis."""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis import Redis


class CostGuard:
	def __init__(
		self,
		redis_client: Redis,
		monthly_budget_usd: float,
		global_monthly_budget_usd: float,
		input_price_per_1k: float,
		output_price_per_1k: float,
	):
		self.redis = redis_client
		self.monthly_budget_usd = monthly_budget_usd
		self.global_monthly_budget_usd = global_monthly_budget_usd
		self.input_price_per_1k = input_price_per_1k
		self.output_price_per_1k = output_price_per_1k

	@staticmethod
	def _month_key() -> str:
		return datetime.now(timezone.utc).strftime("%Y-%m")

	def _user_budget_key(self, user_id: str) -> str:
		return f"budget:user:{user_id}:{self._month_key()}"

	def _global_budget_key(self) -> str:
		return f"budget:global:{self._month_key()}"

	def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
		input_cost = (input_tokens / 1000.0) * self.input_price_per_1k
		output_cost = (output_tokens / 1000.0) * self.output_price_per_1k
		return round(input_cost + output_cost, 8)

	def check_budget(self, user_id: str, estimated_cost: float) -> None:
		user_spent = float(self.redis.get(self._user_budget_key(user_id)) or 0.0)
		global_spent = float(self.redis.get(self._global_budget_key()) or 0.0)

		if user_spent + estimated_cost > self.monthly_budget_usd:
			raise HTTPException(status_code=402, detail="Monthly user budget exceeded")

		if global_spent + estimated_cost > self.global_monthly_budget_usd:
			raise HTTPException(status_code=503, detail="Global monthly budget exceeded")

	def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> float:
		cost = self.estimate_cost(input_tokens, output_tokens)

		user_key = self._user_budget_key(user_id)
		global_key = self._global_budget_key()

		ttl_seconds = 32 * 24 * 60 * 60
		pipe = self.redis.pipeline()
		pipe.incrbyfloat(user_key, cost)
		pipe.expire(user_key, ttl_seconds)
		pipe.incrbyfloat(global_key, cost)
		pipe.expire(global_key, ttl_seconds)
		pipe.execute()

		return cost

	def remaining_budget(self, user_id: str) -> float:
		user_spent = float(self.redis.get(self._user_budget_key(user_id)) or 0.0)
		return max(0.0, round(self.monthly_budget_usd - user_spent, 8))
