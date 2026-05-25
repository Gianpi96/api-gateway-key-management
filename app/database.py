from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — reads the session maker injected by lifespan (or tests)."""
    async with request.app.state.db_session_maker() as session:
        yield session
