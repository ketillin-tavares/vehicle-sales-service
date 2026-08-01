from pydantic import BaseModel, Field


class UnauthorizedResponse(BaseModel):
    """Resposta de erro para requisição sem credencial válida (HTTP 401)."""

    detail: str = Field(default="Token inválido ou ausente", description="Mensagem de erro")


class NotFoundResponse(BaseModel):
    """Resposta de erro para recurso não encontrado (HTTP 404)."""

    detail: str = Field(default="Recurso não encontrado", description="Mensagem de erro")


class ConflictResponse(BaseModel):
    """Resposta de erro para conflito de estado (HTTP 409)."""

    detail: str = Field(default="Operação conflita com o estado atual do recurso", description="Mensagem de erro")
