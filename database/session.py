from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from functools import wraps

from config import DATABASE_URL

async_database_url = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1).replace('postgres://', 'postgresql+asyncpg://', 1)

engine = create_async_engine(async_database_url)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

def db_session(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            result = await func(db, *args, **kwargs)
            return result
    return wrapper 