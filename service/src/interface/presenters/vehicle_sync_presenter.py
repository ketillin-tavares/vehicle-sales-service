import uuid

from pydantic import BaseModel, Field


class VehicleSyncResponse(BaseModel):
    """Resposta da sincronização de catálogo indicando se o snapshot foi aplicado."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo sincronizado")
    applied: bool = Field(..., description="True se o snapshot foi aplicado; False se descartado por ser obsoleto")
