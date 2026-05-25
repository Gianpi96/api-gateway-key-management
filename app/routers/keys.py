from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeyUsageResponse
from app.services.key_service import create_api_key, get_api_key_by_id
from app.services.rate_limiter import RATE_LIMITS

router = APIRouter(prefix="/gateway", tags=["keys"])


@router.post("/keys", response_model=ApiKeyResponse, status_code=201)
async def create_key(payload: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    api_key, raw_key = await create_api_key(db, payload.user_id, payload.tier)
    return ApiKeyResponse(
        id=api_key.id,
        user_id=api_key.user_id,
        tier=api_key.tier,
        key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("/keys/{key_id}/usage", response_model=ApiKeyUsageResponse)
async def get_usage(key_id: int, db: AsyncSession = Depends(get_db)):
    api_key = await get_api_key_by_id(db, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyUsageResponse(
        id=api_key.id,
        user_id=api_key.user_id,
        tier=api_key.tier,
        calls_today=api_key.calls_today,
        calls_this_month=api_key.calls_this_month,
        rate_limit_today=RATE_LIMITS.get(api_key.tier),
    )
