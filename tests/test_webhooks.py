import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, TierEnum


@pytest.mark.asyncio
async def test_invalid_stripe_signature_returns_400(client: AsyncClient):
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    response = await client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": "bad_sig", "content-type": "application/json"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_checkout_completed_upgrades_tier(client: AsyncClient, db_session: AsyncSession):
    api_key = ApiKey(key_hash="hash_upgrade", user_id="stripe_user_1", tier="free")
    db_session.add(api_key)
    await db_session.commit()

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "stripe_user_1",
                "metadata": {"tier": "pro"},
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=event):
        response = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "mock", "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["event"] == "checkout.session.completed"

    db_session.expire_all()  # synchronous — forces reload on next access
    result = await db_session.execute(
        select(ApiKey).where(ApiKey.user_id == "stripe_user_1")
    )
    updated = result.scalar_one()
    assert updated.tier == TierEnum.pro.value


@pytest.mark.asyncio
async def test_subscription_deleted_downgrades_to_free(client: AsyncClient, db_session: AsyncSession):
    api_key = ApiKey(key_hash="hash_downgrade", user_id="stripe_user_2", tier="pro")
    db_session.add(api_key)
    await db_session.commit()

    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "metadata": {"user_id": "stripe_user_2"},
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=event):
        response = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "mock", "content-type": "application/json"},
        )

    assert response.status_code == 200

    db_session.expire_all()  # synchronous — forces reload on next access
    result = await db_session.execute(
        select(ApiKey).where(ApiKey.user_id == "stripe_user_2")
    )
    updated = result.scalar_one()
    assert updated.tier == TierEnum.free.value


@pytest.mark.asyncio
async def test_unknown_event_type_is_ignored(client: AsyncClient):
    event = {"type": "payment_intent.created", "data": {"object": {}}}

    with patch("stripe.Webhook.construct_event", return_value=event):
        response = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "mock", "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
