from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import SoldVehicleResponse, VehicleListingResponse
from src.application.use_cases import ListSoldVehicles, ListVehiclesForSale
from src.infrastructure.database import get_session
from src.interface.gateways import SQLAlchemySaleRepository, SQLAlchemyVehicleReplicaRepository

router = APIRouter(prefix="/vehicles", tags=["v1"])


@router.get("/for-sale", response_model=list[VehicleListingResponse])
async def list_vehicles_for_sale(
    session: AsyncSession = Depends(get_session),
) -> list[VehicleListingResponse]:
    """
    Lista os veículos disponíveis para venda, ordenados por preço crescente.

    Args:
        session: Sessão de banco fornecida pela dependência de infraestrutura.

    Returns:
        Lista de veículos disponíveis ordenada por preço.
    """
    use_case = ListVehiclesForSale(vehicle_replica_repository=SQLAlchemyVehicleReplicaRepository(session))
    return await use_case.execute()


@router.get("/sold", response_model=list[SoldVehicleResponse])
async def list_sold_vehicles(
    session: AsyncSession = Depends(get_session),
) -> list[SoldVehicleResponse]:
    """
    Lista os veículos vendidos, ordenados pelo preço de venda crescente.

    Args:
        session: Sessão de banco fornecida pela dependência de infraestrutura.

    Returns:
        Lista de veículos vendidos ordenada por preço de venda.
    """
    use_case = ListSoldVehicles(sale_repository=SQLAlchemySaleRepository(session))
    return await use_case.execute()
