import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, TierEnum


def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, sha256_hash). Raw key is shown once, only hash is persisted."""
    raw_key = f"gw_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def create_api_key(
    db: AsyncSession, user_id: str, tier: TierEnum
) -> tuple[ApiKey, str]:
    raw_key, key_hash = generate_api_key()
    api_key = ApiKey(key_hash=key_hash, user_id=user_id, tier=tier.value)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, raw_key


async def get_api_key_by_hash(db: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def get_api_key_by_id(db: AsyncSession, key_id: int) -> ApiKey | None:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    return result.scalar_one_or_none()
