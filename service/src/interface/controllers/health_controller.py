from fastapi import APIRouter

from src.environment import get_settings
from src.interface.presenters.health_presenter import HealthResponse

SERVICE_VERSION = "0.1.0"

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Verifica se o serviço está no ar.

    Returns:
        DTO com o status, o nome e a versão do serviço.
    """
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app.service_name, version=SERVICE_VERSION)
