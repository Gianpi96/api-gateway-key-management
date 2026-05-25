import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client: AsyncClient):
    response = await client.get("/gateway/keys/1/usage")
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(client: AsyncClient):
    response = await client.get(
        "/gateway/keys/1/usage",
        headers={"X-API-Key": "gw_totallywrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_valid_api_key_injects_state(client: AsyncClient, db_session: AsyncSession):
    raw_key = "gw_validtestkey123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = ApiKey(key_hash=key_hash, user_id="mw_user", tier="free")
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    response = await client.get(
        f"/gateway/keys/{api_key.id}/usage",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == "mw_user"


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(client: AsyncClient, db_session: AsyncSession, mock_redis):
    mock_redis.incr.return_value = 101  # over the free tier limit of 100

    raw_key = "gw_ratelimited"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = ApiKey(key_hash=key_hash, user_id="rl_user", tier="free")
    db_session.add(api_key)
    await db_session.commit()

    response = await client.get(
        f"/gateway/keys/{api_key.id}/usage",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_exempt_routes_need_no_key(client: AsyncClient):
    assert (await client.get("/health")).status_code == 200
    assert (await client.post("/gateway/keys", json={"user_id": "x"})).status_code == 201
