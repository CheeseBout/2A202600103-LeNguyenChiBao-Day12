"""Application settings using 12-factor environment variables."""
import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # Runtime
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))

    # Metadata
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Day12 Production Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    allowed_origins: list[str] = field(default_factory=lambda: _env_list("ALLOWED_ORIGINS", "*"))

    # LLM and storage
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "mock-llm"))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Reliability and limits
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    rate_limit_window_seconds: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")))
    monthly_budget_usd: float = field(default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0")))
    global_monthly_budget_usd: float = field(default_factory=lambda: float(os.getenv("GLOBAL_MONTHLY_BUDGET_USD", "500.0")))
    input_token_price_per_1k: float = field(default_factory=lambda: float(os.getenv("INPUT_TOKEN_PRICE_PER_1K", "0.00015")))
    output_token_price_per_1k: float = field(default_factory=lambda: float(os.getenv("OUTPUT_TOKEN_PRICE_PER_1K", "0.0006")))
    shutdown_grace_seconds: int = field(default_factory=lambda: int(os.getenv("SHUTDOWN_GRACE_SECONDS", "30")))
    session_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 24))))

    def validate(self) -> "Settings":
        if self.environment.lower() == "production" and not self.agent_api_key:
            raise ValueError("AGENT_API_KEY must be set in production")
        if not self.agent_api_key and self.environment.lower() != "production":
            # Local-only fallback to simplify development while keeping production strict.
            self.agent_api_key = "dev-local-key"
        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be > 0")
        if self.monthly_budget_usd <= 0:
            raise ValueError("MONTHLY_BUDGET_USD must be > 0")
        return self


settings = Settings().validate()
