import pytest
from pydantic import ValidationError

from src.environment import (
    AppSettings,
    CoreServiceSettings,
    DatabaseSettings,
    SecuritySettings,
    Settings,
    get_settings,
)

ENV_VARS = [
    "SERVICE_NAME",
    "DEBUG",
    "LOG_LEVEL",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_NAME",
    "CORE_SERVICE_BASE_URL",
    "CORE_SERVICE_TIMEOUT_SECONDS",
    "INTERNAL_API_TOKEN",
    "PAYMENT_WEBHOOK_TOKEN",
]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que nenhuma variável de ambiente relevante vaze do shell do host para os testes."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestAppSettings:
    """Tests for AppSettings default values and environment variable overrides."""

    def test_default_values(self) -> None:
        """Test that AppSettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = AppSettings()

        # Assert
        assert settings.service_name == "vehicle-sales-service"
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that AppSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "custom-service")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        settings = AppSettings()

        # Assert
        assert settings.service_name == "custom-service"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"


class TestDatabaseSettings:
    """Tests for DatabaseSettings default values, overrides, required fields and URL composition."""

    def test_default_values_with_required_password_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that DatabaseSettings resolves to its documented defaults when only the required password is set."""
        # Arrange
        monkeypatch.setenv("DATABASE_PASSWORD", "vehicle_sales_pass")

        # Act
        settings = DatabaseSettings()

        # Assert
        assert settings.host == "localhost"
        assert settings.port == 5432
        assert settings.user == "vehicle_sales_user"
        assert settings.password == "vehicle_sales_pass"
        assert settings.name == "vehicle_sales"

    def test_missing_password_raises_validation_error(self) -> None:
        """Test that DatabaseSettings raises ValidationError when DATABASE_PASSWORD is not set."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            DatabaseSettings()

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that DatabaseSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("DATABASE_HOST", "db.internal")
        monkeypatch.setenv("DATABASE_PORT", "6543")
        monkeypatch.setenv("DATABASE_USER", "other_user")
        monkeypatch.setenv("DATABASE_PASSWORD", "other_pass")
        monkeypatch.setenv("DATABASE_NAME", "other_db")

        # Act
        settings = DatabaseSettings()

        # Assert
        assert settings.host == "db.internal"
        assert settings.port == 6543
        assert settings.user == "other_user"
        assert settings.password == "other_pass"
        assert settings.name == "other_db"

    def test_async_url_composition_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that async_url composes the asyncpg connection string targeting the vehicle_sales database."""
        # Arrange
        monkeypatch.setenv("DATABASE_PASSWORD", "vehicle_sales_pass")
        settings = DatabaseSettings()

        # Act
        url = settings.async_url

        # Assert
        assert url == "postgresql+asyncpg://vehicle_sales_user:vehicle_sales_pass@localhost:5432/vehicle_sales"

    def test_async_url_composition_with_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that async_url reflects overridden host, port, credentials and database name."""
        # Arrange
        monkeypatch.setenv("DATABASE_HOST", "db.internal")
        monkeypatch.setenv("DATABASE_PORT", "6543")
        monkeypatch.setenv("DATABASE_USER", "other_user")
        monkeypatch.setenv("DATABASE_PASSWORD", "other_pass")
        monkeypatch.setenv("DATABASE_NAME", "other_db")
        settings = DatabaseSettings()

        # Act
        url = settings.async_url

        # Assert
        assert url == "postgresql+asyncpg://other_user:other_pass@db.internal:6543/other_db"


class TestCoreServiceSettings:
    """Tests for CoreServiceSettings default values and environment variable overrides."""

    def test_default_values(self) -> None:
        """Test that CoreServiceSettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = CoreServiceSettings()

        # Assert
        assert settings.base_url == "http://vehicle-core-service:8000"
        assert settings.timeout_seconds == 5.0

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CoreServiceSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("CORE_SERVICE_BASE_URL", "http://core:9000")
        monkeypatch.setenv("CORE_SERVICE_TIMEOUT_SECONDS", "2.5")

        # Act
        settings = CoreServiceSettings()

        # Assert
        assert settings.base_url == "http://core:9000"
        assert settings.timeout_seconds == 2.5


class TestSecuritySettings:
    """Tests for SecuritySettings required fields and environment variable overrides."""

    def test_missing_internal_api_token_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SecuritySettings raises ValidationError when INTERNAL_API_TOKEN is not set."""
        # Arrange
        monkeypatch.setenv("PAYMENT_WEBHOOK_TOKEN", "webhook-token")

        # Act / Assert
        with pytest.raises(ValidationError):
            SecuritySettings()

    def test_missing_payment_webhook_token_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SecuritySettings raises ValidationError when PAYMENT_WEBHOOK_TOKEN is not set."""
        # Arrange
        monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-token")

        # Act / Assert
        with pytest.raises(ValidationError):
            SecuritySettings()

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SecuritySettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("INTERNAL_API_TOKEN", "custom-internal-token")
        monkeypatch.setenv("PAYMENT_WEBHOOK_TOKEN", "custom-webhook-token")

        # Act
        settings = SecuritySettings()

        # Assert
        assert settings.internal_api_token == "custom-internal-token"
        assert settings.payment_webhook_token == "custom-webhook-token"


class TestSettingsAndGetSettings:
    """Tests for the aggregate Settings model and the get_settings factory."""

    def test_settings_aggregates_sub_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Settings exposes app, database, core_service and security sub-settings with their defaults."""
        # Arrange
        monkeypatch.setenv("DATABASE_PASSWORD", "vehicle_sales_pass")
        monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-token")
        monkeypatch.setenv("PAYMENT_WEBHOOK_TOKEN", "webhook-token")

        # Act
        settings = Settings()

        # Assert
        assert isinstance(settings.app, AppSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.core_service, CoreServiceSettings)
        assert isinstance(settings.security, SecuritySettings)
        assert settings.database.name == "vehicle_sales"

    def test_settings_raises_validation_error_when_required_secrets_are_missing(self) -> None:
        """Test that Settings raises ValidationError when the required database password or tokens are absent."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            Settings()

    def test_get_settings_returns_settings_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_settings returns a fully resolved Settings instance."""
        # Arrange
        monkeypatch.setenv("DATABASE_PASSWORD", "vehicle_sales_pass")
        monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-token")
        monkeypatch.setenv("PAYMENT_WEBHOOK_TOKEN", "webhook-token")

        # Act
        settings = get_settings()

        # Assert
        assert isinstance(settings, Settings)
        assert settings.app.service_name == "vehicle-sales-service"
