import hashlib

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.key_service import get_api_key_by_hash
from app.services.rate_limiter import RateLimiter

_EXEMPT_EXACT_GET = {"/health", "/openapi.json", "/favicon.ico"}
_EXEMPT_PREFIXES = ("/docs", "/redoc")
_EXEMPT_POST = {"/gateway/keys", "/webhooks/stripe"}


def _is_exempt(method: str, path: str) -> bool:
    if method == "GET" and (
        path in _EXEMPT_EXACT_GET or path.startswith(_EXEMPT_PREFIXES)
    ):
        return True
    if method == "POST" and path in _EXEMPT_POST:
        return True
    return False


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if _is_exempt(request.method, request.url.path):
            return await call_next(request)

        raw_key = request.headers.get("X-API-Key")
        if not raw_key:
            return Response(
                content='{"detail":"X-API-Key header missing"}',
                status_code=401,
                media_type="application/json",
            )

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        async with request.app.state.db_session_maker() as db:
            api_key = await get_api_key_by_hash(db, key_hash)

        if not api_key:
            return Response(
                content='{"detail":"Invalid API key"}',
                status_code=401,
                media_type="application/json",
            )

        try:
            limiter = RateLimiter(request.app.state.redis)
            allowed, _ = await limiter.is_allowed(api_key.id, api_key.tier)
        except Exception:
            # Redis non disponibile → fail-open (non bloccare la richiesta)
            allowed = True

        if not allowed:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        request.state.user_id = api_key.user_id
        request.state.tier = api_key.tier
        request.state.api_key_id = api_key.id

        return await call_next(request)
