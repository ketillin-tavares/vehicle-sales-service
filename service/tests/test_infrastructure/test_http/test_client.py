import pytest

from src.infrastructure.http import client


class TestHttpClientLifecycle:
    """Tests for the shared HTTP client startup/shutdown/access helpers."""

    @pytest.mark.asyncio
    async def test_get_http_client_raises_before_start(self) -> None:
        """Test that get_http_client raises RuntimeError when the client has not been started yet."""
        # Arrange
        client._http_client = None  # noqa: SLF001

        # Act / Assert
        with pytest.raises(RuntimeError):
            client.get_http_client()

    @pytest.mark.asyncio
    async def test_start_then_get_http_client_returns_instance(self) -> None:
        """Test that get_http_client returns the client created by start_http_client."""
        # Arrange
        await client.start_http_client(timeout_seconds=1.0)

        # Act
        http_client = client.get_http_client()

        # Assert
        assert http_client is not None

        # Cleanup
        await client.stop_http_client()

    @pytest.mark.asyncio
    async def test_stop_http_client_clears_the_shared_instance(self) -> None:
        """Test that stop_http_client closes and clears the shared client instance."""
        # Arrange
        await client.start_http_client(timeout_seconds=1.0)

        # Act
        await client.stop_http_client()

        # Assert
        with pytest.raises(RuntimeError):
            client.get_http_client()
