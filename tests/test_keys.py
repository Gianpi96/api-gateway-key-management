import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey


async def _set_tier(db_session: AsyncSession, key_id: int, tier: str) -> None:
    """Simulate what the Stripe webhook does: change the tier in the database."""
    await db_session.execute(update(ApiKey).where(ApiKey.id == key_id).values(tier=tier))
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_api_key_free(client: AsyncClient):
    response = await client.post(
        "/gateway/keys", json={"user_id": "user_free", "tier": "free"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("gw_")
    assert data["tier"] == "free"
    assert data["user_id"] == "user_free"
    assert "id" in data


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", ["pro", "enterprise", "ultra"])
async def test_client_cannot_choose_tier(client: AsyncClient, requested: str):
    """A client asking for a paid tier must still get a free key (no payment bypass)."""
    response = await client.post(
        "/gateway/keys", json={"user_id": "user_sneaky", "tier": requested}
    )
    assert response.status_code == 201
    assert response.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_get_usage_pro(client: AsyncClient, db_session: AsyncSession):
    create = await client.post("/gateway/keys", json={"user_id": "user_usage"})
    assert create.status_code == 201
    key_id = create.json()["id"]
    raw_key = create.json()["key"]
    await _set_tier(db_session, key_id, "pro")

    response = await client.get(
        f"/gateway/keys/{key_id}/usage",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["calls_today"] == 0
    assert data["rate_limit_today"] == 10_000
    assert data["tier"] == "pro"


@pytest.mark.asyncio
async def test_get_usage_enterprise_unlimited(client: AsyncClient, db_session: AsyncSession):
    create = await client.post("/gateway/keys", json={"user_id": "ent_user"})
    key_id = create.json()["id"]
    raw_key = create.json()["key"]
    await _set_tier(db_session, key_id, "enterprise")

    response = await client.get(
        f"/gateway/keys/{key_id}/usage",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    assert response.json()["rate_limit_today"] is None


@pytest.mark.asyncio
async def test_get_usage_not_found(client: AsyncClient):
    # Need a valid key to pass middleware — create one first
    create = await client.post(
        "/gateway/keys", json={"user_id": "finder", "tier": "free"}
    )
    raw_key = create.json()["key"]

    response = await client.get(
        "/gateway/keys/9999/usage",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_usage_reports_live_counter_from_redis(client: AsyncClient, mock_redis):
    create = await client.post("/gateway/keys", json={"user_id": "counter_user"})
    key_id = create.json()["id"]
    raw_key = create.json()["key"]
    mock_redis.get.return_value = b"42"

    response = await client.get(
        f"/gateway/keys/{key_id}/usage", headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200
    assert response.json()["calls_today"] == 42
