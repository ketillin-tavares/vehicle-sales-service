import httpx

_http_client: httpx.AsyncClient | None = None


async def start_http_client(timeout_seconds: float) -> None:
    """
    Cria o cliente HTTP compartilhado da aplicação.

    Args:
        timeout_seconds: Timeout aplicado às requisições de saída.
    """
    global _http_client
    _http_client = httpx.AsyncClient(timeout=timeout_seconds)


async def stop_http_client() -> None:
    """Encerra o cliente HTTP compartilhado, liberando as conexões abertas."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    """
    Obtém o cliente HTTP compartilhado da aplicação.

    Returns:
        Cliente httpx assíncrono criado no lifespan.

    Raises:
        RuntimeError: Se o cliente ainda não foi inicializado.
    """
    if _http_client is None:
        raise RuntimeError("Cliente HTTP não inicializado: start_http_client deve ser chamado no lifespan")
    return _http_client
