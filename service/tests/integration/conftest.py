import os
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

SERVICE_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = SERVICE_ROOT / "alembic.ini"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Fixture de sessão que sobe um container PostgreSQL efêmero para os testes de integração."""
    with PostgresContainer("postgres:17-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    """
    Monta a URL asyncpg de conexão com o PostgreSQL efêmero do testcontainers.

    Args:
        postgres_container: Container PostgreSQL em execução.

    Returns:
        URL de conexão async no formato postgresql+asyncpg://...
    """
    return (
        f"postgresql+asyncpg://{postgres_container.username}:{postgres_container.password}"
        f"@{postgres_container.get_container_host_ip()}:{postgres_container.get_exposed_port(5432)}"
        f"/{postgres_container.dbname}"
    )


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(postgres_container: PostgresContainer) -> None:
    """
    Aponta as variáveis de ambiente de banco para o container efêmero e roda `alembic upgrade head`.

    Args:
        postgres_container: Container PostgreSQL em execução, usado para resolver host/porta/credenciais.
    """
    os.environ["DATABASE_HOST"] = postgres_container.get_container_host_ip()
    os.environ["DATABASE_PORT"] = str(postgres_container.get_exposed_port(5432))
    os.environ["DATABASE_USER"] = postgres_container.username
    os.environ["DATABASE_PASSWORD"] = postgres_container.password
    os.environ["DATABASE_NAME"] = postgres_container.dbname

    alembic_cfg = Config(str(ALEMBIC_INI))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
async def db_engine(database_url: str) -> AsyncGenerator[AsyncEngine]:
    """Fixture de engine async isolada por teste, apontando para o container efêmero."""
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fixture com a fábrica de sessões async vinculada ao engine do teste."""
    return async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean_tables(db_engine: AsyncEngine) -> AsyncGenerator[None]:
    """Trunca as tabelas de domínio após cada teste, isolando os testes entre si."""
    yield
    async with db_engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE sales, vehicle_replicas RESTART IDENTITY CASCADE"))
