from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL


def _build_engine():
    kwargs = {"echo": False}
    # PostgreSQL uchun connection pool sozlamalari
    if "postgresql" in DATABASE_URL:
        kwargs.update({
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,
            "pool_pre_ping": True,   # ulanish tirik ekanligini tekshiradi
        })
    # SQLite uchun pool argumentlar kerak emas
    return create_async_engine(DATABASE_URL, **kwargs)


engine = _build_engine()

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
