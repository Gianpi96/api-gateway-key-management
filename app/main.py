from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.middleware import ApiKeyMiddleware
from app.models import Base
from app.routers import chat, keys, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    owned: set[str] = set()

    # Tests pre-inject these into app.state — skip if already present
    if not hasattr(app.state, "db_session_maker"):
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.db_session_maker = async_sessionmaker(engine, expire_on_commit=False)
        app.state._engine = engine
        owned.add("db")

    if not hasattr(app.state, "redis"):
        app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        owned.add("redis")

    yield

    if "db" in owned and hasattr(app.state, "_engine"):
        await app.state._engine.dispose()
    if "redis" in owned:
        await app.state.redis.aclose()


app = FastAPI(
    title="API Gateway",
    description="API Gateway with key management, per-tier rate limiting, and Stripe billing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(ApiKeyMiddleware)
app.include_router(keys.router)
app.include_router(webhooks.router)
app.include_router(chat.router)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
