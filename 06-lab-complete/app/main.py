"""Production-ready AI Agent for Day 12 final lab."""
import asyncio
import json
import logging
import os
import signal
import socket
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError

from app.auth import resolve_user_id, verify_api_key
from app.config import settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter

try:
    from utils.mock_llm import ask as llm_ask
except Exception:
    def llm_ask(question: str) -> str:
        return f"Mock answer: {question}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("agent")
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    return logger


logger = configure_logging()

START_TIME = time.time()
INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}"

_is_ready = False
_shutting_down = False
_redis_connected = False
_in_flight_requests = 0
_request_count = 0
_error_count = 0

redis_client: Redis | None = None
rate_limiter: RateLimiter | None = None
cost_guard: CostGuard | None = None


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=128)


class AskResponse(BaseModel):
    question: str
    answer: str
    session_id: str
    usage: dict[str, Any]
    instance_id: str
    timestamp: str


def _ensure_dependencies_ready() -> None:
    if _shutting_down:
        raise HTTPException(status_code=503, detail="Server is shutting down")
    if not _is_ready or not _redis_connected:
        raise HTTPException(status_code=503, detail="Service not ready")
    if redis_client is None or rate_limiter is None or cost_guard is None:
        raise HTTPException(status_code=503, detail="Service dependencies unavailable")
    try:
        redis_client.ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}") from exc


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.5))


def _session_key(session_id: str) -> str:
    return f"session:{session_id}:history"


def load_session(session_id: str) -> list[dict[str, str]]:
    _ensure_dependencies_ready()
    raw = redis_client.lrange(_session_key(session_id), 0, -1)
    return [json.loads(item) for item in raw]


def append_to_history(session_id: str, role: str, content: str) -> None:
    _ensure_dependencies_ready()
    entry = json.dumps({"role": role, "content": content, "ts": datetime.now(timezone.utc).isoformat()})
    key = _session_key(session_id)
    pipe = redis_client.pipeline()
    pipe.rpush(key, entry)
    pipe.expire(key, settings.session_ttl_seconds)
    pipe.execute()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _is_ready, _redis_connected, redis_client, rate_limiter, cost_guard
    logger.info("Starting application")

    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
        _redis_connected = True

        rate_limiter = RateLimiter(
            redis_client=redis_client,
            limit=settings.rate_limit_per_minute,
            window_seconds=settings.rate_limit_window_seconds,
        )
        cost_guard = CostGuard(
            redis_client=redis_client,
            monthly_budget_usd=settings.monthly_budget_usd,
            global_monthly_budget_usd=settings.global_monthly_budget_usd,
            input_price_per_1k=settings.input_token_price_per_1k,
            output_price_per_1k=settings.output_token_price_per_1k,
        )
        _is_ready = True
        logger.info("Application ready")
    except RedisError as exc:
        _is_ready = False
        _redis_connected = False
        logger.error(f"Redis startup check failed: {exc}")

    yield

    _is_ready = False
    deadline = time.time() + settings.shutdown_grace_seconds
    while _in_flight_requests > 0 and time.time() < deadline:
        await asyncio.sleep(0.1)

    if redis_client is not None:
        redis_client.close()

    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-User-Id"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    global _in_flight_requests, _request_count, _error_count

    _request_count += 1
    _in_flight_requests += 1
    start = time.time()

    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        _in_flight_requests -= 1
        raise

    duration_ms = round((time.time() - start) * 1000, 2)
    _in_flight_requests -= 1

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Served-By"] = INSTANCE_ID

    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else "unknown",
            }
        )
    )

    return response


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "instance_id": INSTANCE_ID,
        "redis_connected": _redis_connected,
        "in_flight_requests": _in_flight_requests,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    if not _is_ready or _shutting_down or not _redis_connected or redis_client is None:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        redis_client.ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Not ready: {exc}") from exc
    return {"status": "ready", "instance_id": INSTANCE_ID}


@app.post("/ask", response_model=AskResponse)
def ask_agent(
    body: AskRequest,
    _api_key: str = Depends(verify_api_key),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AskResponse:
    _ensure_dependencies_ready()

    user_id = resolve_user_id(body.user_id, x_user_id)
    session_id = (body.session_id or f"{user_id}-default").strip()

    rate_info = rate_limiter.check_rate_limit(user_id)

    input_tokens = _estimate_tokens(body.question)
    estimated_output_tokens = 200
    estimated_cost = cost_guard.estimate_cost(input_tokens, estimated_output_tokens)
    cost_guard.check_budget(user_id, estimated_cost)

    history = load_session(session_id)
    prompt = body.question
    if history:
        recent = history[-4:]
        context = "\n".join(f"{item['role']}: {item['content']}" for item in recent)
        prompt = f"Conversation context:\n{context}\n\nUser: {body.question}"

    answer = llm_ask(prompt)
    output_tokens = _estimate_tokens(answer)

    append_to_history(session_id, "user", body.question)
    append_to_history(session_id, "assistant", answer)

    request_cost = cost_guard.record_usage(user_id, input_tokens, output_tokens)
    budget_remaining = cost_guard.remaining_budget(user_id)

    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "request_cost_usd": request_cost,
        "budget_remaining_usd": budget_remaining,
        "requests_remaining": rate_info["remaining"],
    }

    return AskResponse(
        question=body.question,
        answer=answer,
        session_id=session_id,
        usage=usage,
        instance_id=INSTANCE_ID,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _handle_shutdown_signal(signum: int, _frame: object) -> None:
    global _is_ready, _shutting_down
    _shutting_down = True
    _is_ready = False
    logger.warning(json.dumps({"event": "signal", "signal": signum, "action": "graceful_shutdown"}))


signal.signal(signal.SIGTERM, _handle_shutdown_signal)
signal.signal(signal.SIGINT, _handle_shutdown_signal)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=settings.shutdown_grace_seconds,
    )
