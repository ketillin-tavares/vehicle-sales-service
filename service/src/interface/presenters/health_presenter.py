from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check do serviço."""

    status: str = Field(default="ok", description="Status atual do serviço")
    service: str = Field(..., description="Nome do serviço que respondeu à verificação")
    version: str = Field(..., description="Versão da aplicação em execução")
