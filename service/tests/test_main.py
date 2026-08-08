import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from src.domain.exceptions import DomainError, InvalidCpfError
from src.main import app, lifespan


class TestLifespan:
    """Tests for the application startup/shutdown lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_configures_logging_and_disposes_engine(self) -> None:
        """Test that the lifespan context runs startup/shutdown without raising, disposing the DB engine."""
        # Arrange / Act / Assert
        async with lifespan(app):
            pass


class _ExemploDomainError(DomainError):
    """Exceção de domínio de exemplo usada apenas para exercitar o exception handler global."""


_test_router = APIRouter()


@_test_router.get("/__raise-domain-error")
async def _raise_domain_error() -> None:
    """Rota de teste que sempre levanta uma DomainError para validar o handler global."""
    raise _ExemploDomainError("erro de domínio simulado")


@_test_router.get("/__raise-invalid-cpf-error")
async def _raise_invalid_cpf_error() -> None:
    """Rota de teste que sempre levanta uma InvalidCpfError para validar o handler específico."""
    raise InvalidCpfError("CPF inválido: 12345678900")


app.include_router(_test_router)


class TestDomainErrorHandler:
    """Tests for the global DomainError -> HTTP 400 exception handler."""

    @pytest.mark.asyncio
    async def test_domain_error_is_translated_to_http_400(self) -> None:
        """Test that a DomainError raised by a route is translated into an HTTP 400 JSON response."""
        # Arrange
        transport = ASGITransport(app=app)

        # Act
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/__raise-domain-error")

        # Assert
        assert response.status_code == 400
        assert response.json() == {"detail": "erro de domínio simulado"}


class TestOpenApiSchema:
    """Tests for the OpenAPI schema exposure of internal-only routes."""

    @pytest.mark.asyncio
    async def test_internal_routes_are_hidden_from_openapi_schema(self, async_client: AsyncClient) -> None:
        """Test that /internal/* routes are excluded from the public OpenAPI schema."""
        # Arrange / Act
        response = await async_client.get("/openapi.json")

        # Assert
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/internal/v1/vehicles/{vehicle_id}" not in paths
        assert not any(path.startswith("/internal/") for path in paths)

    @pytest.mark.asyncio
    async def test_public_routes_remain_documented(self, async_client: AsyncClient) -> None:
        """Test that public routes, including the payment webhook consumed externally, stay in the schema."""
        # Arrange / Act
        response = await async_client.get("/openapi.json")

        # Assert
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/v1/vehicles/for-sale" in paths
        assert "/v1/vehicles/sold" in paths
        assert "/v1/purchases" in paths
        assert "/webhooks/v1/payments" in paths


class TestInvalidCpfErrorHandler:
    """Tests for the InvalidCpfError -> HTTP 422 exception handler."""

    @pytest.mark.asyncio
    async def test_invalid_cpf_error_is_translated_to_http_422(self) -> None:
        """Test that an InvalidCpfError raised by a route is translated into an HTTP 422 JSON response."""
        # Arrange
        transport = ASGITransport(app=app)

        # Act
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/__raise-invalid-cpf-error")

        # Assert
        assert response.status_code == 422
        assert response.json() == {"detail": "CPF inválido: 12345678900"}
