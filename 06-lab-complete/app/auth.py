"""Authentication helpers for API key based access."""
from fastapi import Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Verify API key from X-API-Key header."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )

    if api_key != settings.agent_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


def resolve_user_id(
    body_user_id: str | None,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """Resolve a user id from body first, then X-User-Id header."""
    candidate = (body_user_id or x_user_id or "anonymous").strip()
    return candidate or "anonymous"
