import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import VehicleSnapshot
from src.application.use_cases import UpsertVehicleReplica
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import verify_internal_token
from src.interface.gateways import SQLAlchemyVehicleReplicaRepository
from src.interface.presenters import UnauthorizedResponse, VehicleSnapshotRequest, VehicleSyncResponse

router = APIRouter(prefix="/internal/v1/vehicles", tags=["internal"])


@router.put(
    "/{vehicle_id}",
    response_model=VehicleSyncResponse,
    dependencies=[Depends(verify_internal_token)],
    responses={401: {"model": UnauthorizedResponse}},
)
async def upsert_vehicle_replica(
    vehicle_id: uuid.UUID,
    request: VehicleSnapshotRequest,
    session: AsyncSession = Depends(get_session),
) -> VehicleSyncResponse:
    """
    Aplica o snapshot de catálogo publicado pelo vehicle-core-service.

    Args:
        vehicle_id: Identificador do veículo sincronizado.
        request: Campos de catálogo e versão do snapshot.
        session: Sessão de banco fornecida pela dependência de infraestrutura.

    Returns:
        DTO indicando se o snapshot foi aplicado ou descartado por ser obsoleto.
    """
    use_case = UpsertVehicleReplica(vehicle_replica_repository=SQLAlchemyVehicleReplicaRepository(session))
    snapshot = VehicleSnapshot(
        vehicle_id=vehicle_id,
        brand=request.brand,
        model=request.model,
        year=request.year,
        color=request.color,
        price=request.price,
        version=request.version,
    )
    applied = await use_case.execute(snapshot)
    return VehicleSyncResponse(vehicle_id=vehicle_id, applied=applied)
