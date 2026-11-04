from datetime import datetime

from pydantic import BaseModel

from app.models import TierEnum


class ApiKeyCreate(BaseModel):
    """New keys are always created on the free tier.

    Paid tiers are granted only by the verified Stripe webhook, so the client
    cannot choose a tier here (any ``tier`` field in the body is ignored).
    """

    user_id: str


class ApiKeyResponse(BaseModel):
    id: int
    user_id: str
    tier: str
    key: str  # Raw key — shown only at creation time
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyUsageResponse(BaseModel):
    id: int
    user_id: str
    tier: str
    calls_today: int
    calls_this_month: int
    rate_limit_today: int | None  # None means unlimited

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    model: str
    tier: str
