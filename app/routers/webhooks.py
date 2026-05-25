import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import ApiKey, TierEnum

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_VALID_TIERS = {t.value for t in TierEnum}


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_upgrade(db, obj)
    elif event_type == "customer.subscription.deleted":
        await _handle_downgrade(db, obj)

    return {"status": "ok", "event": event_type}


async def _handle_upgrade(db: AsyncSession, session_obj: dict) -> None:
    user_id = session_obj.get("client_reference_id")
    new_tier = session_obj.get("metadata", {}).get("tier", TierEnum.pro.value)

    if not user_id or new_tier not in _VALID_TIERS:
        return

    await db.execute(
        update(ApiKey).where(ApiKey.user_id == user_id).values(tier=new_tier)
    )
    await db.commit()


async def _handle_downgrade(db: AsyncSession, subscription_obj: dict) -> None:
    user_id = subscription_obj.get("metadata", {}).get("user_id")

    if not user_id:
        return

    await db.execute(
        update(ApiKey)
        .where(ApiKey.user_id == user_id)
        .values(tier=TierEnum.free.value)
    )
    await db.commit()
