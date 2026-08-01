import sys
from typing import Any

from loguru import logger as loguru_logger

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level> | <dim>{extra}</dim>"
)


class StructuredLogger:
    """Adapter estruturado sobre o loguru: aceita um nome de evento e campos como kwargs."""

    def debug(self, event: str, **fields: Any) -> None:
        """
        Emite um log de nível DEBUG.

        Args:
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        self._log("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        """
        Emite um log de nível INFO.

        Args:
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        self._log("INFO", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        """
        Emite um log de nível WARNING.

        Args:
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        self._log("WARNING", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        """
        Emite um log de nível ERROR.

        Args:
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        self._log("ERROR", event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        """
        Emite um log de nível ERROR incluindo o traceback da exceção em tratamento.

        Args:
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        loguru_logger.bind(**fields).opt(depth=1, exception=True).log("ERROR", event)

    @staticmethod
    def _log(level: str, event: str, **fields: Any) -> None:
        """
        Encaminha o registro para o loguru com os campos estruturados vinculados.

        Args:
            level: Nível do log (DEBUG, INFO, WARNING, ERROR).
            event: Nome do evento em snake_case.
            **fields: Campos estruturados anexados ao registro.
        """
        loguru_logger.bind(**fields).opt(depth=2).log(level, event)


_structured_logger = StructuredLogger()


def configure_logging(level: str = "INFO") -> None:
    """
    Configura o sink de log da aplicação (terminal colorido).

    Args:
        level: Nível mínimo de log a ser emitido.
    """
    loguru_logger.remove()
    loguru_logger.add(
        sys.stdout,
        level=level.upper(),
        format=LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=False,
    )


def get_logger() -> StructuredLogger:
    """
    Obtém o logger estruturado compartilhado pela aplicação.

    Returns:
        Instância de StructuredLogger pronta para uso.
    """
    return _structured_logger
