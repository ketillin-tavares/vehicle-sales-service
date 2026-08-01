import pytest

from src.infrastructure.observability.logging import StructuredLogger, configure_logging, get_logger


class TestGetLogger:
    """Tests for the get_logger factory."""

    def test_get_logger_returns_structured_logger_instance(self) -> None:
        """Test that get_logger returns a StructuredLogger instance."""
        # Arrange / Act
        logger = get_logger()

        # Assert
        assert isinstance(logger, StructuredLogger)


class TestConfigureLogging:
    """Tests for the configure_logging sink setup."""

    def test_configure_logging_emits_info_event_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that configure_logging wires a stdout sink that emits INFO events with bound context."""
        # Arrange
        configure_logging("INFO")
        logger = get_logger()

        # Act
        logger.info("evento_de_teste", chave="valor")
        captured = capsys.readouterr()

        # Assert
        assert "evento_de_teste" in captured.out
        assert "chave" in captured.out

    def test_configure_logging_filters_below_configured_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that configure_logging suppresses DEBUG events when the level is set to INFO."""
        # Arrange
        configure_logging("INFO")
        logger = get_logger()

        # Act
        logger.debug("evento_debug_suprimido")
        captured = capsys.readouterr()

        # Assert
        assert "evento_debug_suprimido" not in captured.out


class TestStructuredLogger:
    """Tests for the StructuredLogger adapter methods."""

    def test_debug_emits_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that debug() emits the event name to stdout."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        logger.debug("evento_debug", contexto="a")
        captured = capsys.readouterr()

        # Assert
        assert "evento_debug" in captured.out

    def test_warning_emits_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that warning() emits the event name to stdout."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        logger.warning("evento_warning", contexto="b")
        captured = capsys.readouterr()

        # Assert
        assert "evento_warning" in captured.out

    def test_error_emits_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that error() emits the event name to stdout."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        logger.error("evento_error", contexto="c")
        captured = capsys.readouterr()

        # Assert
        assert "evento_error" in captured.out

    def test_exception_emits_event_with_traceback_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that exception() emits the event name while inside an active exception context."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        try:
            raise ValueError("erro simulado")
        except ValueError:
            logger.exception("evento_exception")
        captured = capsys.readouterr()

        # Assert
        assert "evento_exception" in captured.out
