from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    DomainError,
    InvalidCpfError,
    InvalidPaymentTransitionError,
    SaleNotFoundError,
    VehicleNotFoundError,
    VehicleUnavailableError,
)
from src.environment import get_settings
from src.infrastructure.database import async_engine
from src.infrastructure.http import start_http_client, stop_http_client
from src.infrastructure.observability import configure_logging, get_logger
from src.interface.controllers import (
    health_router,
    internal_vehicle_router,
    listing_router,
    payment_webhook_router,
    purchase_router,
)

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Gerencia o ciclo de vida da aplicação (startup/shutdown).

    Args:
        app: Instância da aplicação FastAPI gerenciada.

    Yields:
        Controle para o runtime enquanto a aplicação estiver ativa.
    """
    settings = get_settings()
    configure_logging(settings.app.log_level)
    await start_http_client(settings.core_service.timeout_seconds)
    logger.info("service_iniciando", service_name=settings.app.service_name)
    yield
    logger.info("service_encerrando", service_name=settings.app.service_name)
    await stop_http_client()
    await async_engine.dispose()


app = FastAPI(
    title="vehicle-sales-service",
    description="Serviço de venda de veículos: listagem, compras e webhook de pagamento",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(listing_router, prefix="/v1")
app.include_router(purchase_router, prefix="/v1")
app.include_router(payment_webhook_router)
app.include_router(internal_vehicle_router)
app.include_router(health_router)


@app.exception_handler(VehicleNotFoundError)
async def vehicle_not_found_handler(request: Request, exc: VehicleNotFoundError) -> JSONResponse:
    """
    Traduz VehicleNotFoundError para HTTP 404.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de veículo inexistente.

    Returns:
        Resposta JSON com status 404 e o detalhe do erro.
    """
    logger.info("veiculo_nao_encontrado", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(SaleNotFoundError)
async def sale_not_found_handler(request: Request, exc: SaleNotFoundError) -> JSONResponse:
    """
    Traduz SaleNotFoundError para HTTP 404.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de venda inexistente.

    Returns:
        Resposta JSON com status 404 e o detalhe do erro.
    """
    logger.info("venda_nao_encontrada", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(VehicleUnavailableError)
async def vehicle_unavailable_handler(request: Request, exc: VehicleUnavailableError) -> JSONResponse:
    """
    Traduz VehicleUnavailableError para HTTP 409.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de veículo indisponível.

    Returns:
        Resposta JSON com status 409 e o detalhe do erro.
    """
    logger.info("veiculo_indisponivel", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidPaymentTransitionError)
async def invalid_payment_transition_handler(request: Request, exc: InvalidPaymentTransitionError) -> JSONResponse:
    """
    Traduz InvalidPaymentTransitionError para HTTP 409.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de transição de pagamento ilegal.

    Returns:
        Resposta JSON com status 409 e o detalhe do erro.
    """
    logger.info("transicao_de_pagamento_invalida", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCpfError)
async def invalid_cpf_handler(request: Request, exc: InvalidCpfError) -> JSONResponse:
    """
    Traduz InvalidCpfError para HTTP 422.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de CPF inválido.

    Returns:
        Resposta JSON com status 422 e o detalhe do erro.
    """
    logger.info("cpf_invalido", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """
    Traduz erros de domínio não mapeados especificamente para HTTP 400.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de domínio levantada durante o processamento.

    Returns:
        Resposta JSON com status 400 e o detalhe do erro.
    """
    logger.error("erro_de_dominio", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})
