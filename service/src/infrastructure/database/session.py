from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.environment import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.database.async_url,
    echo=settings.app.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    Dependency provider que fornece uma sessão async do banco de dados.

    Yields:
        Sessão async do SQLAlchemy, commitada ao final ou revertida em caso de erro.

    Raises:
        Exception: Repropaga qualquer erro ocorrido durante o uso da sessão, após o rollback.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
