import pytest
from httpx import AsyncClient


class TestHealthController:
    """Tests for the GET /health route."""

    @pytest.mark.asyncio
    async def test_health_check_returns_ok_payload(self, async_client: AsyncClient) -> None:
        """Test that /health responds with HTTP 200 and the expected status payload."""
        # Arrange
        expected_payload = {
            "status": "ok",
            "service": "vehicle-sales-service",
            "version": "0.1.0",
        }

        # Act
        response = await async_client.get("/health")

        # Assert
        assert response.status_code == 200
        assert response.json() == expected_payload
