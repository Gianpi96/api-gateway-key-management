import pytest
from httpx import AsyncClient


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
async def test_create_api_key_pro(client: AsyncClient):
    response = await client.post(
        "/gateway/keys", json={"user_id": "user_pro", "tier": "pro"}
    )
    assert response.status_code == 201
    assert response.json()["tier"] == "pro"


@pytest.mark.asyncio
async def test_create_api_key_invalid_tier(client: AsyncClient):
    response = await client.post(
        "/gateway/keys", json={"user_id": "user_x", "tier": "ultra"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_usage_pro(client: AsyncClient):
    create = await client.post(
        "/gateway/keys", json={"user_id": "user_usage", "tier": "pro"}
    )
    assert create.status_code == 201
    key_id = create.json()["id"]
    raw_key = create.json()["key"]

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
async def test_get_usage_enterprise_unlimited(client: AsyncClient):
    create = await client.post(
        "/gateway/keys", json={"user_id": "ent_user", "tier": "enterprise"}
    )
    key_id = create.json()["id"]
    raw_key = create.json()["key"]

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
