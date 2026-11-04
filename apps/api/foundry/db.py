import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def now() -> datetime:
    return datetime.now(UTC)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


engine = create_engine(settings().database_url, pool_pre_ping=True, pool_size=8, max_overflow=8)
Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db
