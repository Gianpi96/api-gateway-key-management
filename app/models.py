import enum

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase


class TierEnum(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(255), nullable=False, index=True)
    # Stored as plain string to stay portable between PostgreSQL and SQLite tests
    tier = Column(String(20), default=TierEnum.free.value, nullable=False)
    calls_today = Column(Integer, default=0, nullable=False)
    calls_this_month = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
